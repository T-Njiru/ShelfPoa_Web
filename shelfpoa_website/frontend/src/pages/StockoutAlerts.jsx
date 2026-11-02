import { useEffect, useState } from "react";
import { api } from "../services/api";
import { downloadCsv, timeLabel } from "../lib/format";
import { GhostButton, Pill, PrimaryButton, Tabs } from "../components/ui";

const COLS = "grid-cols-[minmax(120px,1.1fr)_minmax(140px,1.4fr)_minmax(100px,1fr)_minmax(120px,1fr)_130px_150px] gap-x-4";
const LIMIT = 50;

export default function StockoutAlerts() {
  const [alerts, setAlerts] = useState([]);
  const [tab, setTab] = useState("all");
  const [resolved, setResolved] = useState(() => new Set()); // local until a write endpoint exists
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");

  useEffect(() => {
    api
      .getStockoutAlerts(LIMIT)
      .then(setAlerts)
      .catch(() => setErr("Couldn't load stock-out alerts."))
      .finally(() => setLoading(false));
  }, []);

  const state = (a) => (resolved.has(a.id) || a.status === "resolved" ? "resolved" : a.status === "acknowledged" ? "ack" : "open");
  const isOpen = (a) => state(a) !== "resolved";

  const openCount = alerts.filter(isOpen).length;
  const visible = alerts.filter((a) => (tab === "open" ? isOpen(a) : tab === "resolved" ? !isOpen(a) : true));

  // The API returns at most LIMIT rows, so when we hit it the counts are "at least", not exact.
  const more = alerts.length >= LIMIT ? "+" : "";
  const tabs = [
    { value: "all", label: `All (${alerts.length}${more})` },
    { value: "open", label: `Open (${openCount}${more})` },
    { value: "resolved", label: `Resolved (${alerts.length - openCount}${alerts.length - openCount > 0 ? more : ""})` },
  ];

  // TODO: persist via a backend/Realtime Database write once that endpoint exists.
  const markResolved = (id) => setResolved((s) => new Set(s).add(id));

  const exportCsv = () =>
    downloadCsv(
      "stockout-alerts.csv",
      visible.map((a) => ({
        sku: a.sku,
        outlet: a.branch_name,
        reported_by: a.reported_by ?? "",
        detected_at: a.detected_at,
        status: state(a),
      }))
    );

  if (loading) return <p className="text-muted text-sm">Loading…</p>;
  if (err) return <p className="text-bad text-sm">{err}</p>;

  return (
    <div>
      <div className="flex items-center mb-5">
        <Tabs tabs={tabs} value={tab} onChange={setTab} />
        <PrimaryButton onClick={exportCsv} className="ml-auto h-[34px] px-4">Export</PrimaryButton>
      </div>

      <div className="rounded-card bg-card overflow-x-auto">
       <div className="min-w-[880px]">
        <div className={`grid ${COLS} pl-[21px] pr-6 py-[19px] border-l-[3px] border-l-transparent border-b border-line text-[11px] font-semibold uppercase tracking-wide text-muted`}>
          <span>SKU</span>
          <span>Outlet</span>
          <span>Reported by</span>
          <span>Time</span>
          <span>Status</span>
          <span>Action</span>
        </div>

        {visible.map((a) => {
          const s = state(a);
          return (
            <div
              key={a.id}
              className={`grid ${COLS} items-center h-24 pl-[21px] pr-6 border-b border-line last:border-b-0 border-l-[3px] ${
                s === "resolved" ? "border-l-ok" : "border-l-bad"
              }`}
            >
              <span className="text-[13px] font-bold">{a.sku}</span>
              <span className="text-[13px] text-white/80">{a.branch_name}</span>
              <span className="text-[13px] text-white/80">{a.reported_by ?? "—"}</span>
              <span className="text-[13px] text-muted">{timeLabel(a.detected_at)}</span>
              <div>
                {s === "resolved" ? (
                  <Pill kind="ok">Restocked</Pill>
                ) : s === "ack" ? (
                  <Pill kind="warn">Acknowledged</Pill>
                ) : (
                  <Pill kind="bad">Out of stock</Pill>
                )}
              </div>
              <div>
                {s === "resolved" ? (
                  <GhostButton className="h-[30px] w-full text-left">View history</GhostButton>
                ) : (
                  <PrimaryButton onClick={() => markResolved(a.id)} className="h-[30px] w-full text-left">
                    Mark resolved
                  </PrimaryButton>
                )}
              </div>
            </div>
          );
        })}

        {!visible.length && <p className="p-6 text-sm text-muted">No alerts in this view.</p>}
       </div>
      </div>
    </div>
  );
}
