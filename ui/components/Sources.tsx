import { useState } from "react";
import { api, ApiError, type PermissionRequest, type SourceState } from "../lib/api";

const OS_TEXT: Record<string, string> = {
  not_needed: "Files you chose: no extra macOS permission needed",
  granted: "macOS permission: granted",
  missing: "macOS permission: missing. Open System Settings, Privacy and Security, Automation",
  unknown: "macOS will ask you once, separately, the first time",
};

interface Props {
  sources: SourceState[];
  folder: string;
  onSources: (sources: SourceState[], folder?: string) => void;
  onError: (message: string) => void;
  refresh: () => Promise<void>;
  demoFolder: string;
  onReady: () => void;
}

export default function Sources({ sources, folder, onSources, onError, refresh, demoFolder, onReady }: Props) {
  const [path, setPath] = useState("");
  const [busy, setBusy] = useState("");
  const [request, setRequest] = useState<PermissionRequest | null>(null);
  const [ticked, setTicked] = useState<string[]>([]);

  async function run(label: string, work: () => Promise<void>) {
    setBusy(label);
    try {
      await work();
    } catch (err) {
      onError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setBusy("");
    }
  }

  const choose = (chosen: string) =>
    run("folder", async () => onSources(await api.chooseFolder(chosen), chosen || "the folder you picked"));

  const open = (source: SourceState) =>
    run(source.source_id, async () => {
      const asked = await api.request(source.source_id);
      setTicked(asked.scopes.filter((s) => !/personal/i.test(s.scope_id)).map((s) => s.scope_id));
      setRequest(asked);
    });

  const allow = () =>
    run("allow", async () => {
      if (!request) return;
      await api.grant(request.source_id, ticked);
      setRequest(null);
      await refresh();
    });

  const stop = (source: SourceState) =>
    run(source.source_id, async () => {
      await api.revoke(source.source_id);
      await refresh();
    });

  // Work profile: every work source On; a calendar or folder called "personal" stays Off.
  const workProfile = () =>
    run("profile", async () => {
      for (const source of sources.filter((s) => s.status === "off")) {
        const asked = await api.request(source.source_id);
        const scopes = asked.scopes.filter((s) => !/personal/i.test(s.scope_id)).map((s) => s.scope_id);
        if (scopes.length) await api.grant(source.source_id, scopes);
      }
      await refresh();
    });

  // One click: the invented demo laptop, the Work profile, then straight to Prepare.
  const tryDemo = () =>
    run("demo", async () => {
      const found = await api.chooseFolder(demoFolder);
      for (const source of found.filter((s) => s.status === "off")) {
        const asked = await api.request(source.source_id);
        const scopes = asked.scopes.filter((s) => !/personal/i.test(s.scope_id)).map((s) => s.scope_id);
        if (scopes.length) await api.grant(source.source_id, scopes);
      }
      onSources(await api.sources(), "the demo laptop (invented data)");
      onReady();
    });

  const on = sources.filter((s) => s.status === "on");
  const held = on.reduce((sum, s) => sum + s.items_in_memory, 0);

  return (
    <section>
      <p className="kicker">Sources</p>
      <h1>You choose what it can see.</h1>
      <p className="sub">Everything starts Off. Allow a source with one click, take it back with one click. Taking it back works at once.</p>

      <div className="card row wrap">
        <button className="primary" disabled={busy !== ""} onClick={() => choose("")}>
          {busy === "folder" ? "Waiting for your choice…" : "Choose folder…"}
        </button>
        <form className="row grow" onSubmit={(e) => { e.preventDefault(); if (path.trim()) void choose(path.trim()); }}>
          <input aria-label="Folder path" placeholder="or type a folder path, e.g. ~/Documents/Work" value={path} onChange={(e) => setPath(e.target.value)} />
          <button className="ghost" disabled={busy !== "" || !path.trim()}>Use this path</button>
        </form>
      </div>

      {sources.length === 0 ? (
        <div className="start">
          {demoFolder && (
            <button className="startcard" disabled={busy !== ""} onClick={tryDemo}>
              <span className="kicker">Fastest way to see it</span>
              <b>{busy === "demo" ? "Setting up…" : "Try it with the demo laptop"}</b>
              <span>65 invented files of a manager called Seoyeon. One click switches on the work sources and takes you to tomorrow's one-to-one.</span>
            </button>
          )}
          <button className="startcard plain" disabled={busy !== ""} onClick={() => choose("")}>
            <span className="kicker">Your own files</span>
            <b>Choose my folder…</b>
            <span>Pick a folder. Everything in it starts Off: you allow each source yourself, and you can stop it at any time.</span>
          </button>
        </div>
      ) : (
        <>
          <div className="row wrap between bar">
            <p className="seeing">
              Reading from <b>{folder}</b>. <b>{on.length}</b> of {sources.filter((s) => s.status !== "locked").length} sources On, <b>{held}</b> items in memory.
            </p>
            <div className="row">
              <button className="ghost" disabled={busy !== ""} onClick={workProfile}>{busy === "profile" ? "Switching on…" : "Work profile"}</button>
              <button className="danger" disabled={busy !== "" || on.length === 0} onClick={() => run("all", async () => onSources(await api.revokeAll()))}>Stop all</button>
            </div>
          </div>
          <ul className="sources">
            {sources.map((source) => (
              <li key={source.source_id} className={`source ${source.status}`}>
                <div>
                  <b>{source.label}</b>
                  <span className={`chip ${source.status}`}>{source.status === "locked" ? "Detected, locked off" : source.status === "on" ? "On" : "Off"}</span>
                  <p>
                    {source.status === "locked"
                      ? "A private app. DeskThread cannot read it and it cannot be switched on."
                      : source.status === "on"
                        ? `${source.items_in_memory} items in memory · ${source.allowed_scope_ids.length} part${source.allowed_scope_ids.length === 1 ? "" : "s"} allowed`
                        : "Not read."}
                  </p>
                </div>
                {source.status === "off" && <button className="ghost" disabled={busy !== ""} onClick={() => open(source)}>Turn on…</button>}
                {source.status === "on" && <button className="danger" disabled={busy !== ""} onClick={() => stop(source)}>Stop access</button>}
              </li>
            ))}
          </ul>
        </>
      )}

      {request && (
        <div className="scrim" role="dialog" aria-modal="true" aria-labelledby="ask-title">
          <div className="dialog">
            <p className="kicker">Permission request</p>
            <h2 id="ask-title">Let DeskThread read {request.label}?</h2>
            <p>{request.what_will_be_read}</p>
            <fieldset>
              <legend>What exactly</legend>
              {request.scopes.map((scope) => (
                <label key={scope.scope_id} className="tick">
                  <input
                    type="checkbox"
                    checked={ticked.includes(scope.scope_id)}
                    onChange={(e) => setTicked(e.target.checked ? [...ticked, scope.scope_id] : ticked.filter((s) => s !== scope.scope_id))}
                  />
                  <span>{scope.label}</span>
                  <small>{scope.item_count ?? "?"} files</small>
                </label>
              ))}
            </fieldset>
            <p className="fine">{OS_TEXT[request.os_permission]}. It stays on this laptop, it is held in memory only, and you can stop access at any time.</p>
            <div className="row end">
              <button className="ghost" onClick={() => setRequest(null)}>Not now</button>
              <button className="primary" disabled={ticked.length === 0 || busy !== ""} onClick={allow}>Allow for this session</button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
