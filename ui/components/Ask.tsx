import { useEffect, useState } from "react";
import { api, clock, day, plain, type Answer, type Citation, type Meeting, type Progress } from "../lib/api";

// Plain words for the status of something promised or to do.
const STATUS_TEXT = { done: "Done", open: "Still to do", changed: "Changed", superseded: "No longer valid" } as const;
// The steps of one question, in order (the same names the backend reports).
const STEPS = ["Reading your folders", "Reading pictures", "Finding the right items", "Asking the AI on this Mac", "Checking the answer"];
const STEP: Record<string, string> = { G1: "Allowed to read", G2: "Searched", G3: "AI used", G4: "Answer check", G6: "Record kept" };

// The quotes of one finding, grouped by the note they come from, newest note first.
function byNote(cites: Citation[]): { head: Citation; cites: Citation[] }[] {
  const groups = new Map<string, { head: Citation; cites: Citation[] }>();
  for (const cite of cites) {
    const group = groups.get(cite.item_id);
    if (group) group.cites.push(cite);
    else groups.set(cite.item_id, { head: cite, cites: [cite] });
  }
  const time = (c: Citation) => (c.date ? new Date(c.date).getTime() : -Infinity);
  return [...groups.values()].sort((x, y) => time(y.head) - time(x.head));
}

// An entry opened in the source viewer: the same viewer that shows a quoted note.
const open = (meeting: Meeting): Citation => ({
  item_id: meeting.meeting_id, unit: 0, quote: "", source_id: "", source_label: "", title: meeting.title,
  date: meeting.start, undated: false, read_by_model: false,
});

function when(meeting: Meeting, nowIso: string): string {
  const start = new Date(meeting.start);
  const now = new Date(nowIso);
  const days = Math.round((new Date(start).setHours(0, 0, 0, 0) - new Date(now).setHours(0, 0, 0, 0)) / 86_400_000);
  const label = days === 0 ? "Today" : days === 1 ? "Tomorrow" : start.toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" });
  return `${label} ${clock(meeting.start)}`;
}

