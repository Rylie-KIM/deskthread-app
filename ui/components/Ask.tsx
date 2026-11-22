import { useEffect, useState } from "react";
import { api, clock, day, plain, type Answer, type BriefPoint, type Citation, type ItemRef, type Meeting, type Preparing, type Progress } from "../lib/api";

// Plain words for the status of something promised or to do.
const STATUS_TEXT = { done: "Done", open: "Still to do", changed: "Changed", superseded: "No longer valid" } as const;
// The steps of one question, in order (the same names the backend reports).
const STEPS = ["Reading your folders", "Reading pictures", "Finding the right items", "Asking the AI on this Mac", "Checking the answer"];
const STEP: Record<string, string> = { G1: "Allowed to read", G2: "Searched", G3: "AI used", G4: "Answer check", G6: "Record kept" };

// What was left out on the way to an answer, in plain words (one, many).
const SHOWS: Record<string, Stage> = { off_limits: "off", unreadable: "unread", dropped: "dropped", instructions: "instructions" };
const LEFT: [string, string, string][] = [
  ["off_limits", "file was skipped because you marked it off-limits", "files were skipped because you marked them off-limits"],
  ["unreadable", "item could not be read", "items could not be read"],
  ["dropped", "quote was dropped because it was about something else", "quotes were dropped because they were about something else"],
  ["nowhere", "reference by the AI pointed at a line that does not exist and was dropped", "references by the AI pointed at lines that do not exist and were dropped"],
  ["instructions", "note contained instructions to an assistant; they were ignored", "notes contained instructions to an assistant; they were ignored"],
];

// An item named in a list, opened in the same viewer as a quote.
const refCite = (ref: ItemRef): Citation => ({
  item_id: ref.item_id, unit: 0, quote: "", source_id: "", source_label: ref.source_label, title: ref.title,
  date: ref.date, undated: false, read_by_model: false,
});

type Stage = "read" | "related" | "quoted" | "dropped" | "unread" | "off" | "instructions";

