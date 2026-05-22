"use client";

import { useState } from "react";

const COLLAPSE_THRESHOLD = 600;
const PREVIEW_CHARS = 480;

/**
 * Tool-result body that collapses long content behind a show-more toggle.
 * Short content renders inline with no toggle.
 */
export function CollapsibleText({ text }: { text: string }) {
  const [open, setOpen] = useState(false);
  const long = text.length > COLLAPSE_THRESHOLD;

  if (!long) {
    return <div className="rbody">{text}</div>;
  }

  return (
    <>
      <div className="rbody">
        {open ? text : text.slice(0, PREVIEW_CHARS).trimEnd() + " …"}
      </div>
      <button
        type="button"
        className="toggle"
        onClick={() => setOpen((v) => !v)}
      >
        {open
          ? "Show less"
          : `Show full result (${text.length.toLocaleString()} chars)`}
      </button>
    </>
  );
}