function Found({ answer, onCite }: { answer: Answer; onCite: (cite: Citation) => void }) {
  const [details, setDetails] = useState(false);
  return (
    <div className="reply">
      {answer.kind !== "brief" ? (
        <p className="nothing">{answer.kind === "no_sources" ? "Nothing is switched on yet, so there is nothing I can read." : "I could not find this in what you switched on."}</p>
      ) : (
        <>
          <p className="replyhead">Found in your notes</p>
          {answer.summary.length > 0 && (
            <div className="summary">
              <span className="eyebrow">Summary by the AI</span>
              {answer.summary.map((text) => <p key={text}>{text}</p>)}
            </div>
          )}
          <p className="bits tally">
            <span><b>{answer.points.length}</b> {answer.points.length === 1 ? "thing found" : "things found"}</span>
            <span><b>{answer.coverage.cited}</b> {answer.coverage.cited === 1 ? "note" : "notes"} quoted word for word</span>
            <span>Newest note first</span>
          </p>
          {answer.points.map((point, index) => (
            <article key={index} className="finding">
              <header className="row wrap">
                <h3>{point.label}</h3>
                {answer.show_status && <span className={`status ${point.status}`}>{STATUS_TEXT[point.status]}</span>}
              </header>
              <p className="why">
                {point.matched.length > 0 ? <>Shown because it mentions {point.matched.map((word) => <em key={word} className="tag">{word}</em>)}</> : "Shown because the AI judged it to be about your question"}
              </p>
              {point.note && <p className="note">Written as a question or a maybe, not as a clear promise.</p>}
              {byNote(point.citations).map((group) => (
                <div className="group" key={group.head.item_id}>
                  <p className="grouphead">
                    <em className="tag">{group.head.source_label}</em>
                    <b>{group.head.title}</b>
                    <span className="when">{group.head.undated ? "No date" : day(group.head.date)}</span>
                    {group.head.read_by_model && <em className="tag">Read from the picture</em>}
                  </p>
                  <ul>
                    {group.cites.map((cite) => (
                      <li key={`${cite.item_id}-${cite.unit}`}>
                        <button className="cite" onClick={() => onCite(cite)} title="Open the source">
                          <span className="quote">“{cite.quote.replace(/^[-*•]\s*/, "")}”</span>
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </article>
          ))}
        </>
      )}
      <p className="looked bits">
        <span>Looked through <b>{answer.coverage.searched}</b> items</span>
        <button className="link" onClick={() => setDetails(!details)}>{details ? "Hide the checks" : "How this was checked"}</button>
      </p>
      {details && (
        <table className="checks">
          <tbody>
            {answer.gate_trace.map((gate) => (
              <tr key={gate.gate}>
                <th scope="row">{STEP[gate.gate] ?? gate.gate}</th>
                <td>{gate.detail.split(/;\s*/).map((part) => <span key={part}>{part}</span>)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

interface Props {
  now: string;
  anyOn: boolean;
  visible: boolean;
  thread: Answer[];
  onAnswer: (answer: Answer) => void;
  onCite: (cite: Citation) => void;
  onError: (message: string) => void;
  first?: string;
}

export default function Ask({ now, anyOn, visible, thread, onAnswer, onCite, onError, first }: Props) {
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [question, setQuestion] = useState("");
  const [asking, setAsking] = useState("");
  const [progress, setProgress] = useState<Progress | null>(null);

  useEffect(() => {
    if (visible) api.meetings().then(setMeetings).catch(() => setMeetings([]));
  }, [anyOn, visible]);

  // While a question runs, ask the backend which step it is on.
  useEffect(() => {
    if (asking === "") return setProgress(null);
    const timer = setInterval(() => api.progress().then(setProgress).catch(() => undefined), 500);
    return () => clearInterval(timer);
  }, [asking]);

  async function run(shown: string, work: () => Promise<Answer>) {
    setAsking(shown);
    try {
      const answer = await work();
      if (answer.kind === "stopped") return;  // stopped by the user: the question stays in the box
      onAnswer(answer);
      setQuestion("");
    } catch (err) {
      onError(plain(err));
    } finally {
      setAsking("");
    }
  }
  const ask = (text: string) => run(text, () => api.ask(text));

  // A question carried in the address ("&q=...") is asked once when the screen opens.
  useEffect(() => {
    if (first && anyOn && thread.length === 0) void ask(first);
  }, [first, anyOn]);

  const person = meetings.find((m) => m.person)?.person;
  const examples = [person ? `What did I promise ${person}?` : "What did I promise the team?", "What is still to do this week?", "Where did I note the budget?"];

  return (
    <section>
      <h1>Find anything you wrote down.</h1>
      {!anyOn && <p className="empty">Nothing is switched on yet. Go to Access first.</p>}

      {meetings.length > 0 && (
        <div className="coming">
          <h2>Coming up</h2>
          <ul>
            {meetings.map((meeting) => (
              <li key={meeting.meeting_id}>
                <button type="button" className="entry" title="Open this entry" onClick={() => onCite(open(meeting))}>
                  <span className="time">{when(meeting, now)}</span>
                  <b>{meeting.title}</b>
                </button>
                {/* The whole entry, shown while the pointer or the keyboard is on it. */}
                <span className="peek" role="tooltip">
                  <b>{meeting.title}</b>
                  <span>{new Date(meeting.start).toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long", year: "numeric" })}, {clock(meeting.start)}</span>
                  {meeting.person && <span>With {meeting.person}</span>}
                </span>
                <button className="ghost small" disabled={asking !== ""} onClick={() => run(`Prepare: ${meeting.title}`, () => api.prepare(meeting.meeting_id))}>Prepare</button>
              </li>
            ))}
          </ul>
        </div>
      )}

      <form className="card row ask" onSubmit={(e) => { e.preventDefault(); if (question.trim()) void ask(question.trim()); }}>
        <input aria-label="Your question" placeholder="Ask in your own words" value={question} maxLength={500} disabled={asking !== ""} onChange={(e) => setQuestion(e.target.value)} />
        {asking !== "" ? (
          <button type="button" className="ghost" onClick={() => { api.cancel().catch(() => undefined); }}>Stop</button>
        ) : (
          <button className="primary" disabled={!question.trim() || !anyOn}>Ask</button>
        )}
      </form>
      {thread.length === 0 && asking === "" && anyOn && (
        <div className="row wrap chips">
          {examples.map((text) => <button key={text} className="chipbtn" onClick={() => ask(text)}>{text}</button>)}
        </div>
      )}

      <div className="thread" aria-live="polite">
        {asking !== "" && (
          <div className="turn">
            <p className="mine">{asking}</p>
            <div className="reply progress" role="status">
              <ol className="steps">
                {STEPS.map((name, index) => {
                  const at = progress?.number ?? 0;
                  const state = index + 1 < at ? "past" : index + 1 === at ? "now" : "next";
                  return <li key={name} className={state}><i>{index + 1 < at ? "✓" : index + 1}</i>{name}{state === "now" && progress?.detail ? <small>{progress.detail}</small> : null}</li>;
                })}
              </ol>
            </div>
          </div>
        )}
        {[...thread].reverse().map((answer, index) => (
          <div className="turn" key={thread.length - index}>
            <p className="mine">{answer.question}</p>
            <Found answer={answer} onCite={onCite} />
          </div>
        ))}
      </div>

    </section>
  );
}
