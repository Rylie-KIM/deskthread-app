"""Finding candidate notes with no stored index (FT-08, plan 25).

Everything is computed in memory for each question and thrown away. P0 is the keyword
floor: the question's own words. P3 adds words suggested by the local model for the same
topic, and names (the person from the calendar). A relevance rule runs before the model is
asked to answer: when nothing passes it, the answer is "not found" and no model call is made.
"""

import math
import re
from dataclasses import dataclass, field

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

    @property
    def topic(self) -> set[str]:
        return self.focus | self.extra


def build_query(question: str, person: str | None = None) -> Query:
    people = {stem(n.lower()) for n in names_in(question)}
    if person:
        people.add(stem(person.lower()))
    focus_words = [
        w
        for w in dict.fromkeys(_WORD.findall(question.lower()))
        if w not in STOP and stem(w) not in people and stem(w) not in {stem(g) for g in GENERIC}
    ]
    return Query(
        question=question,
        people=people,
        focus={stem(w) for w in focus_words},
        focus_words=focus_words,
    )


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
