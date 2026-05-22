"use client";

import { useState } from "react";

const COLLAPSE_THRESHOLD = 900;
const PREVIEW_CHARS = 700;

/**
 * A <pre> block that collapses long content behind a toggle.
 * Used for the system prompt and other potentially long verbatim text.
 */
export function CollapsiblePre({ text }: { text: string }) {
  const [open, setOpen] = useState(false);
  const long = text.length > COLLAPSE_THRESHOLD;

  if (!long) {
    return <pre>{text}</pre>;
  }

  return (
    <>
      <pre>{open ? text : text.slice(0, PREVIEW_CHARS).trimEnd() + " …"}</pre>
      <button
        type="button"
        className="toggle"
        style={{ marginTop: 8 }}
        onClick={() => setOpen((v) => !v)}
      >
        {open ? "Show less" : "Show full text"}
      </button>
    </>
  );
}
