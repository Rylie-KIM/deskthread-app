import { useEffect, useState } from "react";
import { api, ApiError, macWindow, plain, type FolderInfo, type PermissionRequest, type SourceState } from "../lib/api";

// Anything personal stays Off when "all work sources" is used. It can still be switched on by hand.
const NOT_WORK = /personal|whatsapp|kakaotalk|line|discord|imessage|messages|telegram|signal/i;

const OS_NOTE: Record<string, string> = {
  not_needed: "",
  granted: "",
  unknown: "macOS will also ask you once for this app.",
  missing: "macOS has not allowed this app yet. Open System Settings, Privacy & Security, Automation.",
};

interface Props {
  sources: SourceState[];
  folder: string;
  demoFolder: string;
  onSources: (sources: SourceState[], folder?: string) => void;
  onError: (message: string) => void;
  refresh: () => Promise<void>;
  onReady: () => void;
}

export default function Access({ sources, folder, demoFolder, onSources, onError, refresh, onReady }: Props) {
  const [path, setPath] = useState("");
  const [busy, setBusy] = useState("");
  const [request, setRequest] = useState<PermissionRequest | null>(null);
  const [ticked, setTicked] = useState<string[]>([]);
  const [folders, setFolders] = useState<FolderInfo[]>([]);

  // The folders in use, kept in step with the sources.
  useEffect(() => {
    api.folders().then(setFolders).catch(() => setFolders([]));
  }, [sources]);

  async function run(label: string, work: () => Promise<void>) {
    setBusy(label);
    try {
      await work();
    } catch (err) {
      if (!(err instanceof ApiError && err.message === "no folder was chosen")) onError(plain(err));
    } finally {
      setBusy("");
    }
  }

  const use = (chosen: string) =>
    run("folder", async () => onSources(await api.chooseFolder(chosen), chosen ? chosen.split("/").filter(Boolean).pop() ?? chosen : "your folder"));

  // In the Mac window the window itself shows the folder panel and hands back the path.
  const choose = (chosen: string) => {
    const app = macWindow();
    if (chosen || !app) return use(chosen);
    (window as unknown as { deskthreadFolder?: (path: string) => void }).deskthreadFolder = (picked) => { if (picked) void use(picked); };
    app.postMessage("choose-folder");
    return Promise.resolve();
  };

  // A switch: Off -> ask first (read permission only); On -> stop at once.
  const flip = (source: SourceState) =>
    run(source.source_id, async () => {
      if (source.status === "on") {
        await api.revoke(source.source_id);
        await refresh();
        return;
      }
      const asked = await api.request(source.source_id);
      setTicked(asked.scopes.filter((s) => !NOT_WORK.test(s.scope_id)).map((s) => s.scope_id));
      setRequest(asked);
    });

  const allow = () =>
    run("allow", async () => {
      if (!request) return;
      await api.grant(request.source_id, ticked);
      setRequest(null);
      await refresh();
    });

  const allWork = (list: SourceState[]) =>
    run("work", async () => {
      for (const source of list.filter((s) => s.status === "off" && s.source_id.startsWith("folder:"))) {
        const asked = await api.request(source.source_id);
        const scopes = asked.scopes.filter((s) => !NOT_WORK.test(s.scope_id)).map((s) => s.scope_id);
        if (scopes.length) await api.grant(source.source_id, scopes);
      }
      await refresh();
    });

  const tryDemo = () =>
    run("demo", async () => {
      const found = await api.chooseFolder(demoFolder);
      for (const source of found.filter((s) => s.status === "off" && s.source_id.startsWith("folder:"))) {
        const asked = await api.request(source.source_id);
        const scopes = asked.scopes.filter((s) => !NOT_WORK.test(s.scope_id)).map((s) => s.scope_id);
        if (scopes.length) await api.grant(source.source_id, scopes);
      }
      onSources(await api.sources(), "the demo laptop");
      onReady();
    });

  const byName = (a: SourceState, b: SourceState) => a.label.localeCompare(b.label);
  const apps = sources.filter((s) => s.source_id.startsWith("mac:")).sort(byName);
  const files = sources.filter((s) => s.source_id.startsWith("folder:")).sort(byName);
  const on = sources.filter((s) => s.status === "on");
  const held = on.reduce((sum, s) => sum + s.items_in_memory, 0);

  const row = (source: SourceState) => (
    <li key={source.source_id} className={source.status === "on" ? "rowitem on" : "rowitem"}>
      <span className="tile" aria-hidden="true">{source.label.slice(0, 1)}</span>
      <span className="who">
        <b>{source.label}</b>
        <small>{busy === source.source_id ? "Working…" : source.status === "on" ? `Reading · ${source.items_in_memory} items` : "Off"}</small>
      </span>
      <button
        role="switch"
        aria-checked={source.status === "on"}
        aria-label={`Read ${source.label}`}
        className={source.status === "on" ? "switch on" : "switch"}
        disabled={busy !== ""}
        onClick={() => flip(source)}
      >
        <i />
      </button>
    </li>
  );

  return (
    <section>
      <h1>Choose what DeskThread can read.</h1>
      <p className="sub">Everything is Off until you switch it on. Switching on gives read permission only.</p>

      {files.length === 0 && demoFolder && (
        <div className="card offer">
          <span className="tile" aria-hidden="true">▶</span>
          <span className="who">
            <b>New here? Try it with the demo laptop</b>
            <small>Invented notes of a manager. One click, nothing of yours is read.</small>
          </span>
          <button className="primary" disabled={busy !== ""} onClick={tryDemo}>{busy === "demo" ? "Setting up…" : "Try the demo"}</button>
        </div>
      )}

      <div className="row between wrap bar">
        <p className="seeing"><b>{on.length}</b> on · <b>{held}</b> items being read</p>
        <div className="row">
          {files.length > 0 && <button className="ghost" disabled={busy !== ""} onClick={() => allWork(sources)}>{busy === "work" ? "Switching on…" : "Turn on all work sources"}</button>}
          <button className="ghost" disabled={busy !== "" || on.length === 0} onClick={() => run("all", async () => onSources(await api.revokeAll()))}>Turn everything off</button>
        </div>
      </div>

      {apps.length > 0 && (
        <div className="card list">
          <h2>Apps on this Mac</h2>
          <ul className="rows">{apps.map(row)}</ul>
        </div>
      )}

      <div className="card list">
        <h2>Folders</h2>
        {folders.length > 0 && (
          <ul className="rows">
            {folders.map((f) => (
              <li key={f.path} className="rowitem">
                <span className="tile" aria-hidden="true">▤</span>
                <span className="who"><b>{f.name}</b><small title={f.path}>{f.path.replace(/^\/Users\/[^/]+/, "~")}</small></span>
                <button className="iconbtn" aria-label={`Remove ${f.name}`} title="Stop using this folder" disabled={busy !== ""} onClick={() => run("remove", async () => onSources(await api.removeFolder(f.path)))}>×</button>
              </li>
            ))}
          </ul>
        )}
        <form className="row wrap pick" onSubmit={(e) => { e.preventDefault(); if (path.trim()) { void choose(path.trim()); setPath(""); } }}>
          <button type="button" className={folders.length ? "ghost" : "primary"} disabled={busy !== ""} onClick={() => choose("")}>{busy === "folder" ? "Waiting for your choice…" : folders.length ? "Add another folder…" : "Choose folder…"}</button>
          <input aria-label="Folder path" placeholder="or type a folder path" value={path} onChange={(e) => setPath(e.target.value)} />
          <button className="ghost" disabled={busy !== "" || !path.trim()}>Use</button>
        </form>
        {files.length > 0 && <h2 className="in">In these folders</h2>}
        {files.length > 0 && <ul className="rows">{files.map(row)}</ul>}
      </div>

      {request && (
        <div className="scrim" role="dialog" aria-modal="true" aria-labelledby="ask-title">
          <div className="dialog">
            <h2 id="ask-title">Allow DeskThread to read {request.label}?</h2>
            <p className="readonly"><b>Read only.</b> DeskThread cannot change, send or delete anything.</p>
            <fieldset>
              <legend>Read from</legend>
              {request.scopes.map((scope) => (
                <label key={scope.scope_id} className="tick">
                  <input
                    type="checkbox"
                    checked={ticked.includes(scope.scope_id)}
                    onChange={(e) => setTicked(e.target.checked ? [...ticked, scope.scope_id] : ticked.filter((s) => s !== scope.scope_id))}
                  />
                  <span>{scope.label}</span>
                  <small>{scope.item_count === null ? "" : `${scope.item_count} items`}</small>
                </label>
              ))}
            </fieldset>
            {OS_NOTE[request.os_permission] && <p className="fine">{OS_NOTE[request.os_permission]}</p>}
            <div className="row end">
              <button className="ghost" onClick={() => setRequest(null)}>Not now</button>
              <button className="primary" disabled={ticked.length === 0 || busy !== ""} onClick={allow}>{busy === "allow" ? "Reading…" : "Allow reading"}</button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
