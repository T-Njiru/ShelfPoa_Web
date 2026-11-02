// >=75 healthy, 50-74 watch, <50 poor (matches the Figma ring colours)
export function tone(pct) {
  if (pct >= 75) return "ok";
  if (pct >= 50) return "warn";
  return "bad";
}

// KPI cards use a slightly lower "healthy" bar than the per-row rings (Figma: 72% KPI is green, 71% ring is amber).
export function statTone(pct) {
  if (pct >= 70) return "ok";
  if (pct >= 50) return "warn";
  return "bad";
}

export const TONE_HEX = { ok: "#5cc48a", warn: "#f2b84a", bad: "#e06159" };
export const TONE_TEXT = { ok: "text-ok", warn: "text-warn", bad: "text-bad" };

const pad = (n) => String(n).padStart(2, "0");

// "Today, 08:42" / "Yesterday, 16:03" / "2 days ago"
export function timeLabel(iso) {
  const d = new Date(iso);
  if (isNaN(d)) return "—";
  const startOfDay = (x) => new Date(x.getFullYear(), x.getMonth(), x.getDate());
  const days = Math.round((startOfDay(new Date()) - startOfDay(d)) / 86400000);
  const hm = `${pad(d.getHours())}:${pad(d.getMinutes())}`;
  if (days <= 0) return `Today, ${hm}`;
  if (days === 1) return `Yesterday, ${hm}`;
  return `${days} days ago`;
}

export function agoLabel(iso) {
  const mins = Math.max(0, Math.round((Date.now() - new Date(iso)) / 60000));
  if (mins < 60) return `${Math.max(mins, 1)}m ago`;
  if (mins < 1440) return `${Math.round(mins / 60)}h ago`;
  return `${Math.round(mins / 1440)}d ago`;
}

export function downloadCsv(filename, rows) {
  if (!rows.length) return;
  const cols = Object.keys(rows[0]);
  const esc = (v) => `"${String(v ?? "").replace(/"/g, '""')}"`;
  const csv = [cols.join(","), ...rows.map((r) => cols.map((c) => esc(r[c])).join(","))].join("\n");
  const url = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export const initials = (name = "") =>
  name.split(/\s+/).filter(Boolean).slice(0, 2).map((p) => p[0]).join("").toUpperCase();
