"""
app/ml/outlet_planner.py
=========================
Turns a new-outlet demand forecast (app/ml/new_outlet.py) into an opening plan for the branch:

  opening stock per SKU   enough to cover one restock cycle + lead time, plus safety stock
                              cover_weeks  = (restock_days + lead_time_days) / 7
                              cycle_stock  = d * cover_weeks
                              safety_stock = z * sigma * sqrt(cover_weeks)
                              opening      = ceil(cycle_stock + safety_stock)
                          d = forecast units/week; z from the service level (0.95 -> 1.645);
                          sigma = weekly demand spread = sqrt(d + (k*d)^2): Poisson noise of the
                          sales themselves + the model's own error on unseen outlets
                          (k = 1.25 x held-out outlet MAPE from new_outlet_evaluation.json).
  facings per SKU         Blueband's shelf facings split in proportion to forecast demand
                          (largest-remainder rounding, at least 1 facing per SKU when possible).
  benchmarks              what comparable outlets achieve now, from shelf history (last 28 days):
                          Blueband share of shelf and on-shelf availability, for the same chain
                          (and the same chain in the same sub-county when there are any).

No new model: everything is calculated from the demand forecast and existing history, so the
numbers move with the forecast. Benchmarks reflect the shelf history (simulated until real audits).
"""

import json
import math
from statistics import NormalDist

import pandas as pd

from app.ml import demand_model
from app.ml.registry import DIR

NOT_ON_MARKET = {"BB CHOCO 1Kg", "BB VANILLA 250g"}  # still in the training data, not real products
BENCH_DAYS = 28
_bench_cache: dict = {}


def _model_rel_error() -> float:
    try:
        with open(DIR / "new_outlet_evaluation.json") as f:
            mape = json.load(f)["overall"]["+ catchment"]["outlet_MAPE_pct"]
        return 1.25 * mape / 100.0  # MAE -> standard deviation for a normal error
    except Exception:
        return 0.20


def _allocate_facings(demands: list[float], total: int) -> list[int]:
    n = len(demands)
    if n == 0 or total <= 0:
        return [0] * n
    floor_one = total >= n
    base = [1] * n if floor_one else [0] * n
    remaining = total - sum(base)
    s = sum(demands) or 1.0
    raw = [remaining * d / s for d in demands]
    alloc = [int(math.floor(r)) for r in raw]
    left = remaining - sum(alloc)
    for i in sorted(range(n), key=lambda i: raw[i] - alloc[i], reverse=True)[:left]:
        alloc[i] += 1
    return [b + a for b, a in zip(base, alloc)]


def _benchmarks() -> dict:
    """{(chain, sub_county|None): {"bb_share_pct", "osa_pct", "outlets"}} from the last BENCH_DAYS of shelf history."""
    if "b" in _bench_cache:
        return _bench_cache["b"]
    shelf = demand_model.load_shelf_history()
    out = {}
    if shelf is not None and len(shelf):
        recent = shelf[shelf["date"] > shelf["date"].max() - pd.Timedelta(days=BENCH_DAYS)]
        share = recent.groupby(["chain", "branch", "date"])["sos_pct"].sum().groupby(["chain", "branch"]).mean()
        osa = recent.groupby(["chain", "branch"])["on_shelf"].mean() * 100
        per_outlet = share.to_frame("bb_share_pct").join(osa.rename("osa_pct")).reset_index()
        subs = demand_model.load_catchments()
        if subs is not None:
            per_outlet = per_outlet.merge(subs[["chain", "branch", "sub_county"]], on=["chain", "branch"], how="left")
        for chain, g in per_outlet.groupby("chain"):
            out[(chain, None)] = {"bb_share_pct": round(float(g.bb_share_pct.mean()), 1),
                                  "osa_pct": round(float(g.osa_pct.mean()), 1), "outlets": int(len(g))}
            if "sub_county" in g:
                for sc, gg in g.groupby("sub_county"):
                    out[(chain, sc)] = {"bb_share_pct": round(float(gg.bb_share_pct.mean()), 1),
                                        "osa_pct": round(float(gg.osa_pct.mean()), 1), "outlets": int(len(gg))}
    _bench_cache["b"] = out
    return out


def plan(forecast: dict, restock_days: int = 7, lead_time_days: int = 2,
         service_level: float = 0.95, blueband_facings: int = 40) -> dict:
    """Adds opening stock, safety stock and facings to each SKU of a new-outlet forecast."""
    skus = [s for s in forecast["skus"] if s["sku"] not in NOT_ON_MARKET]
    cover = (restock_days + lead_time_days) / 7.0
    z = NormalDist().inv_cdf(service_level)
    k = _model_rel_error()

    facings = _allocate_facings([s["predicted_units_per_week"] for s in skus], blueband_facings)
    for s, f in zip(skus, facings):
        d = s["predicted_units_per_week"]
        sigma = math.sqrt(d + (k * d) ** 2)
        safety = z * sigma * math.sqrt(cover)
        s["safety_stock_units"] = int(math.ceil(safety))
        s["opening_stock_units"] = int(math.ceil(d * cover + safety))
        s["facings"] = f

    bench = _benchmarks()
    chain_b = bench.get((forecast["chain"], None))
    area_b = bench.get((forecast["chain"], forecast["sub_county"]))

    return {
        **forecast,
        "skus": skus,
        "total_units_per_week": round(sum(s["predicted_units_per_week"] for s in skus), 1),
        "opening_stock_total": sum(s["opening_stock_units"] for s in skus),
        "facings_total": sum(facings),
        "comparable_chain": chain_b,
        "comparable_chain_in_area": area_b,
        "assumptions": {
            "restock_days": restock_days, "lead_time_days": lead_time_days,
            "service_level": service_level, "z": round(z, 3), "cover_weeks": round(cover, 2),
            "model_relative_error": round(k, 3), "blueband_facings": blueband_facings,
            "benchmark_window_days": BENCH_DAYS,
        },
    }
