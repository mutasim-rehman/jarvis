export function formatRelativeTime(timestampMs: number, nowMs = Date.now()): string {
  const diffSec = Math.floor((nowMs - timestampMs) / 1000);
  if (diffSec < 10) return "just now";
  if (diffSec < 60) return `${diffSec}s ago`;
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin} min ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr} hr ago`;
  return new Date(timestampMs).toLocaleString();
}
