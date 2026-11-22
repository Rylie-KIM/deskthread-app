"""Finding candidate notes with no stored index (FT-08, plan 25).

Everything is computed in memory for each question and thrown away. P0 is the keyword
floor: the question's own words. P3 adds words suggested by the local model for the same
topic, and names (the person from the calendar). A relevance rule runs before the model is
asked to answer: when nothing passes it, the answer is "not found" and no model call is made.
"""

import math
import re
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta

from app.clock import now
from contracts.items import Item, ItemKind

STOP = frozenset(
    [
        "a",
        "an",
        "the",
        "and",
        "or",
        "but",
        "if",
        "of",
        "to",
        "in",
        "on",
        "at",
        "for",
        "from",
        "by",
        "with",
        "about",
        "into",
        "over",
        "after",
        "before",
        "as",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "am",
        "do",
        "does",
        "did",
        "done",
        "have",
        "has",
        "had",
        "having",
        "i",
        "me",
        "my",
        "mine",
        "we",
        "our",
        "you",
        "your",
        "it",
        "its",
        "this",
        "that",
        "these",
        "those",
        "there",
        "here",
        "what",
        "which",
        "who",
        "whom",
        "whose",
        "when",
        "where",
        "why",
        "how",
        "not",
        "no",
        "yes",
        "so",
        "than",
        "then",
        "too",
        "very",
        "can",
        "could",
        "should",
        "would",
        "will",
        "shall",
        "may",
        "might",
        "must",
        "any",
        "some",
        "all",
        "each",
        "every",
        "both",
        "more",
        "most",
        "other",
        "such",
        "only",
        "own",
        "same",
        "just",
        "also",
        "still",
        "yet",
        "ever",
        "s",
        "t",
        "re",
        "ve",
        "ll",
        "d",
        "m",
        "get",
        "got",
    ]
)
# Words that say "a commitment" without naming a subject. They never count as the topic.
GENERIC = frozenset(
    [
        "promise",
        "promised",
        "promising",
        "say",
        "said",
        "tell",
        "told",
        "agree",
        "agreed",
        "commit",
        "committed",
        "offer",
        "offered",
        "owe",
        "note",
        "notes",
        "wrote",
        "written",
        "write",
        "mention",
        "mentioned",
        "thing",
        "things",
        "anything",
        "something",
        "open",
        "status",
        "happen",
        "happening",
        "left",
        "plan",
        "planned",
        "give",
        "gave",
        "stand",
        "stands",
        "standing",
    ]
)
COMMITMENT = frozenset(
    [
        "promise",
        "said",
        "agree",
        "commit",
        "offer",
        "owe",
        "will",
        "ill",
        "back",
        "intro",
        "instead",
        "approve",
        "still",
        "todo",
        "ask",
        "send",
        "set",
        "chase",
    ]
)
_WORD = re.compile(r"[a-z0-9]+(?:'[a-z]+)?")
_NAME = re.compile(r"\b[A-Z][a-z]+\b|\b[A-Z]{2,}\b")


def stem(word: str) -> str:
    """A light stem so promise/promised and course/courses meet. Not linguistics."""
    word = word.split("'")[0]
    for suffix, keep in (("ies", "y"), ("ing", ""), ("ed", ""), ("es", ""), ("s", "")):
        if word.endswith(suffix) and len(word) - len(suffix) >= 3 and not word.endswith("ss"):
            word = word[: -len(suffix)] + keep
            break
    return word[:-1] if word.endswith("e") and len(word) > 4 else word


def stems(text: str) -> list[str]:
    return [stem(w) for w in _WORD.findall(text.lower())]


def names_in(question: str) -> set[str]:
    """Capitalised words that are not the first word: Sam, Mark, HR."""
    found = {m.group(0) for m in _NAME.finditer(question)}
    first = question.strip().split(" ")[0].strip("?,.") if question.strip() else ""
    return {n for n in found if n != first and n.lower() not in STOP and n != "I"}


