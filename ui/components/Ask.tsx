import { useEffect, useState } from "react";
import { api, clock, day, plain, type Answer, type Citation, type Meeting, type Progress } from "../lib/api";

// Plain words for the status of something promised or to do.
const STATUS_TEXT = { done: "Done", open: "Still to do", changed: "Changed", superseded: "No longer valid" } as const;
// The steps of one question, in order (the same names the backend reports).
const STEPS = ["Reading your folders", "Reading pictures", "Finding the right items", "Asking the AI on this Mac", "Checking the answer"];
const STEP: Record<string, string> = { G1: "Access rules", G2: "Reading", G3: "AI on this Mac", G4: "Answer check", G6: "Record" };

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
          {answer.points.map((point, index) => (
            <article key={index} className="finding">
              <header className="row wrap">
                <h3>{point.label}</h3>
                {answer.show_status && <span className={`status ${point.status}`}>{STATUS_TEXT[point.status]}</span>}
              </header>
              {point.note && <p className="note">Written as a question or a maybe, not as a clear promise.</p>}
              <ul>
                {point.citations.map((cite) => (
                  <li key={`${cite.item_id}-${cite.unit}`}>
                    <button className="cite" onClick={() => onCite(cite)} title="Open the source">
                      <span className="quote">“{cite.quote.replace(/^[-*•]\s*/, "")}”</span>
                      <span className="from">
                        {cite.source_label} · {cite.title} · <span className={cite.undated ? "undated" : ""}>{cite.undated ? "no date" : day(cite.date)}</span>
                        {cite.read_by_model && " · read from the picture by the AI"}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            </article>
          ))}
        </>
      )}
      <p className="looked">
        Looked through {answer.coverage.searched} items{answer.kind === "brief" ? ` · quoted ${answer.coverage.cited}` : ""} ·{" "}
        <button className="link" onClick={() => setDetails(!details)}>{details ? "Hide" : "How this was checked"}</button>
      </p>
      {details && (
        <ul className="trace">
          {answer.gate_trace.map((gate) => <li key={gate.gate}><b>{STEP[gate.gate] ?? gate.gate}</b> {gate.detail}</li>)}
        </ul>
      )}
    </div>
  );
}

interface Props {
  now: string;
  anyOn: boolean;
  thread: Answer[];
  onAnswer: (answer: Answer) => void;
  onCite: (cite: Citation) => void;
  onError: (message: string) => void;
  first?: string;
}

export default function Ask({ now, anyOn, thread, onAnswer, onCite, onError, first }: Props) {
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [question, setQuestion] = useState("");
  const [asking, setAsking] = useState("");
  const [progress, setProgress] = useState<Progress | null>(null);

  useEffect(() => {
    api.meetings().then(setMeetings).catch(() => setMeetings([]));
  }, [anyOn]);

  // While a question runs, ask the backend which step it is on.
  useEffect(() => {
    if (asking === "") return setProgress(null);
    const timer = setInterval(() => api.progress().then(setProgress).catch(() => undefined), 500);
    return () => clearInterval(timer);
  }, [asking]);

  async function run(shown: string, work: () => Promise<Answer>) {
    setAsking(shown);
    try {
      onAnswer(await work());
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

      <form className="card row ask" onSubmit={(e) => { e.preventDefault(); if (question.trim()) void ask(question.trim()); }}>
        <input aria-label="Your question" placeholder="Ask in your own words" value={question} maxLength={500} disabled={asking !== ""} onChange={(e) => setQuestion(e.target.value)} />
        <button className="primary" disabled={asking !== "" || !question.trim() || !anyOn}>{asking !== "" ? "Looking…" : "Ask"}</button>
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
                  return <li key={name} className={state}><i>{index + 1 < at ? "✓" : index + 1}</i>{name}</li>;
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

      {meetings.length > 0 && (
        <div className="coming">
          <h2>Coming up</h2>
          <ul>
            {meetings.map((meeting) => (
              <li key={meeting.meeting_id}>
                <span className="time">{when(meeting, now)}</span>
                <b>{meeting.title}</b>
                <button className="ghost small" disabled={asking !== ""} onClick={() => run(`Prepare: ${meeting.title}`, () => api.prepare(meeting.meeting_id))}>Prepare</button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
