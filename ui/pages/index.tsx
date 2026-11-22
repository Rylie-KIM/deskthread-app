import Head from "next/head";
import { useCallback, useEffect, useState } from "react";
import Ask from "../components/Ask";
import Access from "../components/Access";
import Models from "../components/Models";
import { MyData, SessionEnded } from "../components/MyData";
import Viewer from "../components/Viewer";
import { api, readToken, type Answer, type Citation, type MemoryState, type Receipt, type SessionInfo, type SourceState } from "../lib/api";

type Tab = "access" | "ask" | "data" | "model";
const TABS: [Tab, string][] = [["access", "Access"], ["ask", "Ask"], ["data", "My data"], ["model", "AI model"]];

export default function Home() {
  const [tab, setTab] = useState<Tab>("access");
  const [info, setInfo] = useState<SessionInfo | null>(null);
  const [sources, setSources] = useState<SourceState[]>([]);
  const [folder, setFolder] = useState("");
  const [thread, setThread] = useState<Answer[]>([]);  // this session's questions and answers
  const [model, setModel] = useState("");
  const [ai, setAi] = useState<"rest" | "ready" | "use">("rest");
  const [first, setFirst] = useState("");
  const [cite, setCite] = useState<Citation | null>(null);
  const [error, setError] = useState("");
  const [receipt, setReceipt] = useState<Receipt | null>(null);
  const [stopped, setStopped] = useState(false);
  const [confirm, setConfirm] = useState(false);
  // Clear memory and End session show what is being closed, and close when all of it is done.
  const [closing, setClosing] = useState<"" | "clear" | "end">("");
  const [seen, setSeen] = useState<MemoryState | null>(null);  // memory, as it empties
  const [called, setCalled] = useState(false);  // the request itself has come back
  const [state, setState] = useState<"loading" | "ready" | "locked">("loading");

  const refresh = useCallback(async () => setSources(await api.sources()), []);
  const loadModel = useCallback(() => { api.models().then((list) => setModel(list.find((m) => m.selected)?.name ?? "")).catch(() => undefined); }, []);

  // A message closes by itself after a while.
  useEffect(() => {
    if (!error) return;
    const timer = setTimeout(() => setError(""), 9000);
    return () => clearTimeout(timer);
  }, [error]);

  useEffect(() => {
    if (!readToken()) return setState("locked");
    // The address may name the section to open, e.g. "...#t=<token>&tab=data".
    const wanted = new URLSearchParams(window.location.hash.slice(1)).get("tab");
    if (wanted === "access" || wanted === "ask" || wanted === "data" || wanted === "model") setTab(wanted);
    setFirst(new URLSearchParams(window.location.hash.slice(1)).get("q") ?? "");
    api.session().then((session) => { setInfo(session); setState("ready"); loadModel(); return refresh(); }).catch(() => setState("locked"));
  }, [refresh, loadModel]);

  // After End session: keep asking until the address stops answering, then say so.
  useEffect(() => {
    if (!receipt || stopped) return;
    const timer = setInterval(() => { api.session().catch((err) => { if (!("status" in (err as object))) setStopped(true); }); }, 700);
    return () => clearInterval(timer);
  }, [receipt, stopped]);

  useEffect(() => {
    if (!closing) return;
    const timer = setInterval(() => api.memory().then(setSeen).catch(() => undefined), 400);
    return () => clearInterval(timer);
  }, [closing]);

  async function end() {
    setConfirm(false); setSeen(null); setCalled(false); setClosing("end");
    try {
      await api.cancel().catch(() => undefined);  // a running question is stopped first
      const result = await api.endSession();
      setCalled(true); setReceipt(result); setThread([]); setCite(null);
    } catch { setError("End session failed."); setClosing(""); }
  }

  async function clear() {
    setSeen(null); setCalled(false); setClosing("clear");
    try {
      await api.cancel().catch(() => undefined);
      const after = await api.forget();
      setSeen(after); setCalled(true); setThread([]); setCite(null);
      await refresh();
      if (after.model_loaded || after.items_held > 0) setError("Something is still in memory. Use End session to stop everything.");
    } catch { setError("Clear memory did not work."); setClosing(""); }
  }  // the pop-up stays until the user presses OK

  const emptied = seen !== null && seen.items_held === 0;
  const modelGone = receipt ? receipt.model_unloaded : seen !== null && !seen.model_loaded;
  const closingSteps: [string, boolean][] = closing === "clear"
    ? [["What was read leaves memory", emptied], ["The AI model leaves memory", emptied && modelGone], ["This conversation is removed", called]]
    : [["Access is switched off and what was read leaves memory", called || emptied], ["The AI model leaves memory", (called || emptied) && modelGone], ["The receipt is written", called], ["DeskThread stops", stopped]];
  const firstOpen = closingSteps.findIndex(([, done]) => !done);
  const closed = closing === "clear" ? called : stopped;  // everything asked for has happened

  // What the AI is doing right now, for the chip in the bar.
  useEffect(() => {
    if (state !== "ready" || receipt) return;
    const look = () => Promise.all([api.memory(), api.progress()])
      .then(([memory, progress]) => setAi(progress.number >= 2 ? "use" : memory.model_loaded ? "ready" : "rest"))
      .catch(() => undefined);
    look();
    const timer = setInterval(look, 1500);
    return () => clearInterval(timer);
  }, [state, receipt]);

  const anyOn = sources.some((s) => s.status === "on");

  return (
    <>
      <Head>
        <title>DeskThread</title>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <meta name="referrer" content="no-referrer" />
      </Head>
      <div className="scene" aria-hidden="true">
        {/* Flowing glass ribbons, drawn here as vector paths: no image file is loaded. */}
        <svg viewBox="0 0 1440 900" preserveAspectRatio="xMidYMid slice">
          <defs>
            <linearGradient id="ribbonA" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0" stopColor="#ffffff" stopOpacity=".95" />
              <stop offset=".45" stopColor="#9fd2ff" stopOpacity=".5" />
              <stop offset="1" stopColor="#0a17c4" stopOpacity=".3" />
            </linearGradient>
            <linearGradient id="ribbonB" x1="1" y1="0" x2="0" y2="1">
              <stop offset="0" stopColor="#0a17c4" stopOpacity=".34" />
              <stop offset=".5" stopColor="#6fb8ff" stopOpacity=".36" />
              <stop offset="1" stopColor="#ffffff" stopOpacity=".9" />
            </linearGradient>
            <linearGradient id="ribbonC" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" stopColor="#2f9bff" stopOpacity=".34" />
              <stop offset="1" stopColor="#ffffff" stopOpacity=".7" />
            </linearGradient>
            <linearGradient id="edge" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0" stopColor="#ffffff" stopOpacity="1" />
              <stop offset=".5" stopColor="#ffffff" stopOpacity=".25" />
              <stop offset="1" stopColor="#ffffff" stopOpacity=".95" />
            </linearGradient>
            <filter id="glass" x="-10%" y="-10%" width="120%" height="130%">
              <feDropShadow dx="0" dy="18" stdDeviation="16" floodColor="#0a17c4" floodOpacity=".16" />
            </filter>
            <filter id="sheen" x="-5%" y="-5%" width="110%" height="110%"><feGaussianBlur stdDeviation="5" /></filter>
          </defs>
          <g className="ribbons">
            <g filter="url(#glass)" stroke="url(#edge)" strokeWidth="3">
              <path fill="url(#ribbonB)" d="M760 -90 C1080 150 640 400 1000 620 S1500 760 1560 990 L1380 990 C1320 820 900 800 770 560 S840 130 590 -90 Z" />
              <path fill="url(#ribbonA)" d="M-120 110 C300 -70 520 420 900 250 S1480 20 1600 210 L1600 420 C1400 250 1180 520 880 470 S320 150 -120 390 Z" />
              <path fill="url(#ribbonC)" d="M-120 540 C260 380 520 780 900 580 S1380 320 1600 540 L1600 650 C1380 480 1150 830 900 720 S300 540 -120 710 Z" />
            </g>
            {/* light running along the inside of each band */}
            <g fill="none" stroke="#ffffff" strokeOpacity=".7" strokeWidth="14" filter="url(#sheen)">
              <path d="M-120 150 C300 -30 520 450 900 285 S1480 60 1600 250" />
              <path d="M-120 575 C260 415 520 810 900 612 S1380 355 1600 572" />
              <path d="M720 -90 C1040 150 610 400 965 625 S1450 770 1500 990" />
            </g>
          </g>
        </svg>
        <i className="s1" /><i className="s2" /><i className="s3" />
      </div>
      <header className="top">
        <div className="wrap row between">
          <div className="row">
            <span className="mark">DeskThread</span>
            {model && state === "ready" && !receipt && (
              <button className="aichip" onClick={() => setTab("model")} title="Choose the AI model">
                <i className="orb" aria-hidden="true" />
                <span className="ainame"><b>{model}</b><small>AI on this Mac</small></span>
                <em className={`aistate ${ai}`}>{ai === "use" ? "In use" : ai === "ready" ? "Ready" : "Resting"}</em>
              </button>
            )}
          </div>
          {state === "ready" && !receipt && (
            <nav className="row" aria-label="Sections">
              {TABS.map(([key, label]) => (
                <button key={key} className={tab === key ? "tab active" : "tab"} aria-current={tab === key ? "page" : undefined} onClick={() => setTab(key)}>{label}</button>
              ))}
              <button className="ghost" title="Removes what was read, the AI model in memory, the conversation and your access settings; DeskThread stops" onClick={() => setConfirm(true)}>End session</button>
            </nav>
          )}
        </div>
      </header>

      <main className="wrap">
        {state === "loading" && <p className="fine">Starting…</p>}
        {state === "locked" && (
          <section>
            <h1>This page needs the address DeskThread gave you.</h1>
            <p className="sub">Each launch creates a new secret address. Start DeskThread again (double-click DeskThread.command) and use the address it opens. Nothing is reachable without it.</p>
          </section>
        )}
        {receipt && !closing && <SessionEnded receipt={receipt} stopped={stopped} />}
        {state === "ready" && !receipt && (
          <>
            {tab === "access" && (
              <Access sources={sources} folder={folder} refresh={refresh} onError={setError}
                demoFolder={info?.demo_folder ?? ""} onReady={() => setTab("ask")}
                onSources={(next, chosen) => { setSources(next); if (chosen !== undefined) setFolder(chosen); }} />
            )}
            {/* Ask stays alive while another section is open, so a running question keeps running. */}
            {info && <div hidden={tab !== "ask"}><Ask now={info.now} anyOn={anyOn} visible={tab === "ask"} thread={thread} onAnswer={(a) => { setThread((t) => [...t, a]); void refresh(); }} onCite={setCite} onError={setError} first={first} /></div>}
            {tab === "data" && <MyData onError={setError} onClear={clear} onEnd={() => setConfirm(true)} />}
            {tab === "model" && <Models onError={setError} onChange={() => { loadModel(); void refresh(); }} />}
          </>
        )}
      </main>
      {error && (
        <div className="notice" role="alert">
          <span className="dot" />
          <p>{error}</p>
          <button className="iconbtn" aria-label="Close this message" onClick={() => setError("")}>×</button>
        </div>
      )}
      {cite && <Viewer cite={cite} onClose={() => setCite(null)} />}
      {closing && (
        <div className="scrim" role="dialog" aria-modal="true" aria-labelledby="closing-title">
          <div className="dialog">
            <h2 id="closing-title">{closing === "clear" ? (closed ? "Memory cleared" : "Clearing memory") : closed ? "Session ended" : "Ending the session"}</h2>
            <ol className="steps" role="status">
              {closingSteps.map(([name, done], index) => (
                <li key={name} className={done ? "past" : index === firstOpen ? "now" : "next"}><i>{done ? "✓" : index + 1}</i>{name}</li>
              ))}
            </ol>
            <div className="row end">
              <button className="primary" disabled={!closed} onClick={() => setClosing("")}>{closed ? "OK" : "Working…"}</button>
            </div>
          </div>
        </div>
      )}
      {confirm && (
        <div className="scrim" role="dialog" aria-modal="true" aria-labelledby="end-title">
          <div className="dialog">
            <h2 id="end-title">End this session?</h2>
            <p className="lead">DeskThread stops and everything is reset to Off. Your own files and notes stay untouched.</p>
            <div className="row end">
              <button className="ghost" onClick={() => setConfirm(false)}>Cancel</button>
              <button className="primary" onClick={end}>End session</button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
