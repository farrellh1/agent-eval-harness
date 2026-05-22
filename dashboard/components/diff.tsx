/**
 * Renders a unified-diff string with the prototype's green/red line tints.
 *
 * - `+` lines  -> .add   (green tint)
 * - `-` lines  -> .del   (red tint)
 * - `@@` hunks -> .hunk
 * - diff/index/--- /+++ headers -> .meta-line
 * - everything else -> .ctx (context)
 */
export function Diff({ patch }: { patch: string }) {
  const lines = patch.replace(/\n$/, "").split("\n");
  return (
    <div className="diff">
      {lines.map((line, i) => {
        let cls = "ctx";
        if (line.startsWith("@@")) cls = "hunk";
        else if (
          line.startsWith("diff ") ||
          line.startsWith("index ") ||
          line.startsWith("--- ") ||
          line.startsWith("+++ ") ||
          line.startsWith("new file") ||
          line.startsWith("deleted file") ||
          line.startsWith("rename ") ||
          line.startsWith("similarity ")
        )
          cls = "meta-line";
        else if (line.startsWith("+")) cls = "add";
        else if (line.startsWith("-")) cls = "del";
        return (
          <span key={i} className={`ln ${cls}`}>
            {line === "" ? " " : line}
          </span>
        );
      })}
    </div>
  );
}
