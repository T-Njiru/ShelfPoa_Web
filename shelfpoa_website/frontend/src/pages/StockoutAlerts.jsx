import { useCallback, useEffect, useState } from "react";
import { api } from "../services/api";
import { dateTimeLabel, downloadCsv, timeLabel } from "../lib/format";
import { GhostButton, Pill, PrimaryButton, Tabs } from "../components/ui";
import { matches, useSearch } from "../lib/search";

const COLS = "grid-cols-[minmax(120px,1.1fr)_minmax(140px,1.4fr)_minmax(100px,1fr)_minmax(120px,1fr)_130px_150px] gap-x-4";
// Load every current alert: open ones come first, so a lower limit would hide resolved ones
const LIMIT = 500;

const EVENT = {
  out_of_stock: { label: "Reported out of stock", dot: "bg-bad", by: "by" },
  in_stock: { label: "Found in stock", dot: "bg-muted", by: "by" },
  resolved: { label: "Marked resolved", dot: "bg-ok", by: "by" },
};

/** Who reported it, every audit reading since, and who marked it resolved and when. */
function HistoryModal({ alert, onClose }) {
  const [events, setEvents] = useState(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    let live = true;
    api
      .getStockoutHistory(alert)
      .then((e) => live && setEvents(e))
      .catch((e) => live && setErr(e.message || "Couldn't load the history."));
    const esc = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", esc);
    return () => {
      live = false;
      window.removeEventListener("keydown", esc);
    };
  }, [alert, onClose]);

  return (
    <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-6" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-label={`History for ${alert.sku} at ${alert.branch_name}`}
        className="w-full max-w-[560px] max-h-[80vh] flex flex-col rounded-card bg-card"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-4 px-6 pt-5 pb-4 border-b border-line">
          <div className="min-w-0">
            <h2 className="text-base font-bold truncate">{alert.sku}</h2>
            <p className="text-[11px] text-muted truncate">{alert.branch_name}</p>
          </div>
          <GhostButton onClick={onClose} className="ml-auto h-8">Close</GhostButton>
        </div>
        <div className="px-6 py-5 overflow-auto">
          {err && <p className="text-sm text-bad">{err}</p>}
          {!err && !events && <p className="text-sm text-muted">Loading…</p>}
          {events && !events.length && <p className="text-sm text-muted">No history recorded.</p>}
          {events && (
            <ol className="flex flex-col gap-4">
              {events.map((e, i) => (
                <li key={i} className="flex gap-3">
                  <span className={`mt-1.5 w-2.5 h-2.5 rounded-full shrink-0 ${EVENT[e.kind]?.dot ?? "bg-muted"}`} />
                  <div className="min-w-0">
                    <div className="text-[13px] font-semibold">{EVENT[e.kind]?.label ?? e.kind}</div>
                    <div className="text-[11px] text-muted">
                      {dateTimeLabel(e.at)}
                      {e.by ? ` · ${EVENT[e.kind]?.by ?? "by"} ${e.by}` : ""}
                    </div>
                  </div>
                </li>
              ))}
            </ol>
          )}
        </div>
      </div>
    </div>
  );
}

export default function StockoutAlerts() {
  const query = useSearch();
  const [alerts, setAlerts] = useState([]);
  const [tab, setTab] = useState("all");
  const [resolving, setResolving] = useState("");
  const [history, setHistory] = useState(null); // the alert whose history is open
  const closeHistory = useCallback(() => setHistory(null), []);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
  const [saveErr, setSaveErr] = useState("");

  useEffect(() => {
    api
      .getStockoutAlerts(LIMIT)
      .then(setAlerts)
      .catch(() => setErr("Couldn't load stock-out alerts."))
      .finally(() => setLoading(false));
  }, []);

  const state = (a) => (a.status === "resolved" ? "resolved" : a.status === "acknowledged" ? "ack" : "open");
  const isOpen = (a) => state(a) !== "resolved";

  const openCount = alerts.filter(isOpen).length;
  const visible = alerts
    .filter((a) => (tab === "open" ? isOpen(a) : tab === "resolved" ? !isOpen(a) : true))
    .filter((a) => matches(query, a.sku, a.branch_name, a.reported_by));

  // The API returns at most LIMIT rows, so when we hit it the counts are "at least", not exact.
  const more = alerts.length >= LIMIT ? "+" : "";
  const tabs = [
    { value: "all", label: `All (${alerts.length}${more})` },
    { value: "open", label: `Open (${openCount}${more})` },
    { value: "resolved", label: `Resolved (${alerts.length - openCount}${alerts.length - openCount > 0 ? more : ""})` },
  ];

  // Saved through the API (Firebase), so it survives a refresh and every admin sees it.
  async function markResolved(alert) {
    setResolving(alert.id);
    setSaveErr("");
    try {
      const saved = await api.resolveStockout(alert);
      setAlerts((list) =>
        list.map((a) =>
          a.id === alert.id ? { ...a, status: "resolved", resolved_by: saved.resolved_by, resolved_at: saved.resolved_at } : a
        )
      );
    } catch (e) {
      setSaveErr(e.message || "Couldn't save. Try again.");
    } finally {
      setResolving("");
    }
  }

  const exportCsv = () =>
    downloadCsv(
      "stockout-alerts.csv",
      visible.map((a) => ({
        sku: a.sku,
        outlet: a.branch_name,
        reported_by: a.reported_by ?? "",
        detected_at: a.detected_at,
        status: state(a),
        resolved_by: a.resolved_by ?? "",
        resolved_at: a.resolved_at ?? "",
      }))
    );

  if (loading) return <p className="text-muted text-sm">Loading…</p>;
  if (err) return <p className="text-bad text-sm">{err}</p>;

  return (
    <div>
      {saveErr && <p className="text-bad text-xs mb-3">{saveErr}</p>}
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
                  <div className="flex flex-col items-start gap-1">
                    <Pill kind="ok">Restocked</Pill>
                    {a.resolved_by && (
                      <span className="text-[10px] text-muted leading-tight">
                        by {a.resolved_by}, {timeLabel(a.resolved_at)}
                      </span>
                    )}
                  </div>
                ) : s === "ack" ? (
                  <Pill kind="warn">Acknowledged</Pill>
                ) : (
                  <Pill kind="bad">Out of stock</Pill>
                )}
              </div>
              <div>
                {s === "resolved" ? (
                  <GhostButton onClick={() => setHistory(a)} className="h-[30px] w-full text-left">View history</GhostButton>
                ) : (
                  <PrimaryButton onClick={() => markResolved(a)} disabled={resolving === a.id} className="h-[30px] w-full text-left">
                    {resolving === a.id ? "Saving…" : "Mark resolved"}
                  </PrimaryButton>
                )}
              </div>
            </div>
          );
        })}

        {!visible.length && <p className="p-6 text-sm text-muted">No alerts in this view.</p>}
       </div>
      </div>
      {history && <HistoryModal alert={history} onClose={closeHistory} />}
    </div>
  );
}