// The items behind one number of "How this was checked". Opening a row opens the item.
function StageDialog({ answer, stage, onClose, onCite }: { answer: Answer; stage: Stage; onClose: () => void; onCite: (cite: Citation) => void }) {
  const [find, setFind] = useState("");
  const q = find.trim().toLowerCase();
  const hit = (...parts: string[]) => !q || parts.some((part) => part.toLowerCase().includes(q));
  const quoted = new Map<string, { ref: ItemRef; quotes: number }>();
  for (const point of answer.points) for (const c of point.citations) {
    const held = quoted.get(c.item_id);
    if (held) held.quotes += 1;
    else quoted.set(c.item_id, { ref: { item_id: c.item_id, title: c.title, source_label: c.source_label, kind: "", date: c.date }, quotes: 1 });
  }
  const row = (ref: ItemRef, extra?: React.ReactNode, key?: string) => (
    <li key={key ?? ref.item_id}>
      <button type="button" className="stagerow" onClick={() => onCite(refCite(ref))} title="Open this item">
        <b>{ref.title}</b>
        <span className="origin"><em className="tag">{ref.source_label}</em><span>{ref.date ? day(ref.date) : "No date"}</span>{extra}</span>
      </button>
    </li>
  );
  const plainRow = (key: string, main: string, tags: React.ReactNode) => (
    <li key={key}><div className="stagerow still"><b>{main}</b><span className="origin">{tags}</span></div></li>
  );
  let title = "";
  let rows: React.ReactNode[] = [];
  let total = 0;
  if (stage === "read") {
    title = "Items read";
    const list = answer.read_items.filter((r) => hit(r.title, r.source_label));
    total = answer.read_items.length; rows = list.map((r) => row(r));
  } else if (stage === "related") {
    title = "Looked related";
    const list = answer.related_items.filter((r) => hit(r.item.title, r.how));
    total = answer.related_items.length; rows = list.map((r) => row(r.item, <span>{r.how}</span>));
  } else if (stage === "quoted") {
    title = "Notes quoted";
    const list = [...quoted.values()].filter((x) => hit(x.ref.title));
    total = quoted.size; rows = list.map((x) => row(x.ref, <span>{x.quotes} {x.quotes === 1 ? "quote" : "quotes"}</span>));
  } else if (stage === "dropped") {
    title = "Quotes dropped";
    const list = answer.dropped_quotes.filter((d) => hit(d.quote, d.item.title));
    total = answer.dropped_quotes.length;
    rows = list.map((d, i) => (
      <li key={i}>
        <button type="button" className="stagerow" onClick={() => onCite(refCite(d.item))} title="Open the note">
          <span className="quote">“{d.quote.replace(/^[-*•]\s*/, "")}”</span>
          <span className="origin"><span>{d.item.title}</span><span>{d.item.date ? day(d.item.date) : "No date"}</span><em className="tag">{d.why}</em></span>
        </button>
      </li>
    ));
  } else if (stage === "unread") {
    title = "Could not be read";
    const list = answer.unread.filter((u) => hit(u.location, u.why));
    total = answer.unread.length; rows = list.map((u, i) => plainRow(`${i}`, u.location, <em className="tag">{u.why}</em>));
  } else if (stage === "off") {
    title = "Kept out of reach (never opened)";
    const list = answer.off_limits_names.filter((n) => hit(n));
    total = answer.off_limits_names.length; rows = list.map((n, i) => plainRow(`${i}`, n, <em className="tag">Marked off-limits</em>));
  } else {
    title = "Notes that held instructions";
    const list = answer.instruction_notes.filter((r) => hit(r.title));
    total = answer.instruction_notes.length; rows = list.map((r) => row(r, <em className="tag">Treated as plain text</em>));
  }
  return (
    <div className="scrim" role="dialog" aria-modal="true" aria-label={title} onClick={onClose}>
      <div className="dialog wide" onClick={(e) => e.stopPropagation()}>
        <div className="row between">
          <h2>{title} <span className="count">{total}</span></h2>
          <button className="iconbtn" aria-label="Close" onClick={onClose}>×</button>
        </div>
        {total > 10 && <input className="stagefind" aria-label="Find in this list" placeholder="Find" value={find} onChange={(e) => setFind(e.target.value)} />}
        {total === 0 ? <p className="empty">Nothing here.</p> : <ul className="stagelist">{rows}</ul>}
        {q && rows.length === 0 && total > 0 && <p className="empty">No match.</p>}
      </div>
    </div>
  );
}

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
            {point.related ? point.why : point.matched.length > 0 ? <>Shown because it mentions {point.matched.map((word) => <em key={word} className="tag">{word}</em>)}</> : "Shown because the AI judged it to be about your question"}
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
  const [tech, setTech] = useState(false);
  const [stage, setStage] = useState<Stage | null>(null);
  const sure = answer.points.filter((p) => !p.related);
  const maybe = answer.points.filter((p) => p.related);
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
            {sure.map((point, index) => (
              <Finding key={index} point={point} showStatus={answer.show_status} first={index === 0} onCite={onCite} />
            ))}
          </div>
          {maybe.length > 0 && (
            <>
              {/* Kept apart on purpose: the person asked about is not named in these notes. */}
              <p className="maybehead"><b>Possibly related</b><span>The name is not in these notes. Open one to judge it yourself.</span></p>
              <div className="findings maybe">
                {maybe.map((point, index) => (
                  <Finding key={index} point={point} showStatus={false} first={sure.length === 0 && index === 0} onCite={onCite} />
                ))}
              </div>
            </>
          )}
        </>
      )}
      {stage && <StageDialog answer={answer} stage={stage} onClose={() => setStage(null)} onCite={(cite) => { setStage(null); onCite(cite); }} />}
      <p className="looked bits">
        <span>Looked through <b>{answer.coverage.searched}</b> items</span>
        <span className="took">Answered in {took(answer.seconds)}</span>
        <button className="link" onClick={() => setDetails(!details)}>{details ? "Hide" : "How this was checked"}</button>
      </p>
      {details && (
        <div className="checked">
          {/* From everything read down to what is shown: each step keeps fewer items. */}
          <ol className="funnel">
            <li className="click" role="button" tabIndex={0} onClick={() => setStage("read")} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") setStage("read"); }}><b>{answer.coverage.searched}</b><span>items read</span></li>
            <li className="click" role="button" tabIndex={0} onClick={() => setStage("related")} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") setStage("related"); }}><b>{answer.coverage.given_to_model}</b><span>looked related</span></li>
            <li className="click" role="button" tabIndex={0} onClick={() => setStage("quoted")} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") setStage("quoted"); }}><b>{answer.coverage.cited}</b><span>{answer.coverage.cited === 1 ? "note quoted" : "notes quoted"}</span></li>
            <li className="last"><b>{sure.length}</b><span>{sure.length === 1 ? "thing found" : "things found"}{maybe.length > 0 ? `, ${maybe.length} possibly related` : ""}</span></li>
          </ol>
          {answer.model_name && <p className="by"><i className="orb tiny" aria-hidden="true" />Answered by <b>{answer.model_name}</b>, the AI on this Mac</p>}
          <h4>Left out</h4>
          {LEFT.filter(([key]) => (answer.left_out[key] ?? 0) > 0).length === 0 ? (
            <p className="fine">Nothing was left out.</p>
          ) : (
            <ul className="leftout">
              {LEFT.filter(([key]) => (answer.left_out[key] ?? 0) > 0).map(([key, one, many]) => {
                const count = answer.left_out[key] ?? 0;
                const opens = SHOWS[key];
                return <li key={key}><b>{count}</b><span>{count === 1 ? one : many}</span>{opens ? <button type="button" className="link" onClick={() => setStage(opens)}>Show</button> : <i />}</li>;
              })}
            </ul>
          )}
          <button className="link tech" onClick={() => setTech(!tech)}>{tech ? "Hide technical details" : "Technical details"}</button>
          {tech && (
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
  const [prep, setPrep] = useState<Preparing>({ active: false, done: 0, total: 0, what: "" });
  const [stopping, setStopping] = useState(false);  // Stop was pressed; the question is ending

  useEffect(() => {
    if (visible) api.meetings().then(setMeetings).catch(() => setMeetings([]));
  }, [anyOn, visible]);

  // The pictures of a source that was just switched on are read in the background; until
  // that is done the chat stays closed.
  useEffect(() => {
    const look = () => api.preparing().then(setPrep).catch(() => undefined);
    look();
    const timer = setInterval(look, 500);
    return () => clearInterval(timer);
  }, []);

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
      onAnswer(shown !== answer.question && !answer.question.startsWith(shown) ? { ...answer, label: shown } : answer);
      setQuestion("");
    } catch (err) {
      onError(plain(err));
    } finally {
      setAsking("");
      setStopping(false);
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
                <button className="ghost small" disabled={asking !== "" || prep.active} onClick={() => run(`Prepare: ${meeting.title}`, () => api.prepare(meeting.meeting_id))}>Prepare</button>
              </li>
            ))}
          </ul>
        </div>
      )}

      {prep.active && (
        <div className="card prepare" role="status" aria-live="polite">
          <div className="row between"><b>{prep.what || "Reading pictures"}</b><span>{prep.total ? `${prep.done} of ${prep.total}` : "Starting"}</span></div>
          <div className="prepbar" aria-hidden="true"><i style={{ width: `${prep.total ? Math.max(4, Math.round((100 * prep.done) / prep.total)) : 4}%` }} /></div>
        </div>
      )}

      <form className="card row ask" onSubmit={(e) => { e.preventDefault(); if (question.trim()) void ask(question.trim()); }}>
        <input aria-label="Your question" placeholder={prep.active ? "Getting your pictures ready…" : "Ask in your own words"} value={question} maxLength={500} disabled={asking !== "" || prep.active} onChange={(e) => setQuestion(e.target.value)} />
        {asking !== "" ? (
          <button type="button" className="ghost" disabled={stopping} onClick={() => { setStopping(true); api.cancel().catch(() => undefined); }}>{stopping ? "Stopping…" : "Stop"}</button>
        ) : (
          <button className="primary" disabled={!question.trim() || !anyOn || prep.active}>Ask</button>
        )}
      </form>
      {thread.length === 0 && asking === "" && anyOn && (
        <div className="row wrap chips">
          {examples.map((text) => <button key={text} className="chipbtn" disabled={prep.active} onClick={() => ask(text)}>{text}</button>)}
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
            <p className="mine">{answer.label ?? answer.question}</p>
            {answer.label && <p className="searched">Searched as: “{answer.question}”</p>}
            <Found answer={answer} onCite={onCite} />
          </div>
        ))}
      </div>

    </section>
  );
}
