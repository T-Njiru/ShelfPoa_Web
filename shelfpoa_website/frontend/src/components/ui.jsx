import { TONE_HEX, TONE_TEXT, tone } from "../lib/format";

export function StatCard({ value, label, toneName }) {
  return (
    <div className="rounded-card bg-card px-6 py-5 h-[90px] flex flex-col justify-center">
      <div className={`text-[28px] font-bold leading-none ${TONE_TEXT[toneName]}`}>{value}</div>
      <div className="mt-3 text-[11px] font-semibold uppercase tracking-wide text-muted">{label}</div>
    </div>
  );
}

const PILL = {
  ok: "bg-ok-bg text-ok",
  bad: "bg-bad-bg text-bad",
  warn: "bg-warn-bg text-warn",
  neutral: "bg-field text-muted",
};

export function Pill({ kind = "neutral", children }) {
  return (
    <span className={`inline-flex items-center h-6 px-2.5 rounded-md text-[11px] font-semibold whitespace-nowrap ${PILL[kind]}`}>
      {children}
    </span>
  );
}

export function Ring({ value, label }) {
  const v = Math.max(0, Math.min(100, Number(value) || 0));
  const r = 19;
  const c = 2 * Math.PI * r;
  return (
    <div className="flex flex-col gap-1">
      <svg width="48" height="48" viewBox="0 0 48 48" role="img" aria-label={`${label} ${Math.round(v)}%`}>
        <circle cx="24" cy="24" r={r} fill="none" stroke="#525259" strokeWidth="5" />
        <circle
          cx="24"
          cy="24"
          r={r}
          fill="none"
          stroke={TONE_HEX[tone(v)]}
          strokeWidth="5"
          strokeDasharray={`${(v / 100) * c} ${c}`}
          transform="rotate(-90 24 24)"
        />
        <text x="24" y="28" textAnchor="middle" fontSize="11" fontWeight="700" fill="#fff">
          {Math.round(v)}%
        </text>
      </svg>
      <span className="text-[10px] font-semibold text-muted">{label}</span>
    </div>
  );
}

export function Tabs({ tabs, value, onChange }) {
  return (
    <div className="flex gap-2">
      {tabs.map((t) => (
        <button
          key={t.value}
          onClick={() => onChange(t.value)}
          className={`h-[34px] px-3 min-w-[90px] rounded-control text-xs font-semibold text-left whitespace-nowrap transition-colors ${
            value === t.value ? "bg-accent text-ink" : "bg-card text-white hover:bg-field"
          }`}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}

export function PrimaryButton({ className = "", ...props }) {
  return (
    <button
      {...props}
      className={`rounded-control bg-accent hover:bg-accent-hover text-ink text-xs font-semibold px-3 whitespace-nowrap transition-colors disabled:opacity-60 ${className}`}
    />
  );
}

export function GhostButton({ className = "", ...props }) {
  return (
    <button
      {...props}
      className={`rounded-control bg-field hover:bg-track text-white text-xs font-semibold px-3 whitespace-nowrap transition-colors ${className}`}
    />
  );
}

export const selectCls =
  "h-9 rounded-control bg-card text-white text-xs px-3 outline-none focus:ring-1 focus:ring-accent";

export function SectionLabel({ children }) {
  return <h2 className="text-xs font-semibold uppercase tracking-wide text-muted mb-2.5 leading-4">{children}</h2>;
}
