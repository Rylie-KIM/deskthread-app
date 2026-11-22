import { useEffect, useState } from "react";
import { api, day, type Citation, type ItemView } from "../lib/api";

// The place of an item without repeating its source: "Calendar: Work" becomes "Work".
const place = (item: ItemView) => {
  const rest = item.location.replace(new RegExp(`^${item.source_label}:\\s*`), "");
  return rest === item.source_label ? "" : rest;  // a folder called like its app says nothing new
};

// Read-only view of one source. Text is rendered as text: React escapes it, so a note that
// contains markup or a script is shown as characters and never runs.
export default function Viewer({ cite, onClose }: { cite: Citation; onClose: () => void }) {
  const [item, setItem] = useState<ItemView | null>(null);
  const [gone, setGone] = useState(false);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    setItem(null);
    setGone(false);
    api.item(cite.item_id).then(setItem).catch(() => setGone(true));
  }, [cite.item_id]);

  return (
    <div className="scrim" role="dialog" aria-modal="true" aria-label="Source" onClick={onClose}>
      <div className="dialog wide" onClick={(e) => e.stopPropagation()}>
        <div className="row end">
          <button className="iconbtn" aria-label="Close" onClick={onClose}>×</button>
        </div>
        {gone && <p className="empty">Not visible. Its source is Off now, or the file is gone.</p>}
        {item && (
          <>
            <h2>{item.title}</h2>
            {/* One long glass bar: source, date, place. The whole bar leads to the original. */}
            {item.origin !== "" ? (
              <button className="origin-bar" title={item.origin === "file" ? "Show in Finder" : `Show in ${item.source_label}`} onClick={() => { api.reveal(item.item_id).catch(() => setFailed(true)); }}>
                <b>{item.source_label}</b>
                <span className="when">{day(item.date)}</span>
                <span className="where">{place(item)}</span>
                <i aria-hidden="true">↗</i>
              </button>
            ) : (
              <div className="origin-bar still">
                <b>{item.source_label}</b>
                <span className="when">{day(item.date)}</span>
                <span className="where">{place(item)}</span>
              </div>
            )}
            {failed && <p className="fine">It could not be shown.</p>}
            <div className={item.has_image ? "sidebyside" : ""}>
              {item.has_image && <img src={api.imageUrl(item.item_id)} alt="The image this text was read from" />}
              <div>
                {item.read_by_model && <p className="note">Read from the picture on this Mac. Compare it with the picture.</p>}
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
