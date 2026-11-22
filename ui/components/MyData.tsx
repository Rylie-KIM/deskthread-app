import { useEffect, useState } from "react";
import { api, clock, macWindow, type MemoryState, type Proof, type Receipt } from "../lib/api";

const WORDS: Record<string, string> = { grant: "You allowed reading", revoke: "You stopped", revoke_all: "You stopped", read: "Read", denied: "Refused" };

function Details({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <details>
      <summary>{title}</summary>
      {children}
    </details>
  );
}

export function MyData({ onError, onForgot, onEnd }: { onError: (message: string) => void; onForgot: () => void; onEnd: () => void }) {
  const [proof, setProof] = useState<Proof | null>(null);
  const [memory, setMemory] = useState<MemoryState | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const load = () => {
      api.proof().then(setProof).catch(() => onError("This could not be loaded."));
      api.memory().then(setMemory).catch(() => undefined);
    };
    load();
    const timer = setInterval(load, 2000);
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

      <div className="card live">
        <div className="row between wrap">
          <h2>Right now</h2>
        </div>
        <div className="actions">
          <div className="action">
            <button className="primary" disabled={busy} onClick={async () => { setBusy(true); try { setMemory(await api.forget()); onForgot(); } catch { onError("Clear memory did not work."); } finally { setBusy(false); } }}>
              {busy ? "Clearing…" : "Clear memory"}
            </button>
            <ul className="effects">
              <li><b>Removed</b> the files that were read, the AI model in memory, this conversation</li>
              <li><b>Kept</b> your access settings: what you switched on stays on</li>
            </ul>
          </div>
          <div className="action">
            <button className="ghost" onClick={onEnd}>End session</button>
            <ul className="effects">
              <li><b>Removed</b> the same, and your access settings: everything is reset to Off, DeskThread stops</li>
              <li><b>Kept</b> only your own files and notes, untouched</li>
            </ul>
          </div>
        </div>
        {/* What is where, live: your sources -> DeskThread -> the AI. Nothing leads off this Mac. */}
        <div className="flow">
          <div className="node">
            <p className="big">{Object.keys(memory.items_by_source).length}</p>
            <p>sources being read</p>
          </div>
          <div className={memory.items_held > 0 ? "pipe moving" : "pipe"} aria-hidden="true" />
          <div className="node main">
            <p className="big">{memory.items_held}</p>
            <p>items held by DeskThread</p>
          </div>
          <div className={memory.model_loaded ? "pipe moving" : "pipe"} aria-hidden="true" />
          <div className="node">
            <p className="big">{memory.model_loaded ? "On" : "Off"}</p>
            <p>AI on this Mac</p>
          </div>
          <div className="pipe cut" aria-hidden="true" />
          <div className="node off">
            <p className="big">0</p>
            <p>sent to the internet</p>
          </div>
        </div>
      </div>

      <div className="grid2">
        <div className="card part">
          <h2>Held from each source</h2>
          {Object.keys(memory.items_by_source).length === 0 && <p className="blank">Nothing is held. Switch a source on in Access.</p>}
          {Object.entries(memory.items_by_source).sort().map(([name, count]) => (
            <div key={name} className="meter"><span>{name}</span><div><i style={{ width: `${Math.max(4, Math.round((100 * count) / Math.max(1, memory.items_held)))}%` }} /></div><b>{count}</b></div>
          ))}
        </div>
        <div className="card part">
          <h2>Memory used</h2>
          {memory.processes.map((p) => (
            <div key={p.pid} className="meter"><span>{p.name.replace("DeskThread backend", "DeskThread").replace("Model server", "AI server").replace("Model runner", "AI model")}</span><div><i style={{ width: `${Math.max(3, Math.min(100, Math.round(p.memory_mb / 100)))}%` }} /></div><b>{p.memory_mb >= 1024 ? `${(p.memory_mb / 1024).toFixed(1)} GB` : `${Math.round(p.memory_mb)} MB`}</b></div>
          ))}
        </div>
      </div>

      <div className="card part">
        <h2>What happened</h2>
        {proof.audit.length === 0 && <p className="blank">Nothing yet. What you allow, stop and read in this session shows up here.</p>}
        <ul className="timeline">
          {proof.audit.slice(-8).reverse().map((line, i) => (
            <li key={i}><span>{clock(line.at)}</span>{WORDS[line.action] ?? line.action} {line.source_id === "*" ? "everything" : line.source_id.replace(/^(mac|folder):/, "")}{line.action === "read" ? ` · ${line.count} items` : ""}</li>
          ))}
        </ul>
      </div>
    </section>
  );
}

export function SessionEnded({ receipt, stopped }: { receipt: Receipt; stopped: boolean }) {
  const app = macWindow();
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
