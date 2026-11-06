import { useEffect, useMemo, useState } from "react";
import { api } from "../services/api";
import { downloadCsv, initials, statTone, tone } from "../lib/format";
import { Pill, PrimaryButton, Ring, StatCard, selectCls } from "../components/ui";
import SubmissionsModal from "../components/SubmissionsModal";
import { matches, useSearch } from "../lib/search";

const COLS = "grid-cols-[minmax(170px,1.3fr)_minmax(140px,1.3fr)_minmax(80px,0.8fr)_minmax(80px,0.8fr)_minmax(80px,0.8fr)_minmax(120px,0.9fr)] gap-x-4";
const avg = (rows, key) => (rows.length ? rows.reduce((s, r) => s + (Number(r[key]) || 0), 0) / rows.length : 0);
const ALERT_LIMIT = 100;
// Sub-counties come from the outlets each merchandiser visited (last 30 days)
const titleCase = (s) => s.toLowerCase().replace(/(^|[\s'-])\w/g, (c) => c.toUpperCase());
const locationsOf = (r) => (r.sub_counties ?? []).map(titleCase);

export default function MerchandiserPerformance() {
  const query = useSearch();
  const [rows, setRows] = useState([]);
  const [openAlerts, setOpenAlerts] = useState("0");
  const [location, setLocation] = useState("");
  const [selected, setSelected] = useState(null); // merchandiser whose submissions are open
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");

  useEffect(() => {
    Promise.all([
      api.getMerchandiserPerformance(50),
      api.getStockoutAlerts(ALERT_LIMIT).catch(() => []), // alert count is secondary; don't fail the page on it
    ])
      .then(([perf, alerts]) => {
        setRows(perf);
        const open = alerts.filter((a) => a.status !== "resolved").length;
        // the API caps results, so a count at the cap is "at least", not exact
        setOpenAlerts(alerts.length >= ALERT_LIMIT && open >= ALERT_LIMIT ? `${open}+` : String(open));
      })
      .catch(() => setErr("Couldn't load merchandiser performance."))
      .finally(() => setLoading(false));
  }, []);

  const locations = useMemo(() => [...new Set(rows.flatMap(locationsOf))].sort(), [rows]);
  const visible = rows
    .filter((r) => !location || locationsOf(r).includes(location))
    .filter((r) => matches(query, r.name, r.merchandiser_id, r.outlets ?? [], locationsOf(r)));

  const exportCsv = () =>
    downloadCsv(
      "merchandiser-performance.csv",
      visible.map((r) => ({
        merchandiser: r.name,
        locations: locationsOf(r).join("; "),
        outlets: (r.outlets ?? []).join("; "),
        sos_pct: r.avg_sos_pct,
        osa_pct: r.avg_osa_pct,
        compliance_pct: r.planogram_compliance_pct,
      }))
    );

  if (loading) return <p className="text-muted text-sm">Loading…</p>;
  if (err) return <p className="text-bad text-sm">{err}</p>;

  const sos = avg(visible, "avg_sos_pct");
  const osa = avg(visible, "avg_osa_pct");
  const comp = avg(visible, "planogram_compliance_pct");

  return (
    <div>
      <div className="flex items-center gap-3 mb-5">
        <select className={`${selectCls} w-[200px]`} value={location} onChange={(e) => setLocation(e.target.value)}>
          <option value="">All sub-counties</option>
          {locations.map((l) => (
            <option key={l} value={l}>{l}</option>
          ))}
        </select>
        <span className="text-[11px] text-muted">Click a merchandiser to see their submissions</span>
        <PrimaryButton onClick={exportCsv} className="ml-auto h-9 px-4">Export</PrimaryButton>
      </div>

      <div className="grid grid-cols-4 gap-4 mb-[22px]">
        <StatCard value={`${Math.round(sos)}%`} label="Avg SOS" toneName={statTone(sos)} />
        <StatCard value={`${Math.round(osa)}%`} label="Avg OSA" toneName={statTone(osa)} />
        <StatCard value={`${Math.round(comp)}%`} label="Avg compliance" toneName={statTone(comp)} />
        <StatCard value={openAlerts} label="Open alerts" toneName="bad" />
      </div>

      <div className="rounded-card bg-card px-6 pt-5 pb-8 min-h-[580px] overflow-x-auto">
       <div className="min-w-[760px]">
        <div className={`grid ${COLS} pb-3 border-b border-line text-[11px] font-semibold uppercase tracking-wide text-muted`}>
          <span>Merchandiser</span>
          <span>Locations</span>
          <span>SOS</span>
          <span>OSA</span>
          <span>Compliance</span>
          <span>Status</span>
        </div>

        {visible.map((r) => {
          const onTrack = [r.avg_sos_pct, r.avg_osa_pct, r.planogram_compliance_pct].every((v) => tone(v) === "ok");
          return (
            <div
              key={r.merchandiser_id}
              role="button"
              tabIndex={0}
              onClick={() => setSelected(r)}
              onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && setSelected(r)}
              className={`grid ${COLS} items-center h-[88px] -mx-3 px-3 rounded-control cursor-pointer hover:bg-white/5 focus:outline-none focus:ring-1 focus:ring-accent`}
            >
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-full bg-field grid place-items-center text-[10px] font-semibold text-muted">
                  {initials(r.name)}
                </div>
                <span className="text-[13px] font-bold truncate">{r.name}</span>
              </div>
              <div className="min-w-0" title={(r.outlets ?? []).join(", ")}>
                <div className="text-[13px] text-white/80 truncate">{locationsOf(r).join(", ") || "—"}</div>
                <div className="text-[11px] text-muted">
                  {r.branches_covered} outlet{r.branches_covered === 1 ? "" : "s"} · {r.visits_this_month} visits this month
                </div>
              </div>
              <Ring value={r.avg_sos_pct} label="SOS" />
              <Ring value={r.avg_osa_pct} label="OSA" />
              <Ring value={r.planogram_compliance_pct} label="Compl" />
              <div>
                <Pill kind={onTrack ? "ok" : "bad"}>{onTrack ? "On track" : "Needs review"}</Pill>
              </div>
            </div>
          );
        })}

        {!visible.length && <p className="pt-6 text-sm text-muted">No merchandisers to show.</p>}
       </div>
      </div>

      {selected && <SubmissionsModal merchandiser={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}
