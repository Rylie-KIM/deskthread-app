import { useState } from "react";

// A small "?" in the corner: the explanation opens only when asked for.
export default function Help({ about, children }: { about: string; children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <span className="help">
      <button type="button" className="helpbtn" aria-label={`What does ${about} do?`} aria-expanded={open} onClick={() => setOpen(!open)}>?</button>
      {open && <span className="helpbox" role="note">{children}</span>}
    </span>
  );
}
