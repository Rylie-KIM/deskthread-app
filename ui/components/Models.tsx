import { useEffect, useState } from "react";
import { api, plain, type ModelInfo } from "../lib/api";

// One short line per model, and how quick it is. Kept here so the list reads at a glance.
const LINE: Record<string, [string, number]> = {
  "gemma4:e4b": ["For careful answers and pictures", 2],
  "gemma4:e2b": ["For quick answers on any Mac", 3],
  "phi4-mini:latest": ["For the fastest text-only answers", 3],
};

const Mark = ({ yes }: { yes: boolean }) => <span className={yes ? "mark yes" : "mark no"} aria-label={yes ? "yes" : "no"}>{yes ? "✓" : "–"}</span>;
const Speed = ({ level }: { level: number }) => (
  <span className="speed" aria-label={`speed ${level} of 3`}>{[1, 2, 3].map((n) => <i key={n} className={n <= level ? "on" : ""} />)}</span>
);

export default function Models({ onError, onChange }: { onError: (message: string) => void; onChange: () => void }) {
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
      onChange();
    } catch (err) {
      onError(plain(err));
    } finally {
      setBusy("");
    }
  }

  return (
    <section>
      <h1>Choose the AI that reads for you.</h1>
      <p className="sub">Every model runs on this Mac. Pick one for what you need.</p>
      <div className="card modeltable">
        <table>
          <thead><tr><th>Model</th><th>Text</th><th>Pictures</th><th>Speed</th><th>Size</th><th></th></tr></thead>
          <tbody>
            {models.map((m) => (
              <tr key={m.tag} className={m.selected ? "current" : ""}>
                <td><b>{m.name}</b><small>{LINE[m.tag]?.[0] ?? m.good_for} · {m.maker}</small></td>
                <td><Mark yes /></td>
                <td><Mark yes={m.reads_pictures} /></td>
                <td><Speed level={LINE[m.tag]?.[1] ?? 2} /></td>
                <td>{m.download_gb} GB</td>
                <td className="act">
                  {m.selected ? (
                    <span className="status done">In use</span>
                  ) : m.installed ? (
                    <button className="ghost small" disabled={busy !== ""} onClick={() => run(m.tag, () => api.selectModel(m.tag))}>Use</button>
                  ) : m.downloading !== null ? (
                    <span className="dl"><span className="track"><i style={{ width: `${m.downloading}%` }} /></span>{m.downloading}%</span>
                  ) : (
                    <button className="ghost small" disabled={busy !== ""} onClick={() => run(m.tag, () => api.downloadModel(m.tag))}>{m.failed ? "Try again" : "Download"}</button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {downloading && <p className="fine">Downloading uses the internet, this once. Your notes are not part of it.</p>}
    </section>
  );
}
