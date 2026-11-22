import { useEffect, useState } from "react";
import { api, day, type Citation, type ItemView } from "../lib/api";

// Read-only view of one source. Text is rendered as text: React escapes it, so a note that
// contains markup or a script is shown as characters and never runs.
export default function Viewer({ cite, onClose }: { cite: Citation; onClose: () => void }) {
  const [item, setItem] = useState<ItemView | null>(null);
  const [gone, setGone] = useState(false);

  useEffect(() => {
    setItem(null);
    setGone(false);
    api.item(cite.item_id).then(setItem).catch(() => setGone(true));
  }, [cite.item_id]);

  return (
    <div className="scrim" role="dialog" aria-modal="true" aria-label="Source" onClick={onClose}>
      <div className="dialog wide" onClick={(e) => e.stopPropagation()}>
        <div className="row between">
          <p className="fine">Read only</p>
          <button className="iconbtn" aria-label="Close" onClick={onClose}>×</button>
        </div>
        {gone && <p className="empty">Not visible. Its source is Off now, or the file is gone.</p>}
        {item && (
          <>
            <h2>{item.title}</h2>
            <p className="fine">{item.source_label} · {day(item.date)} · {item.location}</p>
            <div className={item.has_image ? "sidebyside" : ""}>
              {item.has_image && <img src={api.imageUrl(item.item_id)} alt="The image this text was read from" />}
              <div>
                {item.read_by_model && <p className="note">Read from the picture by the AI on this Mac. Compare it with the picture.</p>}
                <ol className="lines">
                  {item.units.map((unit) => (
                    <li key={unit.number} className={unit.number === cite.unit ? "hit" : ""}>{unit.text}</li>
                  ))}
                </ol>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