@dataclass
class Query:
    question: str
    people: set[str] = field(default_factory=set)  # stems of names
    focus: set[str] = field(default_factory=set)  # stems of the topic words
    extra: set[str] = field(default_factory=set)  # stems of model-suggested words (P3)
    focus_words: list[str] = field(default_factory=list)  # the topic words as written
    # The stretch of time the question names ("today", "this week"), in local time. Items
    # dated inside it are shown whatever their words are: a calendar entry for tonight
    # does not contain the word "today".
    window: tuple[datetime, datetime] | None = None
    window_name: str = ""
    # The question asks what is still ahead ("still to do", "left", "upcoming"): then only
    # what is not over counts, and a done reminder does not.
    forward: bool = False

    @property
    def topic(self) -> set[str]:
        return self.focus | self.extra


# Words that name a stretch of time, and words that only mean "what is on" once one is named.
_WHEN = ("today", "tonight", "tomorrow", "yesterday", "week", "weekend", "now", "morning",
         "afternoon", "evening", "day", "next", "upcoming", "coming")  # fmt: skip
_AGENDA = ("todo", "todos", "do", "schedule", "scheduled", "agenda", "calendar", "plan", "plans",
           "meeting", "meetings", "event", "events", "task", "tasks", "appointment",
           "appointments",
           "reminder", "reminders", "due", "list", "have", "got", "need", "tell",
           "show")  # fmt: skip


def time_window(
    question: str, moment: datetime | None = None
) -> tuple[datetime, datetime, str] | None:
    """The stretch of time a question names, as local day bounds, or None."""
    local = (moment or now()).astimezone()
    words = set(_WORD.findall(question.lower()))
    start = datetime.combine(local.date(), time.min, local.tzinfo)

    def days(first: int, count: int, name: str) -> tuple[datetime, datetime, str]:
        begin = start + timedelta(days=first)
        return begin, begin + timedelta(days=count) - timedelta(microseconds=1), name

    if "tomorrow" in words:
        return days(1, 1, "tomorrow")
    if "yesterday" in words:
        return days(-1, 1, "yesterday")
    if "week" in words:
        monday = -local.weekday()
        return days(monday + 7, 7, "next week") if "next" in words else days(monday, 7, "this week")
    if "weekend" in words:
        return days(5 - local.weekday(), 2, "the weekend")
    if words & {"today", "tonight"}:
        return days(0, 1, "today")
    return None


_FORWARD = frozenset(
    stem(w)
    for w in ("still", "left", "remaining", "remain", "pending", "upcoming", "coming", "due",
              "todo", "ahead", "outstanding")
)  # fmt: skip


def is_forward(question: str) -> bool:
    """Does the question ask for what is still ahead, not for what happened?"""
    text = " " + " ".join(_WORD.findall(question.lower())) + " "
    return bool(_FORWARD & set(stems(question))) or " to do " in text


def build_query(
    question: str, person: str | None = None, spellings: dict[str, tuple[str, ...]] | None = None
) -> Query:
    """`spellings`: a name -> other ways the user writes it ("Sam" -> "Samuel", "Sammy"). If the
    question uses any of them, all of them count as that person."""
    people = {stem(n.lower()) for n in names_in(question)}
    if person:
        people.add(stem(person.lower()))
    asked = set(stems(question))
    for name, others in (spellings or {}).items():
        group = {s for text in (name, *others) for s in stems(text) if len(s) > 1}
        if group & (asked | people):
            people |= group
    when = time_window(question)
    skip = {stem(g) for g in GENERIC} | ({stem(w) for w in (*_WHEN, *_AGENDA)} if when else set())
    focus_words = [
        w
        for w in dict.fromkeys(_WORD.findall(question.lower()))
        if w not in STOP and stem(w) not in people and stem(w) not in skip
    ]
    return Query(
        question=question,
        people=people,
        focus={stem(w) for w in focus_words},
        focus_words=focus_words,
        window=(when[0], when[1]) if when else None,
        window_name=when[2] if when else "",
        forward=bool(when) and is_forward(question),
    )


