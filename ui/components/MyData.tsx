import { useEffect, useState } from "react";
import { api, clock, type MemoryState, type Proof, type Receipt } from "../lib/api";

function Details({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <details>
      <summary>{title}</summary>
      {children}
    </details>
  );
}

export function MyData({ onError, onForgot }: { onError: (message: string) => void; onForgot: () => void }) {
  const [proof, setProof] = useState<Proof | null>(null);
  const [memory, setMemory] = useState<MemoryState | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const load = () => {
      api.proof().then(setProof).catch(() => onError("This could not be loaded."));
      api.memory().then(setMemory).catch(() => undefined);
    };
    load();
    const timer = setInterval(load, 4000);
    return () => clearInterval(timer);
  }, []);

  if (!proof || !memory) return <section><p className="fine">Checking…</p></section>;
  const untouched = proof.folders.every((f) => f.unchanged);
  const files = proof.folders.reduce((sum, f) => sum + f.files, 0);

  return (
    <section>
      <h1>Your data stays yours.</h1>
      <div className="facts">
        <div className="card fact">
          <span className={proof.all_local ? "dot" : "dot bad"} />
          <h2>{proof.all_local ? "Nothing was sent to the internet." : "An outside connection was seen."}</h2>
          <p>DeskThread only talks to itself on this Mac.</p>
          <Details title="Details">
            <table>
              <thead><tr><th>Program</th><th>Talking to</th><th></th></tr></thead>
              <tbody>{proof.connections.map((c, i) => <tr key={i}><td>{c.process}</td><td>{c.remote}</td><td>{c.local_only ? "this Mac" : "OUTSIDE"}</td></tr>)}</tbody>
            </table>
          </Details>
        </div>
        <div className="card fact">
          <span className={untouched ? "dot" : "dot warn"} />
          <h2>{proof.folders.length === 0 ? "No folder chosen yet." : untouched ? "Your files are untouched." : "Your files changed since you chose the folder."}</h2>
          {proof.folders.length > 0 && <p>{files} files, the same as when you chose the folder.</p>}
          {proof.folders.length > 0 && (
            <Details title="Details">
              {proof.folders.map((f) => <p key={f.label} className="fine">{f.label}: {f.before} then, {f.now} now</p>)}
            </Details>
          )}
        </div>
        <div className="card fact">
          <span className={proof.files_written_by_app === 0 ? "dot" : "dot bad"} />
          <h2>{proof.files_written_by_app === 0 ? "DeskThread saved nothing." : `DeskThread saved ${proof.files_written_by_app} files.`}</h2>
          <p>No copy of your notes is kept on this Mac.</p>
        </div>
      </div>

      <div className="card holding">
        <div>
          <p className="big">{memory.items_held}</p>
          <p>items it is holding right now · AI: {memory.model_loaded ? "ready" : "resting"}</p>
        </div>
        <button className="primary" disabled={busy} onClick={async () => { setBusy(true); try { setMemory(await api.forget()); onForgot(); } catch { onError("Forget now did not work."); } finally { setBusy(false); } }}>
          {busy ? "Forgetting…" : "Forget now"}
        </button>
      </div>
      <Details title="Details">
        <div className="grid2">
          <div className="card">
            <h3>Programs</h3>
            <table>
              <thead><tr><th>Program</th><th>Id</th><th>Memory</th></tr></thead>
              <tbody>{memory.processes.map((p) => <tr key={p.pid}><td>{p.name}</td><td>{p.pid}</td><td>{Math.round(p.memory_mb)} MB</td></tr>)}</tbody>
            </table>
          </div>
          <div className="card">
            <h3>What you allowed and when</h3>
            <ul className="trace">
              {proof.audit.slice(-10).map((line, i) => <li key={i}>{clock(line.at)} · {line.action} · {line.source_id.replace(/^(mac|folder):/, "")} · {line.count}</li>)}
              {proof.audit.length === 0 && <li>Nothing yet.</li>}
            </ul>
          </div>
        </div>
      </Details>
    </section>
  );
}

// In the Mac window a small bridge lets the page ask the app to start again or to quit.
type Bridge = { postMessage: (message: string) => void };
function bridge(): Bridge | null {
  const w = window as unknown as { webkit?: { messageHandlers?: { deskthread?: Bridge } } };
  return w.webkit?.messageHandlers?.deskthread ?? null;
}

export function SessionEnded({ receipt, stopped }: { receipt: Receipt; stopped: boolean }) {
  const app = typeof window === "undefined" ? null : bridge();
  const rows: [string, string][] = [
    ["Questions asked", String(receipt.questions)],
    ["Items read", String(receipt.items_read)],
    ["Items shown to the AI", String(receipt.items_given_to_model)],
    ["Cleared from memory", receipt.memory_cleared ? "Yes" : "No"],
    ["Saved by DeskThread", receipt.files_written_by_app === 0 ? "Nothing" : `${receipt.files_written_by_app} files`],
    ["Sent to the internet", receipt.all_connections_local ? "Nothing" : "Something"],
    ["Your files", receipt.folders.every((f) => f.unchanged) ? "Untouched" : "Changed"],
  ];
  return (
    <section className="ended">
      <h1>Session ended.</h1>
      <p className="sub">Everything from this session is cleared. Your notes are where they were, and nowhere else.</p>
      <div className="card">
        <table><tbody>{rows.map(([name, value]) => <tr key={name}><td>{name}</td><td><b>{value}</b></td></tr>)}</tbody></table>
      </div>
      {app ? (
        <div className="row">
          <button className="primary" disabled={!stopped} onClick={() => app.postMessage("restart")}>{stopped ? "Start a new session" : "Stopping…"}</button>
          <button className="ghost" onClick={() => app.postMessage("quit")}>Quit DeskThread</button>
        </div>
      ) : (
        <p className="fine">{stopped ? "DeskThread has stopped. You can close this tab. Open DeskThread again to start a new session." : "Stopping…"}</p>
      )}
    </section>
  );
}
