import { useEffect, useState } from "react";
import { api, clock, day, macWindow, type AuditLine, type ConnectionCheck, type FolderHash, type MemoryState, type Progress, type Proof, type Receipt } from "../lib/api";

const WORDS: Record<string, string> = { grant: "You allowed reading", revoke: "You stopped", revoke_all: "You stopped", read: "Read", denied: "Refused", folder_added: "You added the folder", folder_removed: "You removed the folder" };

function Details({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <details>
      <summary>{title}</summary>
      {children}
    </details>
  );
}

// The same thing done again and again (a folder is read for every question) is one line
// with how many times; the newest is first. The whole log of the session is kept.
function grouped(lines: AuditLine[]): (AuditLine & { times: number; key: string })[] {
  const out: (AuditLine & { times: number; key: string })[] = [];
  lines.forEach((line, index) => {
    const last = out[out.length - 1];
    if (last && last.action === line.action && last.source_id === line.source_id && last.count === line.count) {
      last.times += 1;
      last.at = line.at;  // the time of the latest one
    } else out.push({ ...line, times: 1, key: `${index}-${line.at}` });
  });
  return out.reverse();
}

const WHAT = { added: "Added", changed: "Changed", removed: "Removed" } as const;

// Which files are different from when the folder was chosen: name, time and owning account.
function Changes({ folder }: { folder: FolderHash }) {
  return (
    <div className="changes">
      <table>
        <thead><tr><th>File</th><th></th><th>When</th><th>Account</th></tr></thead>
        <tbody>
          {folder.changes.map((c) => (
            <tr key={c.name}>
              <td title={c.name}>{c.name}</td>
              <td><em className="tag">{WHAT[c.what]}</em></td>
              <td>{c.when ? `${day(c.when)} ${clock(c.when)}` : ""}</td>
              <td>{c.owner}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {folder.changes_total > folder.changes.length && <p className="fine">The newest {folder.changes.length} of {folder.changes_total} are shown.</p>}
      <p className="fine">DeskThread counts every file it opens for writing, and that count is 0. So these changes were made by you or by another app. macOS keeps the time and the account of a change, not the name of the app, and you and DeskThread use the same account.</p>
    </div>
  );
}

// One line of the receipt; its details open only when asked for.
function Line({ name, value, children }: { name: string; value: string; children?: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <li className={open ? "open" : ""}>
      <div className="line">
        <span>{name}</span>
        <b>{value}</b>
        {children ? <button type="button" className="ghost small" aria-expanded={open} onClick={() => setOpen(!open)}>{open ? "Hide" : "Details"}</button> : <i />}
      </div>
      {open && <div className="more">{children}</div>}
    </li>
  );
}

function Counts({ by }: { by: Record<string, number> }) {
  const rows = Object.entries(by).filter(([, n]) => n > 0).sort((a, b) => b[1] - a[1]);
  if (rows.length === 0) return <p className="fine">Nothing.</p>;
  return <ul className="counts">{rows.map(([name, n]) => <li key={name}><span>{name}</span><b>{n}</b></li>)}</ul>;
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
  const [check, setCheck] = useState<ConnectionCheck | null>(null);
  const [checking, setChecking] = useState(false);
  const [copied, setCopied] = useState(false);

  async function runCheck() {
    setChecking(true);
    try { setCheck(await api.checkConnections()); setCopied(false); } catch { onError("The check did not run."); } finally { setChecking(false); }
  }
  async function copy(text: string) {
    try { await navigator.clipboard.writeText(text); } catch {
      const box = document.createElement("textarea");  // for a window without the clipboard service
      box.value = text; document.body.appendChild(box); box.select(); document.execCommand("copy"); box.remove();
    }
    setCopied(true);
  }

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
  const reading = Object.entries(memory.items_by_source).sort();  // what is On and held, by name

  return (
    <section>
      <h1>Your data stays yours.</h1>
      <div className="facts">
        <div className="card fact">
          <span className={proof.all_local ? "dot" : "dot bad"} />
          <h2>{proof.all_local ? "Nothing was sent to the internet." : "An outside connection was seen."}</h2>
          <p>DeskThread only talks to itself on this Mac.</p>
          <button className="ghost check" disabled={checking} onClick={runCheck}>{checking ? "Checking…" : "Check it now"}</button>
        </div>
        <div className={untouched ? "card fact" : "card fact blink"}>
          <span className="dot" />
          <h2>{proof.folders.length > 0 ? (untouched ? "Your files are untouched." : "A file in your folders changed.") : reading.length > 0 ? "Your apps are only read." : "Nothing is switched on yet."}</h2>
          {proof.folders.length === 0 && reading.length > 0 && <p>DeskThread asks these apps for their content and sends them nothing to save, change or delete.</p>}
          {proof.folders.length === 0 && reading.length > 0 && (
            <ul className="folders">
              {reading.map(([name, count]) => <li key={name}><b>{name}</b><span>{count} items</span><em className="tag">Read only</em></li>)}
            </ul>
          )}
          {proof.folders.length === 0 && reading.length === 0 && <p>Switch a source on in Access. What is read, and that nothing is changed, shows up here.</p>}
          {proof.folders.length > 0 && <p>{untouched ? "Nothing was added, changed or removed since you chose them." : "Not by DeskThread: it cannot write, and it saved 0 files. You or another app changed it."}</p>}
          {proof.folders.length > 0 && (
            <ul className="folders">
              {proof.folders.map((f) => (
                <li key={f.label}><b>{f.label}</b><span>{f.files} files</span><em className={f.unchanged ? "tag" : "tag strong"}>{f.unchanged ? "Same" : "Changed"}</em></li>
              ))}
            </ul>
          )}
          {proof.folders.filter((f) => !f.unchanged).map((f) => (
            <Details key={f.label} title={`What changed in ${f.label}`}><Changes folder={f} /></Details>
          ))}
        </div>
      </div>

      <div className="card live">
        <div className="row between wrap">
          <h2>Session status</h2>
        </div>
        <div className="actions">
          <div className="action">
            <button className="primary" onClick={onClear}>Clear memory</button>
            <Help about="Clear memory">
              <b>Removed</b> the files that were read, the AI model in memory, this conversation.<br />
              <b>Kept</b> your access settings: what you switched on stays on. The list under “What happened” also stays until End session: it holds times and counts only, never what was read.
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
            return <div key={name} className="meter"><span>{name}</span><div><i style={{ width: `${Math.max(3, share)}%` }} /></div><b>{count}</b><em>{share}%</em></div>;
          })}
        </div>
        <div className="card part">
          <h2>Memory used</h2>
          <p className="basis">A full bar would be all {size(mac)} of this Mac. {size(memory.mac_free_mb)} is free right now.</p>
          {memory.processes.map((p) => {
            const share = (100 * p.memory_mb) / mac;
            return <div key={p.pid} className="meter"><span>{p.name.replace("DeskThread backend", "DeskThread").replace("Model server", "AI server").replace("Model runner", "AI model")}</span><div><i style={{ width: `${Math.max(2, Math.min(100, Math.round(share)))}%` }} /></div><b>{size(p.memory_mb)}</b><em>{share < 1 ? "<1" : Math.round(share)}%</em></div>;
          })}
        </div>
      </div>

      <div className="card part">
        <h2>What happened</h2>
        {proof.audit.length === 0 && <p className="blank">Nothing yet. What you allow, stop and read in this session shows up here.</p>}
        <ul className="timeline">
          {grouped(proof.audit).map((line) => (
            <li key={line.key}>
              <span>{clock(line.at)}</span>
              <b>{WORDS[line.action] ?? line.action} {line.source_id === "*" ? "everything" : line.source_id.replace(/^(mac|folder|dir):/, "")}</b>
              {line.action === "read" ? <em>{line.count} items{line.times > 1 ? `, ${line.times} times` : ""}</em> : line.times > 1 ? <em>{line.times} times</em> : <em />}
            </li>
          ))}
        </ul>
      </div>
      {check && (
        <div className="scrim" role="dialog" aria-modal="true" aria-labelledby="check-title">
          <div className="dialog wide">
            <h2 id="check-title">{check.all_local ? "Every connection stays on this Mac." : "A connection leaves this Mac."}</h2>
            <p className="lead">DeskThread asked macOS which connections its own programs have open, at {clock(check.ran_at)}.</p>
            <div className="connbox">
            <table className="conn">
              <thead><tr><th>Program</th><th>Talking to</th><th></th></tr></thead>
              <tbody>
                {check.connections.map((c, i) => <tr key={i}><td>{c.process}</td><td>{c.remote}</td><td><em className={c.local_only ? "tag" : "tag strong"}>{c.local_only ? "This Mac" : "Outside"}</em></td></tr>)}
                {check.connections.length === 0 && <tr><td colSpan={3}>No open connection.</td></tr>}
              </tbody>
            </table>
            </div>
            <h3>How to read it</h3>
            <ul className="read">
              <li><b>127.0.0.1</b> is the address a Mac uses to talk to itself. Nothing sent there leaves the Mac.</li>
              <li><b>listening</b> means a program waits for the DeskThread window on this Mac.</li>
              <li>Any other address would be a connection to the outside, and is marked Outside.</li>
            </ul>
            <h3>What macOS printed</h3>
            <pre className="printout">{check.output || "(nothing)"}</pre>
            <h3>Check it without DeskThread</h3>
            <ol className="read">
              <li>Copy the line below and open Terminal.</li>
              <li>Paste the line into Terminal and run it. DeskThread types nothing there.</li>
            </ol>
            <div className="copyline">
              <code className="cmd">{check.command}</code>
              <button className={copied ? "primary small" : "ghost small"} onClick={() => copy(check.command)}>{copied ? "Copied" : "Copy"}</button>
              {macWindow() && <button className="ghost small" onClick={() => macWindow()?.postMessage("open-terminal")}>Open Terminal</button>}
            </div>
            <div className="pair closing">
              <button className="ghost" disabled={checking} onClick={runCheck}>{checking ? "Checking…" : "Run again"}</button>
              <button className="primary" onClick={() => setCheck(null)}>Close</button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

export function SessionEnded({ receipt, stopped }: { receipt: Receipt; stopped: boolean }) {
  const app = macWindow();
  const changed = receipt.folders.filter((f) => !f.unchanged);
  return (
    <section className="ended">
      <h1>Session ended.</h1>
      <p className="sub">Everything from this session is cleared. Your notes are where they were, and nowhere else.</p>
      <div className="card">
        <ul className="receipt">
          <Line name="Questions asked" value={String(receipt.questions)} />
          <Line name="Items read" value={String(receipt.items_read)}><Counts by={receipt.read_by_source} /></Line>
          <Line name="Items shown to the AI" value={String(receipt.items_given_to_model)}><Counts by={receipt.given_by_source} /></Line>
          <Line name="Cleared from memory" value={receipt.memory_cleared && receipt.model_unloaded ? "Yes" : "No"}>
            <ul className="counts">
              <li><span>What was read</span><b>{receipt.memory_cleared ? "Removed" : "Still held"}</b></li>
              <li><span>AI model</span><b>{receipt.model_unloaded ? "Out of memory" : "Still in memory"}</b></li>
            </ul>
          </Line>
          <Line name="Saved by DeskThread" value={receipt.files_written_by_app === 0 ? "Nothing" : `${receipt.files_written_by_app} files`}>
            <p className="fine">How it is counted: DeskThread counts every file it opens for writing while it runs. The count for this session is {receipt.files_written_by_app}.</p>
            <p className="fine">How to check it yourself: “Your files” below compares your folders with how they were when you chose them, using the Mac's own file times. An AI model you download is the one thing kept on this Mac.</p>
          </Line>
          <Line name="Sent to the internet" value={receipt.all_connections_local ? "Nothing" : "Something"}>
            <p className="fine">How it is counted: the open connections of DeskThread's programs were read from macOS. Every one went to 127.0.0.1, which is this Mac.</p>
            <p className="fine">How to check it yourself: in a session, open My data and “Check it yourself” for a Terminal command, or switch Wi-Fi off and keep working.</p>
          </Line>
          <Line name="Your files" value={receipt.folders.length === 0 ? "No folder" : changed.length === 0 ? "Untouched" : "Changed"}>
            {changed.length === 0 ? <p className="fine">Every folder is the same as when you chose it.</p> : changed.map((f) => (
              <div key={f.label}><p className="fine"><b>{f.label}</b></p><Changes folder={f} /></div>
            ))}
          </Line>
        </ul>
      </div>
      {app ? (
        <div className="pair">
          <button className="primary" disabled={!stopped} onClick={() => app.postMessage("restart")}>{stopped ? "Start a new session" : "Stopping…"}</button>
          <button className="ghost" onClick={() => app.postMessage("quit")}>Quit DeskThread</button>
        </div>
      ) : (
        <p className="fine">{stopped ? "DeskThread has stopped. You can close this tab. Open DeskThread again to start a new session." : "Stopping…"}</p>
      )}
    </section>
  );
}