def in_window(query: Query, item: Item) -> bool:
    """Is the item dated inside the time the question names? An open reminder with no date
    counts for a stretch that includes today: it is still to do."""
    if query.window is None:
        return False
    start, end = query.window
    today = now().astimezone()
    if item.kind is ItemKind.REMINDER and query.forward:
        if item.meta.get("status") != "open":
            return False  # done: nothing left to do
        if item.date is None:
            return start <= today <= end
        moment = item.date if item.date.tzinfo else item.date.replace(tzinfo=start.tzinfo)
        return moment <= end  # an open reminder that is overdue is still to do
    if item.date is None:
        return (
            item.kind is ItemKind.REMINDER
            and item.meta.get("status") == "open"
            and start <= today <= end
        )
    moment = item.date if item.date.tzinfo else item.date.replace(tzinfo=start.tzinfo)
    if query.forward:
        start = max(start, today)  # what has already happened is not still to do
    return start <= moment <= end


def add_expansion(query: Query, words: list[str]) -> None:
    for phrase in words[:12]:
        for s in stems(str(phrase)):
            if s not in STOP and s not in query.people and len(s) > 2:
                query.extra.add(s)
    query.extra -= query.focus


def item_stems(item: Item) -> set[str]:
    text = " ".join([item.title, item.meta.get("attendees", ""), *(u.text for u in item.units)])
    return set(stems(text))


@dataclass(frozen=True)
class Candidate:
    item: Item
    score: float


def find(query: Query, items: list[Item], limit: int | None = None) -> list[Candidate]:
    """Score every readable item against the query. Nothing is stored between questions."""
    if limit is None:
        # "What did I promise Sam?" has no topic of its own: show every note on the person.
        limit = 14 if query.topic else 26
    bags = [(item, item_stems(item)) for item in items if item.units]
    total = len(bags) or 1
    seen: dict[str, int] = {}
    for _, bag in bags:
        for s in bag:
            seen[s] = seen.get(s, 0) + 1

    def idf(term: str) -> float:
        return math.log(1 + total / seen[term]) if term in seen else 0.0

    commitment = {stem(w) for w in COMMITMENT}
    out: list[Candidate] = []
    for item, bag in bags:
        if in_window(query, item):
            # Named by its date: shown first, in the order of the day.
            order = item.date.timestamp() if item.date else 0.0
            out.append(Candidate(item, 1e6 - order / 1e6))
            continue
        if query.window is not None and not query.topic and not query.people:
            # "What is on today?" has no topic: only what is dated then, plus, when the
            # question asks what is to do, undated notes that are marked as a to-do list.
            asks_todo = bool({"todo", "todos", "do", "task", "tasks"} & set(stems(query.question)))
            if asks_todo and item.date is None and {"todo", "task"} & bag:
                out.append(Candidate(item, 1.0))
            continue
        on_person = bool(query.people & bag)
        on_focus = bool(query.focus & bag)
        on_extra = bool(query.extra & bag)
        # The relevance rule. A question with a topic needs the topic (or a suggested word
        # for it) in the note; a name alone is not enough. A question with no topic of its
        # own ("What did I promise Sam?") needs the person.
        if query.topic:
            if not (on_focus or on_extra):
                continue
            if query.people and not on_person and not on_focus:
                continue
        elif not on_person:
            continue
        if item.kind is ItemKind.EVENT and not on_focus:
            continue  # the calendar says who and when, not what was promised
        score = sum(2.0 * idf(t) for t in query.focus & bag)
        score += sum(0.8 * idf(t) for t in query.extra & bag)
        score += sum(1.5 * idf(t) for t in query.people & bag)
        score += 0.3 * len(commitment & bag)
        out.append(Candidate(item, score))
    out.sort(key=lambda c: (-c.score, c.item.item_id))
    return out[:limit]


def keyword_floor(phrase: str, items: list[Item]) -> list[Item]:
    """P0, what an ordinary search does: the exact phrase, nothing else (test D1)."""
    needle = " ".join(phrase.lower().split())
    return [
        item
        for item in items
        if needle in " ".join(" ".join([item.title, *(u.text for u in item.units)]).lower().split())
    ]
