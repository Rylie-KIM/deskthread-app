import { useEffect, useState } from "react";
import { api, clock, macWindow, type MemoryState, type Progress, type Proof, type Receipt } from "../lib/api";

const WORDS: Record<string, string> = { grant: "You allowed reading", revoke: "You stopped", revoke_all: "You stopped", read: "Read", denied: "Refused" };

function Details({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <details>
      <summary>{title}</summary>
      {children}
    </details>
  );
}

// A small "?" in the corner: the explanation opens only when asked for.
function Help({ about, children }: { about: string; children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <span className="help">
      <button type="button" className="helpbtn" aria-label={`What does ${about} do?`} aria-expanded={open} onClick={() => setOpen(!open)}>?</button>
      {open && <span className="helpbox" role="note">{children}</span>}
    </span>
  );
}

const size = (mb: number) => (mb >= 1024 ? `${(mb / 1024).toFixed(1)} GB` : `${Math.round(mb)} MB`);

export function MyData({ onError, onClear, onEnd }: { onError: (message: string) => void; onClear: () => void; onEnd: () => void }) {
  const [proof, setProof] = useState<Proof | null>(null);
  const [memory, setMemory] = useState<MemoryState | null>(null);
  const [running, setRunning] = useState<Progress | null>(null);

  useEffect(() => {
    const load = () => {
      api.proof().then(setProof).catch(() => onError("This could not be loaded."));
      api.memory().then(setMemory).catch(() => undefined);
      api.progress().then(setRunning).catch(() => undefined);
    };
    load();
    const timer = setInterval(load, 1500);
    return () => clearInterval(timer);
  }, []);

  if (!proof || !memory) return <section><p className="fine">Checking…</p></section>;
  const untouched = proof.folders.every((f) => f.unchanged);
  // Counted from the live list of connections; it is above zero only while a model downloads.
  const outside = proof.connections.filter((c) => !c.local_only).length;
  // The AI is working from the step where it reads pictures to the end of a question.
  const working = (running?.number ?? 0) >= 2;
  const mac = Math.max(1, memory.mac_memory_mb);

  return (
    <section>
      <h1>Your data stays yours.</h1>
      <div className="facts">
        <div className="card fact">
          <span className={proof.all_local ? "dot" : "dot bad"} />
          <h2>{proof.all_local ? "Nothing was sent to the internet." : "An outside connection was seen."}</h2>
          <p>DeskThread only talks to itself on this Mac.</p>
          <Details title="Check it yourself">
            <table>
              <thead><tr><th>Program</th><th>Talking to</th><th></th></tr></thead>
              <tbody>{proof.connections.map((c, i) => <tr key={i}><td>{c.process}</td><td>{c.remote}</td><td>{c.local_only ? "this Mac" : "OUTSIDE"}</td></tr>)}</tbody>
            </table>
            <p className="fine">This list is read live from macOS. To see it without DeskThread, paste this into Terminal: every line must show 127.0.0.1, which is this Mac.</p>
            <code className="cmd">lsof -nP -i -a -p {memory.processes.map((p) => p.pid).join(",")}</code>
            <p className="fine">Or switch Wi-Fi off: DeskThread keeps answering.</p>
          </Details>
        </div>
        <div className="card fact">
          <span className={untouched ? "dot" : "dot warn"} />
          <h2>{proof.folders.length === 0 ? "No folder chosen yet." : untouched ? "Your files are untouched." : "A file in your folders changed."}</h2>
          {proof.folders.length > 0 && <p>{untouched ? "Nothing was added, changed or removed since you chose them." : "Not by DeskThread: it cannot write, and it saved 0 files. You or another app changed it."}</p>}
          {proof.folders.length > 0 && (
            <table className="compare">
              <thead><tr><th>Folder</th><th>Files</th><th>Since you chose it</th></tr></thead>
              <tbody>{proof.folders.map((f) => <tr key={f.label}><td>{f.label}</td><td>{f.files}</td><td><b className={f.unchanged ? "" : "changed"}>{f.unchanged ? "Same" : "Changed"}</b></td></tr>)}</tbody>
            </table>
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
            <button className="primary" onClick={onClear}>Clear memory</button>
            <Help about="Clear memory">
              <b>Removed</b> the files that were read, the AI model in memory, this conversation.<br />
              <b>Kept</b> your access settings: what you switched on stays on.
            </Help>
          </div>
          <div className="action">
            <button className="ghost" onClick={onEnd}>End session</button>
            <Help about="End session">
              <b>Removed</b> the same, and your access settings: everything is reset to Off and DeskThread stops.<br />
              <b>Kept</b> only your own files and notes, untouched.
            </Help>
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
          <div className={working ? "pipe moving" : "pipe"} aria-hidden="true" />
          <div className="node">
            <p className="big">{working ? "In use" : memory.model_loaded ? "Ready" : "Resting"}</p>
            <p>{working ? "AI is answering your question" : memory.model_loaded ? "AI is in memory, waiting" : "AI is not in memory until you ask"}</p>
          </div>
          <div className="pipe cut" aria-hidden="true" />
          <div className={outside > 0 ? "node off alert" : "node off"}>
            <p className="big">{outside}</p>
            <p>{outside === 1 ? "connection" : "connections"} outside this Mac</p>
          </div>
        </div>
      </div>

      <div className="grid2">
        <div className="card part">
          <h2>In memory now, by source</h2>
          <p className="basis">A full bar would be all {memory.items_held} items DeskThread holds.</p>
          {Object.keys(memory.items_by_source).length === 0 && <p className="blank">Nothing is held. Switch a source on in Access.</p>}
          {Object.entries(memory.items_by_source).sort().map(([name, count]) => {
            const share = Math.round((100 * count) / Math.max(1, memory.items_held));
            return <div key={name} className="meter"><span>{name}</span><div><i style={{ width: `${Math.max(3, share)}%` }} /></div><b>{count} · {share}%</b></div>;
          })}
        </div>
        <div className="card part">
          <h2>Memory used</h2>
          <p className="basis">A full bar would be all {size(mac)} of this Mac.</p>
          {memory.processes.map((p) => {
            const share = (100 * p.memory_mb) / mac;
            return <div key={p.pid} className="meter"><span>{p.name.replace("DeskThread backend", "DeskThread").replace("Model server", "AI server").replace("Model runner", "AI model")}</span><div><i style={{ width: `${Math.max(2, Math.min(100, Math.round(share)))}%` }} /></div><b>{size(p.memory_mb)} · {share < 1 ? "<1" : Math.round(share)}%</b></div>;
          })}
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
