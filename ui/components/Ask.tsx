import { useEffect, useState } from "react";
import { api, ApiError, clock, day, type Answer, type Citation, type Meeting } from "../lib/api";

const STATUS_TEXT = { done: "Done", open: "Open", changed: "Changed", superseded: "Superseded" } as const;

function when(meeting: Meeting, nowIso: string): string {
  const start = new Date(meeting.start);
  const now = new Date(nowIso);
  const days = Math.round((new Date(start).setHours(0, 0, 0, 0) - new Date(now).setHours(0, 0, 0, 0)) / 86_400_000);
  const label = days === 0 ? "Today" : days === 1 ? "Tomorrow" : start.toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "short" });
  return `${label} ${clock(meeting.start)}`;
}

interface Props {
  now: string;
  anyOn: boolean;
  answer: Answer | null;
  onAnswer: (answer: Answer) => void;
  onCite: (cite: Citation) => void;
  onError: (message: string) => void;
}

export default function Ask({ now, anyOn, answer, onAnswer, onCite, onError }: Props) {
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState("");
  const [details, setDetails] = useState(false);

  useEffect(() => {
    api.meetings().then(setMeetings).catch(() => setMeetings([]));
  }, [anyOn]);

  async function run(label: string, work: () => Promise<Answer>) {
    setBusy(label);
    try {
      onAnswer(await work());
    } catch (err) {
      onError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setBusy("");
    }
  }

  return (
    <section>
      <p className="kicker">Prepare</p>
      <h1>What is coming up, and what you wrote about it.</h1>

      {!anyOn && <p className="empty">No source is On. Go to Sources first: nothing can be read yet.</p>}

      {meetings.length > 0 && (
        <div className="meetings">
          {meetings.slice(0, 3).map((meeting) => (
            <article key={meeting.meeting_id} className="meeting">
              <p className="time">{when(meeting, now)}</p>
              <h3>{meeting.title}</h3>
              <button className="primary" disabled={busy !== ""} onClick={() => run(meeting.meeting_id, () => api.prepare(meeting.meeting_id))}>
                {busy === meeting.meeting_id ? "Reading your notes…" : "Prepare"}
              </button>
            </article>
          ))}
        </div>
      )}
      {anyOn && meetings.length === 0 && <p className="fine">No one-to-one found in an allowed calendar for the next seven days.</p>}

      <form className="card row ask" onSubmit={(e) => { e.preventDefault(); if (question.trim()) void run("ask", () => api.ask(question.trim())); }}>
        <input aria-label="Your question" placeholder="Ask about your own notes, e.g. What salary did I promise Sam?" value={question} maxLength={500} onChange={(e) => setQuestion(e.target.value)} />
        <button className="primary" disabled={busy !== "" || !question.trim() || !anyOn}>{busy === "ask" ? "Looking…" : "Ask"}</button>
      </form>
      {busy !== "" && <p className="fine" role="status">The model on this laptop is working. The first answer takes longest, because it loads and reads the images.</p>}

      {answer && (
        <div className="answer" aria-live="polite">
          <p className="asked">{answer.question}</p>
          {answer.kind !== "brief" && <div className="notfound"><b>{answer.message}</b></div>}
          {answer.points.map((point, index) => (
            <article key={index} className="point">
              <header className="row wrap">
                <span className={`chip ${point.status}`}>{STATUS_TEXT[point.status]}</span>
                <h3>{point.label}</h3>
              </header>
              {point.note && <p className="note">{point.note}</p>}
              <ul>
                {point.citations.map((cite) => (
                  <li key={`${cite.item_id}-${cite.unit}`}>
                    <button className="cite" onClick={() => onCite(cite)} title="Open the source, read-only">
                      <span className="quote">“{cite.quote}”</span>
                      <span className="from">
                        {cite.source_label} · {cite.title} · <span className={cite.undated ? "undated" : ""}>{day(cite.date)}</span>
                        {cite.read_by_model && " · read from the image by the model"}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            </article>
          ))}

          <div className="coverage">
            <p>
              <b>What it looked at:</b> {answer.coverage.accessible} readable · {answer.coverage.searched} searched · {answer.coverage.unsupported} could not be read · {answer.coverage.given_to_model} shown to the model · {answer.coverage.cited} cited · {answer.seconds}s
            </p>
            <p>
              <b>Out of reach:</b>{" "}
              {Object.entries(answer.coverage.not_accessible).map(([name, count]) => `${name}: ${count === null ? "locked" : count}`).join(" · ")}
            </p>
            <button className="link" onClick={() => setDetails(!details)}>{details ? "Hide the checks" : "Show the checks behind this answer"}</button>
            {details && (
              <ul className="trace">
                {answer.gate_trace.map((gate) => (
                  <li key={gate.gate}><span className={`chip ${gate.outcome}`}>{gate.gate} {gate.outcome}</span> {gate.detail}</li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
