"""
app/ml/shelf_opportunities.py
===============================
"What if the shelf were better?" -- uplift estimates from the shelf-aware XGBoost model.
Each scenario scores next week twice with the SAME model: once as the shelf is now, once with
one shelf lever moved to a target. The difference is the uplift. (Same counterfactual method
as /api/forecast/with-promo, just a shelf lever instead of a promo.)

Kinds:
  sos           Blueband share of the spreads shelf at a branch -> target = the chain's
                top-quartile branch, at least +5 points (cap 70%). Branch-level, all SKUs summed.
  planogram     Planogram compliance at a branch -> target 90% (or +5 if already >= 85%, cap 98%).
  availability  A SKU that was off the shelf part of last week -> units lost if that repeats,
                vs fully stocked. One row per branch x SKU.

Current shelf values come from the latest week of load_shelf_history() (simulated now;
Firebase audits later). Uplifts are >= 0 by construction: the model is trained with monotone
constraints on these features.
"""

import re
import time

import numpy as np

from app.ml import demand_model
from app.ml.registry import registry

CACHE_SECONDS = 300
_cache = {"at": 0.0, "rows": []}


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def available() -> bool:
    return registry.ready and demand_model._uses_shelf()


def _scenarios():
    base = demand_model.next_week_frame()
    if base is None:
        return []
    base_units = registry.predict(base)
    base = base.assign(units=base_units, branch_name=base["chain"].astype(str) + " " + base["branch"].astype(str))
    rows = []

    # --- share of shelf, per branch ---------------------------------------------------------------
    share = base.groupby(["chain", "branch"], observed=True)["bb_share_pct_week"].first()
    p75 = share.groupby(level="chain", observed=True).transform(lambda s: s.quantile(0.75))
    target = np.minimum(np.maximum(p75, share + 5), 70)
    x = base.copy()
    x["bb_share_pct_week"] = [target[(c, b)] for c, b in zip(base["chain"], base["branch"])]
    gain = registry.predict(x) - base_units
    for (c, b), g in base.assign(gain=gain).groupby(["chain", "branch"], observed=True):
        cur, tgt = share[(c, b)], target[(c, b)]
        rows.append(_row("sos", g, None, cur, tgt, g["units"].sum(), g["gain"].sum(),
                         f"Raise Blueband share of shelf at {g['branch_name'].iloc[0]} from {cur:.0f}% to {tgt:.0f}%"))

    # --- planogram compliance, per branch ---------------------------------------------------------
    plano = base.groupby(["chain", "branch"], observed=True)["planogram_pct_week"].first()
    p_target = np.minimum(np.where(plano < 85, 90, plano + 5), 98)
    p_target = dict(zip(plano.index, p_target))
    x = base.copy()
    x["planogram_pct_week"] = [p_target[(c, b)] for c, b in zip(base["chain"], base["branch"])]
    gain = registry.predict(x) - base_units
    for (c, b), g in base.assign(gain=gain).groupby(["chain", "branch"], observed=True):
        cur, tgt = plano[(c, b)], p_target[(c, b)]
        rows.append(_row("planogram", g, None, cur, tgt, g["units"].sum(), g["gain"].sum(),
                         f"Bring planogram compliance at {g['branch_name'].iloc[0]} from {cur:.0f}% to {tgt:.0f}%"))

    # --- availability, per branch x SKU (only where last week had stock-outs) ---------------------
    x = base.copy()
    x["osa_pct_week"] = base["osa_pct_lag_1w"]
    lost = base_units - registry.predict(x)
    for i in np.flatnonzero(base["osa_pct_lag_1w"].to_numpy() < 100):
        r = base.iloc[[i]]
        osa = float(r["osa_pct_lag_1w"].iloc[0])
        rows.append(_row("availability", r, str(r["sku"].iloc[0]), osa, 100.0,
                         float(r["units"].iloc[0]) - lost[i], lost[i],
                         f"Keep {r['sku'].iloc[0]} on the shelf at {r['branch_name'].iloc[0]} "
                         f"(it was available {osa:.0f}% of last week)"))
    rows.sort(key=lambda r: -r["uplift_units"])
    for i, r in enumerate(rows):
        r["id"] = f"SHELF-{i:04d}"
    return rows


def _row(kind, g, sku, current, target, baseline, uplift, action):
    baseline, uplift = float(baseline), max(float(uplift), 0.0)
    pct = 100 * uplift / baseline if baseline > 0 else 0.0
    name = g["branch_name"].iloc[0]
    return {
        "id": "", "kind": kind, "outlet_id": _slug(name), "branch_name": name,
        "chain": str(g["chain"].iloc[0]), "branch": str(g["branch"].iloc[0]), "sku": sku,
        "current_value": round(float(current), 1), "target_value": round(float(target), 1),
        "baseline_units": round(baseline, 1), "uplift_units": round(uplift, 1), "uplift_pct": round(pct, 1),
        # availability: % is meaningless off a stock-out-depressed baseline, so show units only
        "message": (f"{action} -> about {uplift:.0f} units/week of sales recovered" if kind == "availability"
                    else f"{action} -> about +{pct:.1f}% sales (+{uplift:.0f} units/week)"),
    }


def opportunities(limit: int = 10, kind: str | None = None) -> list[dict]:
    if time.time() - _cache["at"] > CACHE_SECONDS or not _cache["rows"]:
        _cache.update(at=time.time(), rows=_scenarios())
    rows = [r for r in _cache["rows"] if kind in (None, r["kind"])]
    return rows[:limit]
