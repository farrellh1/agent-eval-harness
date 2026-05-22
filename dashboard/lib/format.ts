/** Presentation helpers shared by the leaderboard and task-detail pages. */

/**
 * Format a 0..1 score the way the prototype does: a perfect score reads
 * "1.00"; a score that needs three decimals to be distinct keeps three
 * (e.g. 0.999); everything else rounds to two.
 */
export function formatScore(score: number): string {
  if (score >= 1) return "1.00";
  const two = score.toFixed(2);
  // Keep a third decimal only when rounding to 2dp would hide detail.
  if (Number(two) !== Number(score.toFixed(3))) {
    return score.toFixed(3);
  }
  return two;
}

/** Bar tint class matching the prototype: plain green / warn / bad. */
export function barClass(score: number): string {
  if (score < 0.85) return "bar bad";
  if (score < 0.95) return "bar warn";
  return "bar";
}

/** Integer with thousands separators. */
export function num(value: number): string {
  return Math.round(value).toLocaleString("en-US");
}
