import { useEffect, useState } from "react";
import { api, plain, type ModelInfo } from "../lib/api";

// Choose the AI model. One is in use; another can be downloaded once and then switched to.
export default function Models({ onError }: { onError: (message: string) => void }) {
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [busy, setBusy] = useState("");
  const downloading = models.some((m) => m.downloading !== null);

  useEffect(() => {
    api.models().then(setModels).catch(() => setModels([]));
  }, []);
  useEffect(() => {
    if (!downloading) return;
    const timer = setInterval(() => api.models().then(setModels).catch(() => undefined), 1500);
    return () => clearInterval(timer);
  }, [downloading]);

  async function run(tag: string, work: () => Promise<ModelInfo[]>) {
    setBusy(tag);
    try {
      setModels(await work());
    } catch (err) {
      onError(plain(err));
    } finally {
      setBusy("");
    }
  }

  if (models.length === 0) return null;
  return (
    <div className="card list models">
      <h2>AI model</h2>
      <ul className="rows">
        {models.map((m) => (
          <li key={m.tag} className={m.selected ? "rowitem on" : "rowitem"}>
            <span className="tile" aria-hidden="true">{m.name.slice(0, 1)}</span>
            <span className="who">
              <b>{m.name}</b>
              <small>{m.good_for}</small>
            </span>
            {m.selected ? (
              <span className="status done">In use</span>
            ) : m.installed ? (
              <button className="ghost small" disabled={busy !== ""} onClick={() => run(m.tag, () => api.selectModel(m.tag))}>Use</button>
            ) : m.downloading !== null ? (
              <span className="status">Downloading {m.downloading}%</span>
            ) : (
              <button className="ghost small" disabled={busy !== ""} onClick={() => run(m.tag, () => api.downloadModel(m.tag))}>
                {m.failed ? "Try again" : `Download ${m.download_gb} GB`}
              </button>
            )}
          </li>
        ))}
      </ul>
      {downloading && <p className="fine">Downloading uses the internet, this once. Your notes are not part of it.</p>}
    </div>
  );
}
