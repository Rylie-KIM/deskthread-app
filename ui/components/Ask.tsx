import { useEffect, useState } from "react";
import { api, clock, day, plain, type Answer, type BriefPoint, type Citation, type Meeting, type Progress } from "../lib/api";

// Plain words for the status of something promised or to do.
const STATUS_TEXT = { done: "Done", open: "Still to do", changed: "Changed", superseded: "No longer valid" } as const;
// The steps of one question, in order (the same names the backend reports).
const STEPS = ["Reading your folders", "Reading pictures", "Finding the right items", "Asking the AI on this Mac", "Checking the answer"];
const STEP: Record<string, string> = { G1: "Allowed to read", G2: "Searched", G3: "AI used", G4: "Answer check", G6: "Record kept" };

// How long an answer took, in plain words.
const took = (seconds: number) => (seconds < 60 ? `${Math.max(1, Math.round(seconds))} s` : `${Math.floor(seconds / 60)} min ${Math.round(seconds % 60)} s`);

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

// One thing found: a closed row (name, newest date, number of quotes, status). Opening it
// shows why it is there and the exact words, each with the note it comes from.
function Finding({ point, showStatus, first, onCite }: { point: BriefPoint; showStatus: boolean; first: boolean; onCite: (cite: Citation) => void }) {
  const [open, setOpen] = useState(first);
  const notes = byNote(point.citations);
  const newest = notes[0]?.head;
  const count = point.citations.length;
  return (
    <article className={open ? "finding open" : "finding"}>
      <button type="button" className="findrow" aria-expanded={open} onClick={() => setOpen(!open)}>
        <i className="chev" aria-hidden="true" />
        <b>{point.label}</b>
        <span className="when">{!newest || newest.undated ? "No date" : day(newest.date)}</span>
        <span className="n">{count} {count === 1 ? "quote" : "quotes"}</span>
        {showStatus && <em className={`tag state-${point.status}`}>{STATUS_TEXT[point.status]}</em>}
      </button>
      {open && (
        <div className="findbody">
          <p className="why">
            {point.matched.length > 0 ? <>Shown because it mentions {point.matched.map((word) => <em key={word} className="tag">{word}</em>)}</> : "Shown because the AI judged it to be about your question"}
          </p>
          {point.note && <p className="note">Written as a question or a maybe, not as a clear promise.</p>}
          <ul>
            {notes.flatMap((group) => group.cites).map((cite) => (
              <li key={`${cite.item_id}-${cite.unit}`}>
                <button className="cite" onClick={() => onCite(cite)} title="Open the source">
                  <span className="quote">“{cite.quote.replace(/^[-*•]\s*/, "")}”</span>
                  <span className="origin">
                    <span>{cite.title}</span>
                    <span>{cite.undated ? "No date" : day(cite.date)}</span>
                    <span>{cite.read_by_model ? "Read from the picture" : cite.source_label}</span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </article>
  );
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
          <div className="findings">
            {answer.points.map((point, index) => (
              <Finding key={index} point={point} showStatus={answer.show_status} first={index === 0} onCite={onCite} />
            ))}
          </div>
        </>
      )}
      <p className="looked bits">
        <span>Looked through <b>{answer.coverage.searched}</b> items</span>
        <span className="took">Answered in {took(answer.seconds)}</span>
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
