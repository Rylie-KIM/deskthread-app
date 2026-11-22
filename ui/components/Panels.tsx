import { useEffect, useState } from "react";
import { api, clock, type MemoryState, type Proof, type Receipt } from "../lib/api";

export function ProofPanel({ onError }: { onError: (message: string) => void }) {
  const [proof, setProof] = useState<Proof | null>(null);
  const load = () => api.proof().then(setProof).catch(() => onError("The proof could not be loaded."));
  useEffect(() => { void load(); }, []);
  if (!proof) return <section><p className="fine">Sampling…</p></section>;
  return (
    <section>
      <p className="kicker">Proof</p>
      <h1>Check it yourself.</h1>
      <p className="sub">Sampled at {clock(proof.sampled_at)} from the Mac's own tools. <button className="link" onClick={load}>Sample again</button></p>

      <div className="grid2">
        <div className="card">
          <h3>Connections <span className={`chip ${proof.all_local ? "pass" : "fail"}`}>{proof.all_local ? "this Mac only" : "outside address found"}</span></h3>
          <table>
            <thead><tr><th>Program</th><th>Connected to</th><th></th></tr></thead>
            <tbody>
              {proof.connections.map((c, i) => (
                <tr key={i}><td>{c.process}</td><td><code>{c.remote}</code></td><td>{c.local_only ? "local" : "OUTSIDE"}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="card">
          <h3>Your files <span className={`chip ${proof.folders.every((f) => f.unchanged) ? "pass" : "warn"}`}>{proof.folders.every((f) => f.unchanged) ? "unchanged" : "changed since you chose it"}</span></h3>
          {proof.folders.length === 0 && <p className="fine">No folder chosen yet.</p>}
          {proof.folders.map((f) => (
            <dl key={f.label}>
              <dt>{f.label} · {f.files} files</dt>
              <dd>when chosen <code>{f.before}</code></dd>
              <dd>now <code>{f.now}</code></dd>
            </dl>
          ))}
          <h3>What DeskThread saved <span className={`chip ${proof.files_written_by_app === 0 ? "pass" : "fail"}`}>{proof.files_written_by_app} files</span></h3>
        </div>
      </div>
      <div className="card">
        <h3>Access log (in memory only, counts and ids)</h3>
        <ul className="trace">
          {proof.audit.slice(-12).map((line, i) => <li key={i}><code>{clock(line.at)}</code> {line.action} · {line.source_id} · {line.count}</li>)}
          {proof.audit.length === 0 && <li>Nothing yet.</li>}
        </ul>
      </div>
    </section>
  );
}

export function MemoryPanel({ onError, onForgot }: { onError: (message: string) => void; onForgot: () => void }) {
  const [memory, setMemory] = useState<MemoryState | null>(null);
  const [busy, setBusy] = useState(false);
  const load = () => api.memory().then(setMemory).catch(() => onError("The memory numbers could not be loaded."));
  useEffect(() => {
    void load();
    const timer = setInterval(load, 4000);
    return () => clearInterval(timer);
  }, []);
  if (!memory) return <section><p className="fine">Reading…</p></section>;
  const total = memory.processes.reduce((sum, p) => sum + p.memory_mb, 0);
  return (
    <section>
      <p className="kicker">Memory</p>
      <h1>What it is holding right now.</h1>
      <div className="grid2">
        <div className="card">
          <p className="big">{memory.items_held}</p>
          <p>items held in memory{memory.image_readings_held > 0 && `, ${memory.image_readings_held} image readings`}</p>
          <ul className="trace">{Object.entries(memory.items_by_source).map(([name, count]) => <li key={name}>{name}: {count}</li>)}</ul>
          <p>Model: <span className={`chip ${memory.model_loaded ? "warn" : "pass"}`}>{memory.model_loaded ? "loaded" : "not loaded"}</span></p>
          <button className="primary" disabled={busy} onClick={async () => { setBusy(true); try { setMemory(await api.forget()); onForgot(); } catch { onError("Forget now failed."); } finally { setBusy(false); } }}>
            {busy ? "Forgetting…" : "Forget now"}
          </button>
        </div>
        <div className="card">
          <h3>Programs <span className="chip">{Math.round(total)} MB</span></h3>
          <table>
            <thead><tr><th>Program</th><th>Process id</th><th>Memory</th></tr></thead>
            <tbody>{memory.processes.map((p) => <tr key={p.pid}><td>{p.name}</td><td><code>{p.pid}</code></td><td>{Math.round(p.memory_mb)} MB</td></tr>)}</tbody>
          </table>
        </div>
      </div>
    </section>
  );
}

export function ReceiptScreen({ receipt, stopped }: { receipt: Receipt; stopped: boolean }) {
  const rows: [string, string][] = [
    ["Questions asked", String(receipt.questions)],
    ["Items read from your sources", String(receipt.items_read)],
    ["Items shown to the model", String(receipt.items_given_to_model)],
    ["Memory cleared", receipt.memory_cleared ? "yes" : "no"],
    ["Model unloaded", receipt.model_unloaded ? "yes" : "no"],
    ["Files DeskThread wrote", String(receipt.files_written_by_app)],
    ["Connections", receipt.all_connections_local ? "this Mac only" : "an outside address was seen"],
  ];
  return (
    <section className="receipt">
      <p className="kicker">Session ended</p>
      <h1>Your knowledge is where it was, and nowhere else.</h1>
      <div className="card">
        <table><tbody>{rows.map(([name, value]) => <tr key={name}><td>{name}</td><td><b>{value}</b></td></tr>)}</tbody></table>
        {receipt.folders.map((f) => (
          <p key={f.label}>{f.label}: {f.files} files, <span className={`chip ${f.unchanged ? "pass" : "warn"}`}>{f.unchanged ? "unchanged since you chose it" : "changed outside DeskThread"}</span></p>
        ))}
        <p><span className={`chip ${stopped ? "pass" : "warn"}`}>{stopped ? "The server has stopped: this address no longer answers" : "Stopping the programs…"}</span></p>
      </div>
    </section>
  );
}
