import { useEffect, useState } from "react";
import { api } from "../services/api";
import { TONE_TEXT, timeLabel, tone } from "../lib/format";
import { GhostButton, Tabs } from "./ui";

const PERIODS = [
  { value: "latest", label: "Latest" },
  { value: "day", label: "Last 24 hours" },
  { value: "week", label: "Last 7 days" },
];
const COLS = "grid-cols-[minmax(150px,1.4fr)_minmax(120px,1fr)_minmax(150px,1.3fr)_80px_100px] gap-x-4";
const titleCase = (s) => (s ? s.toLowerCase().replace(/(^|[\s'-])\w/g, (c) => c.toUpperCase()) : "");

function Pct({ value }) {
  if (value == null) return <span className="text-[13px] text-muted">—</span>;
  return <span className={`text-[13px] font-semibold ${TONE_TEXT[tone(value)]}`}>{Math.round(value)}%</span>;
}

/** Visits a merchandiser submitted (OSA, SOS, planogram per visit), newest first. */
export default function SubmissionsModal({ merchandiser, onClose }) {
  const [period, setPeriod] = useState("latest");
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");

  useEffect(() => {
    let live = true;
    setLoading(true);
    setErr("");
    api
      .getMerchandiserSubmissions(merchandiser.merchandiser_id, period)
      .then((r) => live && setRows(r))
      .catch(() => live && setErr("Couldn't load submissions."))
      .finally(() => live && setLoading(false));
    return () => {
      live = false;
    };
  }, [merchandiser.merchandiser_id, period]);

  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-6" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-label={`Submissions by ${merchandiser.name}`}
        className="w-full max-w-[860px] max-h-[85vh] flex flex-col rounded-card bg-card"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-4 px-6 pt-5 pb-4 border-b border-line">
          <div className="min-w-0">
            <h2 className="text-base font-bold truncate">{merchandiser.name}</h2>
            <p className="text-[11px] text-muted">Submitted OSA, share of shelf and compliance, per store visit</p>
          </div>
          <GhostButton onClick={onClose} className="ml-auto h-8">Close</GhostButton>
        </div>

        <div className="px-6 pt-4">
          <Tabs tabs={PERIODS} value={period} onChange={setPeriod} />
        </div>

        <div className="px-6 pt-4 pb-6 overflow-auto">
          <div className="min-w-[680px]">
            <div className={`grid ${COLS} pb-3 border-b border-line text-[11px] font-semibold uppercase tracking-wide text-muted`}>
              <span>Outlet</span>
              <span>When</span>
              <span>OSA</span>
              <span>SOS</span>
              <span>Compliance</span>
            </div>

            {loading && <p className="pt-5 text-sm text-muted">Loading…</p>}
            {err && <p className="pt-5 text-sm text-bad">{err}</p>}
            {!loading && !err && !rows.length && (
              <p className="pt-5 text-sm text-muted">
                No submissions {period === "day" ? "in the last 24 hours" : period === "week" ? "in the last 7 days" : "yet"}.
              </p>
            )}

            {!loading &&
              !err &&
              rows.map((r) => (
                <div key={r.audit_id} className={`grid ${COLS} items-center py-3 border-b border-line last:border-b-0`}>
                  <div className="min-w-0">
                    <div className="text-[13px] font-bold truncate">{r.branch_name || r.outlet_id}</div>
                    <div className="text-[11px] text-muted">{titleCase(r.sub_county) || "—"}</div>
                  </div>
                  <span className="text-[13px] text-white/80">{timeLabel(r.timestamp)}</span>
                  <div>
                    <Pct value={r.osa_pct} />
                    {r.out_of_stock.length > 0 && (
                      <div className="text-[11px] text-bad leading-snug">Out: {r.out_of_stock.join(", ")}</div>
                    )}
                  </div>
                  <Pct value={r.sos_pct} />
                  <Pct value={r.planogram_pct} />
                </div>
              ))}
          </div>
        </div>
      </div>
    </div>
  );
}
