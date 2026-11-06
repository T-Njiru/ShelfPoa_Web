import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../services/api";
import { SKUS } from "../services/recommendationStore";
import { matches, useSearch } from "../lib/search";
import { GhostButton, PrimaryButton, SectionLabel, Tabs, selectCls } from "../components/ui";

const TABS = [
  { value: "all", label: "All" },
  { value: "fp", label: "FP-Growth" },
  { value: "xgb", label: "XGBoost" },
  { value: "shelf", label: "Shelf" },
];
const TOP = 8;       // rows per section (and per shelf lever) on the "All" tab
const PAGE = 20;     // "Show more" step on a section's own tab
const REAL_SKUS = new Set(SKUS); // hides the two non-existent SKUs still in the simulated sales history
const MIN_BASE = 5;  // a % change off fewer units than this is noise (1 -> 6 units = "+500%"), so it's hidden

const COLS = "grid-cols-[minmax(120px,1fr)_minmax(150px,1.3fr)_minmax(150px,1.2fr)_minmax(110px,0.8fr)_170px] gap-x-4";
const SHELF_COLS = "grid-cols-[110px_minmax(150px,1.3fr)_minmax(120px,1fr)_minmax(160px,1.4fr)_170px] gap-x-4";
const SHELF_KINDS = ["sos", "planogram", "availability"];
const LEVER = {
  sos: { label: "Share of shelf", tone: "text-info", makerType: "sos" },
  planogram: { label: "Planogram", tone: "text-warn", makerType: "sos" },
  availability: { label: "Availability", tone: "text-bad", makerType: "restock" },
};

const RULE_SORTS = {
  lift: { label: "Strongest link (lift)", fn: (a, b) => b.lift - a.lift },
  confidence: { label: "Most reliable (confidence)", fn: (a, b) => b.confidence - a.confidence },
  support: { label: "Most common (support)", fn: (a, b) => b.support - a.support },
};
const FORECAST_SORTS = {
  demand: { label: "Highest demand", fn: (a, b) => b.forecast_units_next_7d - a.forecast_units_next_7d },
  rise: { label: "Biggest rise", fn: (a, b) => (pctOf(b) ?? -1e9) - (pctOf(a) ?? -1e9) },
  drop: { label: "Biggest drop", fn: (a, b) => (pctOf(a) ?? 1e9) - (pctOf(b) ?? 1e9) },
};
const SHELF_SORTS = {
  units: { label: "Biggest gain (units/week)", fn: (a, b) => b.uplift_units - a.uplift_units },
  pct: { label: "Biggest gain (% sales)", fn: (a, b) => b.uplift_pct - a.uplift_pct },
  gap: { label: "Biggest gap to target", fn: (a, b) => b.target_value - b.current_value - (a.target_value - a.current_value) },
  outlet: { label: "Outlet A–Z", fn: (a, b) => a.branch_name.localeCompare(b.branch_name) },
};

// % change vs last week, only when last week had enough units to make a % meaningful
function pctOf(f) {
  return f.last_week_units != null && f.last_week_units >= MIN_BASE ? f.change_pct : null;
}

