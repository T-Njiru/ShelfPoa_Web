import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../services/api";
import { PrimaryButton, SectionLabel, Tabs } from "../components/ui";

const COLS = "grid-cols-[minmax(120px,1.1fr)_minmax(140px,1.3fr)_minmax(150px,1.3fr)_minmax(140px,1.1fr)_170px] gap-x-4";
const TABS = [
  { value: "all", label: "All" },
  { value: "fp", label: "FP-Growth" },
  { value: "xgb", label: "XGBoost" },
  { value: "shelf", label: "Shelf" },
];

// Shelf what-ifs from the shelf-aware XGBoost model (/api/shelf/opportunities)
const SHELF_COLS = "grid-cols-[110px_minmax(150px,1.3fr)_minmax(120px,1fr)_minmax(160px,1.4fr)_170px] gap-x-4";
const SHELF_KINDS = ["sos", "planogram", "availability"];
const LEVER = {
  sos: { label: "Share of shelf", tone: "text-info", makerType: "sos" },
  planogram: { label: "Planogram", tone: "text-warn", makerType: "sos" },
  availability: { label: "Availability", tone: "text-bad", makerType: "restock" },
};

// Next week's forecast vs the last 3 weeks' average, shown as a bar (50% = flat) plus a signed label.
function trendBar(f) {
  const t = f.trend_pct;
  if (t == null) return { w: 0, label: "—" };
  return { w: Math.max(0, Math.min(100, 50 + t / 2)), label: `${t > 0 ? "+" : ""}${t}%` };
}

