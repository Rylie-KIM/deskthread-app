import Head from "next/head";
import { useCallback, useEffect, useState } from "react";
import Ask from "../components/Ask";
import { MemoryPanel, ProofPanel, ReceiptScreen } from "../components/Panels";
import Sources from "../components/Sources";
import Viewer from "../components/Viewer";
import { api, readToken, type Answer, type Citation, type Receipt, type SessionInfo, type SourceState } from "../lib/api";

type Tab = "sources" | "prepare" | "proof" | "memory";
const TABS: [Tab, string][] = [["sources", "Sources"], ["prepare", "Prepare"], ["proof", "Proof"], ["memory", "Memory"]];

export default function Home() {
  const [tab, setTab] = useState<Tab>("sources");
  const [info, setInfo] = useState<SessionInfo | null>(null);
  const [sources, setSources] = useState<SourceState[]>([]);
  const [folder, setFolder] = useState("");
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [cite, setCite] = useState<Citation | null>(null);
  const [error, setError] = useState("");
  const [receipt, setReceipt] = useState<Receipt | null>(null);
  const [stopped, setStopped] = useState(false);
  const [state, setState] = useState<"loading" | "ready" | "locked">("loading");

  const refresh = useCallback(async () => setSources(await api.sources()), []);

  useEffect(() => {
    if (!readToken()) return setState("locked");
    api.session().then((session) => { setInfo(session); setState("ready"); return refresh(); }).catch(() => setState("locked"));
  }, [refresh]);

  // After End session: keep asking until the address stops answering, then say so.
  useEffect(() => {
    if (!receipt || stopped) return;
    const timer = setInterval(() => { api.session().catch((err) => { if (!("status" in (err as object))) setStopped(true); }); }, 700);
    return () => clearInterval(timer);
  }, [receipt, stopped]);

  async function end() {
    try { setReceipt(await api.endSession()); setAnswer(null); setCite(null); } catch { setError("End session failed."); }
  }

  const anyOn = sources.some((s) => s.status === "on");

  return (
    <>
      <Head>
        <title>DeskThread</title>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <meta name="referrer" content="no-referrer" />
      </Head>
      <div className="scene" aria-hidden="true">
        <i className="blob a" /><i className="blob b" /><i className="blob c" />
        <i className="sphere" /><i className="sphere small" /><i className="ring" />
      </div>
      <header className="top">
        <div className="wrap row between">
          <div className="row">
            <span className="mark">DeskThread</span>
            <span className="chip pass">Stays on this laptop</span>
          </div>
          {state === "ready" && !receipt && (
            <nav className="row" aria-label="Sections">
              {TABS.map(([key, label]) => (
                <button key={key} className={tab === key ? "tab active" : "tab"} aria-current={tab === key ? "page" : undefined} onClick={() => setTab(key)}>{label}</button>
              ))}
              <button className="danger" onClick={end}>End session</button>
            </nav>
          )}
        </div>
      </header>

      <main className="wrap">
        {error && <p className="error" role="alert">{error} <button className="link" onClick={() => setError("")}>Dismiss</button></p>}
        {state === "loading" && <p className="fine">Starting…</p>}
        {state === "locked" && (
          <section>
            <h1>This page needs the address DeskThread gave you.</h1>
            <p className="sub">Each launch creates a new secret address. Start DeskThread again (double-click DeskThread.command) and use the address it opens. Nothing is reachable without it.</p>
          </section>
        )}
        {receipt && <ReceiptScreen receipt={receipt} stopped={stopped} />}
        {state === "ready" && !receipt && (
          <>
            {tab === "sources" && (
              <Sources sources={sources} folder={folder} refresh={refresh} onError={setError}
                demoFolder={info?.demo_folder ?? ""} onReady={() => setTab("prepare")}
                onSources={(next, chosen) => { setSources(next); if (chosen !== undefined) { setFolder(chosen); setAnswer(null); } }} />
            )}
            {tab === "prepare" && info && <Ask now={info.now} anyOn={anyOn} answer={answer} onAnswer={(a) => { setAnswer(a); void refresh(); }} onCite={setCite} onError={setError} />}
            {tab === "proof" && <ProofPanel onError={setError} />}
            {tab === "memory" && <MemoryPanel onError={setError} onForgot={() => { setAnswer(null); void refresh(); }} />}
          </>
        )}
      </main>
      {cite && <Viewer cite={cite} onClose={() => setCite(null)} />}
      {info && !receipt && (
        <footer className="wrap fine">
          Model {info.model_tag} · {info.model_digest.slice(0, 12)} · prompt {info.prompt_version} · runs on this laptop · no account, no telemetry
        </footer>
      )}
    </>
  );
}