const titleCase = (s = "") => s.toLowerCase().replace(/(^|[\s'-])\w/g, (c) => c.toUpperCase());
const ruleItems = (r) => [...r.antecedent, ...r.consequent];

// Next week vs last week, colour-coded: green rise, red drop, grey roughly flat (within ±5%)
function Change({ pct, lowVolume }) {
  if (lowVolume) return <span className="text-[11px] text-muted" title={`Fewer than ${MIN_BASE} units last week`}>low volume</span>;
  if (pct == null) return <span className="text-[12px] text-muted">—</span>;
  const cls = pct >= 5 ? "bg-ok-bg text-ok" : pct <= -5 ? "bg-bad-bg text-bad" : "bg-field text-muted";
  const arrow = pct >= 5 ? "▲" : pct <= -5 ? "▼" : "≈";
  return (
    <span title="Next week's forecast vs last week's actual sales"
      className={`inline-flex items-center gap-1 h-6 px-2 rounded-md text-[12px] font-semibold whitespace-nowrap ${cls}`}>
      {arrow} {pct > 0 ? "+" : ""}{pct}%
    </span>
  );
}

function Select({ value, onChange, options, className = "w-[200px]" }) {
  return (
    <select className={`${selectCls} ${className}`} value={value} onChange={(e) => onChange(e.target.value)}>
      {options.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
    </select>
  );
}

function ShowMore({ shown, total, onMore }) {
  if (total <= shown) return null;
  return (
    <div className="flex items-center gap-3 pt-3">
      <GhostButton onClick={onMore} className="h-8">Show {Math.min(PAGE, total - shown)} more</GhostButton>
      <span className="text-[11px] text-muted">{shown} of {total}</span>
    </div>
  );
}

const Empty = ({ children }) => <p className="py-4 text-sm text-muted">{children}</p>;

export default function Recommendations() {
  const query = useSearch();
  const [tab, setTab] = useState("all");
  const [rules, setRules] = useState([]);
  const [forecasts, setForecasts] = useState([]);
  const [shelf, setShelf] = useState([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
  const navigate = useNavigate();

  // per-tab controls
  const [ruleSort, setRuleSort] = useState("lift");
  const [ruleSku, setRuleSku] = useState("");
  const [fcSort, setFcSort] = useState("demand");
  const [fcSku, setFcSku] = useState("");
  const [fcArea, setFcArea] = useState("");
  const [lever, setLever] = useState("");
  const [shelfSort, setShelfSort] = useState("units");
  const [shown, setShown] = useState({ fp: PAGE, xgb: PAGE, shelf: PAGE });
  const more = (k) => setShown((s) => ({ ...s, [k]: s[k] + PAGE }));
  useEffect(() => setShown({ fp: PAGE, xgb: PAGE, shelf: PAGE }), [tab, query]);

  useEffect(() => {
    Promise.all([
      api.getBasketRules(500),
      api.getForecasts(null),
      // every opportunity of each lever; a failure here only hides the Shelf section
      Promise.all(SHELF_KINDS.map((k) => api.getShelfOpportunities(500, k))).catch(() => []),
    ])
      .then(([r, f, s]) => {
        setRules(r);
        setForecasts(f.filter((x) => REAL_SKUS.has(x.sku)));
        setShelf(s.flat());
      })
      .catch(() => setErr("Couldn't load recommendations."))
      .finally(() => setLoading(false));
  }, []);

  // ---- filtered + sorted lists -------------------------------------------------------------
  const ruleSkus = useMemo(
    () => [...new Set(rules.flatMap(ruleItems).filter((i) => i.startsWith("BB ")))].sort(),
    [rules]
  );
  const ruleRows = useMemo(
    () =>
      rules
        .filter((r) => matches(query, ruleItems(r)))
        .filter((r) => tab !== "fp" || !ruleSku || ruleItems(r).includes(ruleSku))
        .sort(RULE_SORTS[tab === "fp" ? ruleSort : "lift"].fn),
    [rules, query, tab, ruleSku, ruleSort]
  );

  const areas = useMemo(() => [...new Set(forecasts.map((f) => f.sub_county).filter(Boolean))].sort(), [forecasts]);
  const fcRows = useMemo(
    () =>
      forecasts
        .filter((f) => matches(query, f.sku, f.branch_name, f.sub_county))
        .filter((f) => tab !== "xgb" || ((!fcSku || f.sku === fcSku) && (!fcArea || f.sub_county === fcArea)))
        // rise / drop rankings only make sense for SKUs that actually sell at the outlet
        .filter((f) => tab !== "xgb" || fcSort === "demand" || pctOf(f) != null)
        .sort(FORECAST_SORTS[tab === "xgb" ? fcSort : "demand"].fn),
    [forecasts, query, tab, fcSku, fcArea, fcSort]
  );

  const shelfRows = useMemo(() => {
    const rows = shelf
      .filter((o) => !o.sku || REAL_SKUS.has(o.sku))
      .filter((o) => matches(query, o.branch_name, o.sku, LEVER[o.kind]?.label));
    if (tab !== "shelf") {
      // All tab: top 8 of each lever, levers kept together
      return SHELF_KINDS.flatMap((k) => rows.filter((o) => o.kind === k).sort(SHELF_SORTS.units.fn).slice(0, TOP));
    }
    return rows.filter((o) => !lever || o.kind === lever).sort(SHELF_SORTS[shelfSort].fn);
  }, [shelf, query, tab, lever, shelfSort]);

  // ---- "Send recommendation" -> maker, prefilled -------------------------------------------
  const sendShelf = (o) =>
    navigate("/recommendation-maker", {
      state: { outlet: o.branch_name, sku: o.sku ?? "", type: LEVER[o.kind].makerType, source: `XGBoost — shelf what-if: ${o.message}` },
    });
  const sendForecast = (f) =>
    navigate("/recommendation-maker", {
      state: {
        outlet: f.branch_name,
        sku: f.sku,
        type: "restock",
        source: `XGBoost — demand forecast, ${f.forecast_units_next_7d} units next week (${f.sku}${
          f.change_pct != null ? `, ${f.change_pct > 0 ? "+" : ""}${f.change_pct}% vs last week` : ""
        })`,
      },
    });
  const sendRule = (r) =>
    navigate("/recommendation-maker", {
      state: {
        type: "copromo",
        sku: ruleItems(r).find((item) => item.startsWith("BB ")) ?? "",
        source: `FP-Growth — ${r.antecedent.join(" + ")} → ${r.consequent.join(" + ")}, confidence ${Math.round(r.confidence * 100)}%, lift ${r.lift}x`,
      },
    });

  if (loading) return <p className="text-muted text-sm">Loading…</p>;
  if (err) return <p className="text-bad text-sm">{err}</p>;

  const limitFor = (k) => (tab === "all" ? TOP : shown[k]);
  const visRules = ruleRows.slice(0, limitFor("fp"));
  const visFc = fcRows.slice(0, limitFor("xgb"));
  const visShelf = tab === "all" ? shelfRows : shelfRows.slice(0, shown.shelf);

  return (
    <div>
      <div className="mb-[22px]">
        <Tabs tabs={TABS} value={tab} onChange={setTab} />
      </div>

      {/* ---------------- FP-Growth ---------------- */}
      {(tab === "all" || tab === "fp") && (
        <section className="mb-6">
          <SectionLabel>Co-promotion rules · FP-Growth{tab === "all" && ruleRows.length > TOP ? ` · top ${TOP}` : ""}</SectionLabel>
          {tab === "fp" && (
            <div className="flex items-center gap-3 mb-3">
              <Select value={ruleSku} onChange={setRuleSku} options={[["", "All Blueband SKUs"], ...ruleSkus.map((s) => [s, s])]} />
              <Select value={ruleSort} onChange={setRuleSort} options={Object.entries(RULE_SORTS).map(([k, v]) => [k, v.label])} className="w-[230px]" />
              <span className="text-[11px] text-muted">{ruleRows.length} rules</span>
            </div>
          )}
          <div className="grid grid-cols-[repeat(auto-fill,minmax(260px,1fr))] gap-5">
            {visRules.map((r) => (
              <div key={ruleItems(r).join("|")} className="rounded-card bg-card p-4 min-h-[128px] flex flex-col">
                <div className="text-[13px] font-bold">{ruleItems(r).join(" + ")}</div>
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
          {!visRules.length && <Empty>No co-promotion rules match.</Empty>}
          {tab === "fp" && <ShowMore shown={visRules.length} total={ruleRows.length} onMore={() => more("fp")} />}
        </section>
      )}

      {/* ---------------- XGBoost demand ---------------- */}
      {(tab === "all" || tab === "xgb") && (
        <section className="mb-6">
          <SectionLabel>Demand forecast recommendations · XGBoost{tab === "all" && fcRows.length > TOP ? ` · top ${TOP} by demand` : ""}</SectionLabel>
          {tab === "xgb" && (
            <div className="flex items-center gap-3 mb-3">
              <Select value={fcSku} onChange={setFcSku} options={[["", "All SKUs"], ...SKUS.map((s) => [s, s])]} />
              <Select value={fcArea} onChange={setFcArea} options={[["", "All sub-counties"], ...areas.map((a) => [a, titleCase(a)])]} />
              <Select value={fcSort} onChange={setFcSort} options={Object.entries(FORECAST_SORTS).map(([k, v]) => [k, v.label])} className="w-[170px]" />
              <span className="text-[11px] text-muted">{fcRows.length} outlet × SKU forecasts</span>
            </div>
          )}
          <div className="rounded-card bg-card px-6 pt-5 pb-3 overflow-x-auto">
           <div className="min-w-[800px]">
            <div className={`grid ${COLS} pb-3 border-b border-line text-[11px] font-semibold uppercase tracking-wide text-muted`}>
              <span>SKU</span>
              <span>Outlet</span>
              <span>Last week → next week</span>
              <span>Change</span>
              <span>Action</span>
            </div>
            {visFc.map((f) => (
              <div key={`${f.branch_name}|${f.sku}`} className={`grid ${COLS} items-center h-[74px]`}>
                <span className="text-[13px] font-bold">{f.sku}</span>
                <div className="min-w-0">
                  <div className="text-[13px] text-white/80 truncate">{f.branch_name}</div>
                  {f.sub_county && <div className="text-[11px] text-muted">{titleCase(f.sub_county)}</div>}
                </div>
                <span className="text-[13px] whitespace-nowrap">
                  <span className="text-muted">{f.last_week_units ?? "—"} → </span>
                  <span className="font-semibold">{f.forecast_units_next_7d} units</span>
                </span>
                <div><Change pct={f.change_pct} lowVolume={f.last_week_units != null && f.last_week_units < MIN_BASE} /></div>
                <div>
                  <PrimaryButton onClick={() => sendForecast(f)} className="h-[30px] w-full text-left">
                    Send recommendation
                  </PrimaryButton>
                </div>
              </div>
            ))}
            {!visFc.length && <Empty>No forecasts match.</Empty>}
           </div>
          </div>
          {tab === "xgb" && <ShowMore shown={visFc.length} total={fcRows.length} onMore={() => more("xgb")} />}
        </section>
      )}

      {/* ---------------- Shelf what-ifs ---------------- */}
      {(tab === "all" || tab === "shelf") && shelf.length > 0 && (
        <section>
          <SectionLabel>Shelf opportunities · XGBoost what-if{tab === "all" ? ` · top ${TOP} per lever` : ""}</SectionLabel>
          {tab === "shelf" && (
            <div className="flex items-center gap-3 mb-3">
              <Select value={lever} onChange={setLever}
                options={[["", "All levers"], ...SHELF_KINDS.map((k) => [k, LEVER[k].label])]} className="w-[170px]" />
              <Select value={shelfSort} onChange={setShelfSort} options={Object.entries(SHELF_SORTS).map(([k, v]) => [k, v.label])} className="w-[230px]" />
              <span className="text-[11px] text-muted">{shelfRows.length} opportunities</span>
            </div>
          )}
          <div className="rounded-card bg-card px-6 pt-5 pb-3 overflow-x-auto">
           <div className="min-w-[800px]">
            <div className={`grid ${SHELF_COLS} pb-3 border-b border-line text-[11px] font-semibold uppercase tracking-wide text-muted`}>
              <span>Lever</span>
              <span>Outlet</span>
              <span>Now → target</span>
              <span>Expected impact</span>
              <span>Action</span>
            </div>
            {visShelf.map((o) => {
              const lv = LEVER[o.kind];
              return (
                <div key={o.id} className={`grid ${SHELF_COLS} items-center min-h-[74px] py-2`}>
                  <span className={`text-[12px] font-bold ${lv.tone}`}>{lv.label}</span>
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
            {!visShelf.length && <Empty>No shelf opportunities match.</Empty>}
           </div>
          </div>
          {tab === "shelf" && <ShowMore shown={visShelf.length} total={shelfRows.length} onMore={() => more("shelf")} />}
          <p className="mt-2 text-[11px] text-muted">
            Estimated by scoring next week twice with the demand model: as the shelf is now, and with the lever at the target.
          </p>
        </section>
      )}
    </div>
  );
}