export default function Recommendations() {
  const [tab, setTab] = useState("all");
  const [rules, setRules] = useState([]);
  const [forecasts, setForecasts] = useState([]);
  const [shelf, setShelf] = useState([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
  const navigate = useNavigate();

  useEffect(() => {
    Promise.all([
      api.getBasketRules(3),
      api.getForecasts(8),
      // top 3 of each lever, so availability rows (biggest unit counts) don't crowd out the rest;
      // a failure here only hides the Shelf section instead of the whole page
      Promise.all(SHELF_KINDS.map((k) => api.getShelfOpportunities(3, k))).catch(() => []),
    ])
      .then(([r, f, s]) => {
        setRules(r);
        setForecasts(f);
        setShelf(s.flat());
      })
      .catch(() => setErr("Couldn't load recommendations."))
      .finally(() => setLoading(false));
  }, []);

  // Shelf what-if → SOS / restock recommendation for that outlet (+ SKU for availability)
  const sendShelf = (o) =>
    navigate("/recommendation-maker", {
      state: {
        outlet: o.branch_name,
        sku: o.sku ?? "",
        type: LEVER[o.kind].makerType,
        source: `XGBoost — shelf what-if: ${o.message}`,
      },
    });

  // XGBoost row → restock recommendation for that outlet + SKU
  const sendForecast = (f) =>
    navigate("/recommendation-maker", {
      state: {
        outlet: f.branch_name,
        sku: f.sku,
        type: "restock",
        source: `XGBoost — demand forecast, ${f.forecast_units_next_7d} units next week (${f.sku}${
          f.trend_pct != null ? `, ${f.trend_pct > 0 ? "+" : ""}${f.trend_pct}% vs 3-wk avg` : ""
        })`,
      },
    });

  // FP-Growth rule → co-promotion recommendation (outlet chosen in the maker)
  const sendRule = (r) =>
    navigate("/recommendation-maker", {
      state: {
        type: "copromo",
        sku: [...r.antecedent, ...r.consequent].find((item) => item.startsWith("BB ")) ?? "",
        source: `FP-Growth — ${r.antecedent.join(" + ")} → ${r.consequent.join(" + ")}, confidence ${Math.round(
          r.confidence * 100
        )}%, lift ${r.lift}x`,
      },
    });

  if (loading) return <p className="text-muted text-sm">Loading…</p>;
  if (err) return <p className="text-bad text-sm">{err}</p>;

  return (
    <div>
      <div className="mb-[22px]">
        <Tabs tabs={TABS} value={tab} onChange={setTab} />
      </div>

      {(tab === "all" || tab === "fp") && (
        <section className="mb-6">
          <SectionLabel>Co-promotion rules · FP-Growth</SectionLabel>
          <div className="grid grid-cols-[repeat(auto-fit,minmax(260px,1fr))] gap-5">
            {rules.map((r, i) => (
              <div key={i} className="rounded-card bg-card p-4 min-h-[128px] flex flex-col">
                <div className="w-8 h-8 rounded-lg bg-warn-bg mb-3" />
                <div className="text-[13px] font-bold">
                  {[...r.antecedent, ...r.consequent].join(" + ")}
                </div>
                <div className="text-[11px] text-muted">Support {(r.support * 100).toFixed(1)}%</div>
                <div className="mt-auto pt-3 flex flex-wrap gap-x-10 gap-y-1 text-[11px]">
                  <span className="text-warn">Confidence {Math.round(r.confidence * 100)}%</span>
                  <span className="text-ok">Lift {r.lift}x</span>
                </div>
                <PrimaryButton onClick={() => sendRule(r)} className="h-[30px] w-full text-left mt-3">
                  Send recommendation
                </PrimaryButton>
              </div>
            ))}
          </div>
        </section>
      )}

      {(tab === "all" || tab === "xgb") && (
        <section className="mb-6">
          <SectionLabel>Demand forecast recommendations · XGBoost</SectionLabel>
          <div className="rounded-card bg-card px-6 pt-5 pb-3 overflow-x-auto">
           <div className="min-w-[800px]">
            <div className={`grid ${COLS} pb-3 border-b border-line text-[11px] font-semibold uppercase tracking-wide text-muted`}>
              <span>SKU</span>
              <span>Outlet</span>
              <span>Predicted demand</span>
              <span>Vs 3-wk avg</span>
              <span>Action</span>
            </div>
            {forecasts.map((f, i) => {
              const c = trendBar(f);
              return (
                <div key={i} className={`grid ${COLS} items-center h-[74px]`}>
                  <span className="text-[13px] font-bold">{f.sku}</span>
                  <span className="text-[13px] text-white/80">{f.branch_name}</span>
                  <span className="text-[13px] font-semibold text-ok whitespace-nowrap">{f.forecast_units_next_7d} units next week</span>
                  <div className="flex items-center gap-2">
                    <div className="w-[100px] h-1.5 rounded-full bg-track overflow-hidden">
                      <div className="h-full rounded-full bg-info" style={{ width: `${c.w}%` }} />
                    </div>
                    <span className="text-[11px] text-muted">{c.label}</span>
                  </div>
                  <div>
                    <PrimaryButton onClick={() => sendForecast(f)} className="h-[30px] w-full text-left">
                      Send recommendation
                    </PrimaryButton>
                  </div>
                </div>
              );
            })}
           </div>
          </div>
        </section>
      )}

      {(tab === "all" || tab === "shelf") && shelf.length > 0 && (
        <section>
          <SectionLabel>Shelf opportunities · XGBoost what-if</SectionLabel>
          <div className="rounded-card bg-card px-6 pt-5 pb-3 overflow-x-auto">
           <div className="min-w-[800px]">
            <div className={`grid ${SHELF_COLS} pb-3 border-b border-line text-[11px] font-semibold uppercase tracking-wide text-muted`}>
              <span>Lever</span>
              <span>Outlet</span>
              <span>Now → target</span>
              <span>Expected impact</span>
              <span>Action</span>
            </div>
            {shelf.map((o) => {
              const lever = LEVER[o.kind];
              return (
                <div key={o.id} className={`grid ${SHELF_COLS} items-center min-h-[74px] py-2`}>
                  <span className={`text-[12px] font-bold ${lever.tone}`}>{lever.label}</span>
                  <div>
                    <div className="text-[13px] text-white/80">{o.branch_name}</div>
                    {o.sku && <div className="text-[11px] text-muted">{o.sku}</div>}
                  </div>
                  <span className="text-[13px] font-semibold whitespace-nowrap">
                    {Math.round(o.current_value)}% → {Math.round(o.target_value)}%
                  </span>
                  <span className="text-[13px] font-semibold text-ok">
                    {o.kind === "availability"
                      ? `~${Math.round(o.uplift_units)} units/week recovered`
                      : `+${o.uplift_pct}% sales (+${Math.round(o.uplift_units)} units/week)`}
                  </span>
                  <div>
                    <PrimaryButton onClick={() => sendShelf(o)} className="h-[30px] w-full text-left">
                      Send recommendation
                    </PrimaryButton>
                  </div>
                </div>
              );
            })}
           </div>
          </div>
          <p className="mt-2 text-[11px] text-muted">
            Estimated by scoring next week twice with the demand model: as the shelf is now, and with the lever at the target.
          </p>
        </section>
      )}
    </div>
  );
}
