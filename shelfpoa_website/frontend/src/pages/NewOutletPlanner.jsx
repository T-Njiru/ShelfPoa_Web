import { useEffect, useState } from "react";
import { api } from "../services/api";
import { downloadCsv } from "../lib/format";
import { PrimaryButton, SectionLabel, Tabs, selectCls } from "../components/ui";
import SiteMap from "../components/SiteMap";

// Plans a branch with NO sales history: the new-outlet model (chain, sub-county, satellite catchment)
// forecasts weekly demand per SKU; the backend turns that into an opening order and shelf facings.
// "Pin on map" looks the point up in the pre-built Earth Engine grid, so no satellite work is needed here.
const MODES = [
  { value: "pin", label: "Pin on map" },
  { value: "existing", label: "Existing" },
  { value: "site", label: "Manual" },
];
// "-1.2891, 36.7620", "(-1.2891,36.7620)" or a Google Maps link containing "@-1.2891,36.7620"
function parseCoords(text) {
  const m = text.match(/(-?\d{1,2}(?:\.\d+)?)\s*,\s*(-?\d{1,3}(?:\.\d+)?)/);
  if (!m) return null;
  const lat = Number(m[1]), lon = Number(m[2]);
  return Math.abs(lat) <= 90 && Math.abs(lon) <= 180 ? { lat, lon } : null;
}
const fmtInt = (n) => Math.round(n).toLocaleString("en-KE");
const COLS = "grid-cols-[minmax(130px,1.2fr)_minmax(110px,1fr)_minmax(150px,1.2fr)_minmax(90px,0.7fr)_minmax(140px,1.2fr)] gap-x-4";
const fieldCls = "w-full h-10 rounded-control bg-field px-3 text-[13px] text-white outline-none focus:ring-1 focus:ring-accent";
const labelCls = "block mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted";
const titleCase = (s = "") => s.toLowerCase().replace(/(^|[\s'-])\w/g, (c) => c.toUpperCase());
const fmtPop = (n) => (n >= 1000 ? `${Math.round(n / 1000)}k` : String(Math.round(n)));

function Field({ label, children, hint }) {
  return (
    <label className="block">
      <span className={labelCls}>{label}</span>
      {children}
      {hint && <span className="block mt-1 text-[10px] text-muted">{hint}</span>}
    </label>
  );
}

function Stat({ value, label, sub }) {
  return (
    <div className="rounded-card bg-card px-5 py-4 min-h-[90px] flex flex-col justify-center">
      <div className="text-[26px] font-bold leading-none">{value}</div>
      <div className="mt-2 text-[11px] font-semibold uppercase tracking-wide text-muted">{label}</div>
      {sub && <div className="text-[11px] text-muted mt-0.5">{sub}</div>}
    </div>
  );
}

export default function NewOutletPlanner() {
  const [options, setOptions] = useState(null);
  const [mode, setMode] = useState("existing");
  const [pin, setPin] = useState(null);                 // { lat, lon }
  const [coordText, setCoordText] = useState("");
  const [loc, setLoc] = useState(null);                 // catchment at the pin
  const [locBusy, setLocBusy] = useState(false);
  const [site, setSite] = useState("");                 // "chain|branch"
  const [chain, setChain] = useState("Naivas");
  const [subCounty, setSubCounty] = useState("");
  const [population, setPopulation] = useState("40000");
  const [growthPct, setGrowthPct] = useState("3");
  const [segment, setSegment] = useState("");
  const [restockDays, setRestockDays] = useState("7");
  const [leadDays, setLeadDays] = useState("2");
  const [service, setService] = useState("0.95");
  const [facings, setFacings] = useState("40");
  const [plan, setPlan] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  async function run(body) {
    setBusy(true);
    setErr("");
    try {
      setPlan(await api.planNewOutlet({
        ...body,
        restock_days: Number(restockDays),
        lead_time_days: Number(leadDays),
        service_level: Number(service),
        blueband_facings: Number(facings),
      }));
    } catch (e) {
      setErr(e.message || "Couldn't plan this outlet.");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    api.getNewOutletOptions()
      .then((o) => {
        setOptions(o);
        if (o.sub_counties.length) setSubCounty(o.sub_counties[0]);
        if (o.grid_available) {
          setMode("pin");                                 // map first; nothing to plan until a pin is dropped
        } else if (o.sites.length) {
          const first = `${o.sites[0].chain}|${o.sites[0].branch}`;
          setSite(first);
          run({ chain: o.sites[0].chain, branch: o.sites[0].branch }); // show a worked example straight away
        }
      })
      .catch(() => setErr("Couldn't load the planner options."));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const pinBody = (l, sc = subCounty, ch = chain) => ({
    chain: ch, sub_county: sc, catchment_pop_2026: l.catchment_pop_2026, built_growth_annual: l.built_growth_annual,
    ...(segment ? { dominant_income_segment: segment } : {}),
  });

  async function pick(lat, lon) {
    const p = { lat: Number(lat.toFixed(6)), lon: Number(lon.toFixed(6)) };
    setPin(p);
    setCoordText(`${p.lat.toFixed(5)}, ${p.lon.toFixed(5)}`);
    setLoc(null);
    setPlan(null);
    setErr("");
    setLocBusy(true);
    try {
      const l = await api.getLocationCatchment(p.lat, p.lon);
      setLoc(l);
      setSubCounty(l.sub_county ?? subCounty);            // the effect below then plans it
    } catch (e) {
      setErr(e.message || "Couldn't look up that location.");
    } finally {
      setLocBusy(false);
    }
  }

  // pin mode: re-plan whenever the pin, chain, sub-county or income segment changes
  useEffect(() => {
    if (mode === "pin" && loc) run(pinBody(loc));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loc, chain, subCounty, segment]);

  function goToCoords() {
    const c = parseCoords(coordText);
    if (!c) return setErr("Paste coordinates like -1.2891, 36.7620 (from Google Maps: right-click the spot).");
    pick(c.lat, c.lon);
  }

  function changeMode(m) {
    setMode(m);
    setPlan(null);
    setErr("");
  }

  function submit() {
    if (mode === "pin") {
      if (!loc) return setErr("Click the map or paste coordinates first.");
      return run(pinBody(loc));
    }
    if (mode === "existing") {
      const [c, b] = site.split("|");
      if (!c || !b) return setErr("Choose an outlet.");
      return run({ chain: c, branch: b });
    }
    const pop = Number(population);
    const growth = Number(growthPct) / 100;
    if (!(pop > 0)) return setErr("Enter the catchment population (people within ~2 km).");
    if (Number.isNaN(growth)) return setErr("Enter the built-up growth rate.");
    run({
      chain, sub_county: subCounty, catchment_pop_2026: pop, built_growth_annual: growth,
      ...(segment ? { dominant_income_segment: segment } : {}),
    });
  }

  const exportCsv = () =>
    plan && downloadCsv(`opening-plan-${plan.chain}-${plan.branch ?? plan.sub_county}.csv`.replace(/\s+/g, "-"),
      plan.skus.map((s) => ({
        sku: s.sku,
        weekly_demand_units: s.predicted_units_per_week,
        opening_stock_units: s.opening_stock_units,
        of_which_safety_stock: s.safety_stock_units,
        facings: s.facings,
      })));

  const bench = plan?.comparable_chain_in_area ?? plan?.comparable_chain;
  const outletsTxt = bench ? `${bench.outlets} outlet${bench.outlets === 1 ? "" : "s"}` : "";
  const benchLabel = plan?.comparable_chain_in_area
    ? `${plan.chain} in ${titleCase(plan.sub_county)} (${outletsTxt})`
    : bench ? `${plan.chain} average (${outletsTxt})` : "";
  const maxDemand = plan ? Math.max(...plan.skus.map((s) => s.predicted_units_per_week), 1) : 1;

  return (
    <div className="grid grid-cols-[340px_minmax(0,1fr)] gap-6 items-start">
      {/* ---------------- inputs ---------------- */}
      <div className="rounded-card bg-card p-5 flex flex-col gap-4">
        <Tabs tabs={MODES} value={mode} onChange={changeMode} />

        {mode === "pin" ? (
          <>
            <Field label="Location" hint="Click the map, or paste coordinates (Google Maps: right-click the spot).">
              <div className="flex gap-2">
                <input className={fieldCls} placeholder="-1.2891, 36.7620" value={coordText}
                  onChange={(e) => setCoordText(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && goToCoords()} />
                <button onClick={goToCoords} className="h-10 px-3 rounded-control bg-field text-xs font-semibold hover:bg-track">Go</button>
              </div>
            </Field>
            <Field label="Chain">
              <select className={fieldCls} value={chain} onChange={(e) => setChain(e.target.value)}>
                {(options?.chains ?? []).map((c) => <option key={c}>{c}</option>)}
              </select>
            </Field>
            <Field label="Sub-county" hint={loc?.sub_county_from ? `Guessed from the nearest outlet, ${loc.sub_county_from}. Change it if wrong.` : null}>
              <select className={fieldCls} value={subCounty} onChange={(e) => setSubCounty(e.target.value)}>
                {(options?.sub_counties ?? []).map((s) => <option key={s} value={s}>{titleCase(s)}</option>)}
              </select>
            </Field>
            <Field label="Income segment">
              <select className={fieldCls} value={segment} onChange={(e) => setSegment(e.target.value)}>
                <option value="">Chain's usual</option>
                {(options?.income_segments ?? []).map((s) => <option key={s} value={s}>{titleCase(s)}</option>)}
              </select>
            </Field>
          </>
        ) : mode === "existing" ? (
          <Field label="Outlet" hint="Uses the outlet's satellite catchment on file, ignoring its sales history.">
            <select className={fieldCls} value={site} onChange={(e) => setSite(e.target.value)}>
              {(options?.sites ?? []).map((s) => (
                <option key={`${s.chain}|${s.branch}`} value={`${s.chain}|${s.branch}`}>
                  {s.chain} {s.branch} · {titleCase(s.sub_county)} · {fmtPop(s.catchment_pop_2026)} people
                </option>
              ))}
            </select>
          </Field>
        ) : (
          <>
            <Field label="Chain">
              <select className={fieldCls} value={chain} onChange={(e) => setChain(e.target.value)}>
                {(options?.chains ?? []).map((c) => <option key={c}>{c}</option>)}
              </select>
            </Field>
            <Field label="Sub-county">
              <select className={fieldCls} value={subCounty} onChange={(e) => setSubCounty(e.target.value)}>
                {(options?.sub_counties ?? []).map((s) => <option key={s} value={s}>{titleCase(s)}</option>)}
              </select>
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="People ~2 km">
                <input className={fieldCls} type="number" min="1" value={population} onChange={(e) => setPopulation(e.target.value)} />
              </Field>
              <Field label="Growth %/yr">
                <input className={fieldCls} type="number" step="0.1" value={growthPct} onChange={(e) => setGrowthPct(e.target.value)} />
              </Field>
            </div>
            <p className="text-[10px] text-muted -mt-2">
              From Google Earth Engine: <code className="text-white/80">scripts\catchment_for_site.py --lat … --lon …</code>
            </p>
            <Field label="Income segment">
              <select className={fieldCls} value={segment} onChange={(e) => setSegment(e.target.value)}>
                <option value="">Chain's usual</option>
                {(options?.income_segments ?? []).map((s) => <option key={s} value={s}>{titleCase(s)}</option>)}
              </select>
            </Field>
          </>
        )}

        <SectionLabel>Opening plan</SectionLabel>
        <div className="grid grid-cols-2 gap-3 -mt-2">
          <Field label="Delivery (days)">
            <input className={fieldCls} type="number" min="1" max="60" value={restockDays} onChange={(e) => setRestockDays(e.target.value)} />
          </Field>
          <Field label="Lead time">
            <input className={fieldCls} type="number" min="0" max="30" value={leadDays} onChange={(e) => setLeadDays(e.target.value)} />
          </Field>
          <Field label="Service level">
            <select className={fieldCls} value={service} onChange={(e) => setService(e.target.value)}>
              <option value="0.9">90%</option>
              <option value="0.95">95%</option>
              <option value="0.98">98%</option>
            </select>
          </Field>
          <Field label="Blueband facings">
            <input className={fieldCls} type="number" min="1" max="500" value={facings} onChange={(e) => setFacings(e.target.value)} />
          </Field>
        </div>

        {err && <p className="text-bad text-xs">{err}</p>}
        <PrimaryButton onClick={submit} disabled={busy} className="h-[42px] text-left px-4 text-[13px]">
          {busy ? "Planning…" : "Plan outlet"}
        </PrimaryButton>
      </div>

      {/* ---------------- results ---------------- */}
      <div className="min-w-0">
        {mode === "pin" && (
          <div className="mb-5">
            <SiteMap pin={pin} outlets={options?.points ?? []} onPick={pick} />
            {!pin && <p className="mt-2 text-[11px] text-muted">Click where the outlet will open. Grey dots are outlets already on file.</p>}
            {locBusy && <p className="mt-3 text-sm text-muted">Looking up the catchment…</p>}
            {loc && (
              <div className="mt-4">
                <div className="grid grid-cols-4 gap-4">
                  <Stat value={fmtInt(loc.pop_1km)} label="People within 1 km" sub="WorldPop 2026" />
                  <Stat value={fmtInt(loc.pop_2km)} label="People within 2 km" />
                  <Stat value={fmtInt(loc.density_per_km2)} label="People per km²" sub="within 2 km" />
                  <Stat value={`${(loc.built_growth_annual * 100).toFixed(1)}%`} label="Built-up growth / yr" sub="Open Buildings 2016–23" />
                </div>
                <p className="mt-2 text-[11px] text-muted">
                  {loc.nearby.length
                    ? <>Within 3 km: {loc.nearby.slice(0, 6).map((n) => `${n.chain} ${n.branch} (${n.distance_km.toFixed(1)} km)`).join(" · ")}
                        {loc.nearby.length > 6 ? ` and ${loc.nearby.length - 6} more` : ""}</>
                    : "No outlets on file within 3 km."}
                </p>
                {!loc.in_training_range && (
                  <p className="mt-1 text-[11px] text-warn">
                    This catchment is outside the range of the outlets the model learned from, so treat the forecast as rough.
                  </p>
                )}
              </div>
            )}
          </div>
        )}
        {!plan ? (
          mode !== "pin" && <p className="text-sm text-muted">{busy ? "Planning…" : "Choose an outlet or enter a site, then Plan outlet."}</p>
        ) : (
          <>
            <div className="flex items-center gap-3 mb-4">
              <div className="min-w-0">
                <h2 className="text-base font-bold truncate">
                  {plan.chain} {plan.branch ?? (mode === "pin" && pin ? `at ${pin.lat.toFixed(4)}, ${pin.lon.toFixed(4)}` : "(new site)")} · {titleCase(plan.sub_county)}
                </h2>
                <p className="text-[11px] text-muted">
                  {fmtPop(plan.catchment_pop_2026)} people in the distance-weighted catchment · built-up area growing{" "}
                  {(plan.built_growth_annual * 100).toFixed(1)}%/yr · {titleCase(plan.dominant_income_segment)} income
                </p>
              </div>
              <PrimaryButton onClick={exportCsv} className="ml-auto h-9 px-4">Export</PrimaryButton>
            </div>

            <div className="grid grid-cols-4 gap-4 mb-5">
              <Stat value={Math.round(plan.total_units_per_week)} label="Weekly demand" sub="units, typical week" />
              <Stat value={plan.opening_stock_total} label="Opening order" sub={`covers ${plan.assumptions.cover_weeks} weeks + safety`} />
              <Stat value={plan.facings_total} label="Blueband facings" sub={`across ${plan.skus.length} SKUs`} />
              <Stat
                value={bench ? `${Math.round(bench.bb_share_pct)}%` : "—"}
                label="Expected share of shelf"
                sub={bench ? `${benchLabel} · OSA ${Math.round(bench.osa_pct)}%` : "no comparable outlets"}
              />
            </div>

            <div className="rounded-card bg-card px-6 pt-5 pb-3 overflow-x-auto">
             <div className="min-w-[720px]">
              <div className={`grid ${COLS} pb-3 border-b border-line text-[11px] font-semibold uppercase tracking-wide text-muted`}>
                <span>SKU</span>
                <span>Weekly demand</span>
                <span>Opening stock</span>
                <span>Facings</span>
                <span>Share of demand</span>
              </div>
              {plan.skus.map((s) => (
                <div key={s.sku} className={`grid ${COLS} items-center h-[52px] border-b border-line last:border-b-0`}>
                  <span className="text-[13px] font-bold">{s.sku}</span>
                  <span className="text-[13px]">{s.predicted_units_per_week.toFixed(1)} units</span>
                  <span className="text-[13px]">
                    <span className="font-semibold">{s.opening_stock_units}</span>
                    <span className="text-muted"> (incl. {s.safety_stock_units} safety)</span>
                  </span>
                  <span className="text-[13px] font-semibold">{s.facings}</span>
                  <div className="flex items-center gap-2">
                    <div className="w-[110px] h-1.5 rounded-full bg-track overflow-hidden">
                      <div className="h-full rounded-full bg-info" style={{ width: `${(100 * s.predicted_units_per_week) / maxDemand}%` }} />
                    </div>
                    <span className="text-[11px] text-muted">
                      {Math.round((100 * s.predicted_units_per_week) / plan.total_units_per_week)}%
                    </span>
                  </div>
                </div>
              ))}
             </div>
            </div>

            <p className="mt-3 text-[11px] text-muted leading-relaxed">
              Demand: new-outlet XGBoost model (chain, sub-county, income and the site's satellite catchment; no sales history).
              Opening stock = demand × {plan.assumptions.cover_weeks} weeks (delivery every {plan.assumptions.restock_days} days
              + {plan.assumptions.lead_time_days} days lead time) + safety stock for a {Math.round(plan.assumptions.service_level * 100)}%
              chance of not running out (z = {plan.assumptions.z}, model error ±{Math.round(plan.assumptions.model_relative_error * 100)}%).
              Facings split in proportion to demand. Share of shelf and OSA are what comparable outlets achieve over the last{" "}
              {plan.assumptions.benchmark_window_days} days.
            </p>
          </>
        )}
      </div>
    </div>
  );
}
