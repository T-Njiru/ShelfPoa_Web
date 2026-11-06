"""
app/ml/new_outlet.py
====================
Serves the new-outlet model (train_new_outlet_model.py): typical weekly Blueband demand per SKU
for an outlet with NO sales history -- a planned branch, or one Flora doesn't serve yet.

Inputs per request: chain, sub-county, and the location's satellite catchment
(catchment_pop_2026, built_growth_annual). For a candidate site, get those two numbers with
scripts\\catchment_for_site.py --lat .. --lon .. ; for an existing outlet, pass chain + branch
and they are looked up from outlet_catchments.csv (handy for checking the model against reality).

Loaded lazily on first call, separately from the weekly model in registry.py, so a missing
new-outlet model never stops the rest of the API from loading.
"""

import json

import numpy as np
import pandas as pd
import xgboost as xgb

from app.ml.demand_model import load_catchments
from app.ml.registry import DIR

MODEL_PATH = DIR / "new_outlet_model.json"
META_PATH = DIR / "new_outlet_categories.json"
_cache: dict = {}


def available() -> bool:
    return MODEL_PATH.exists() and META_PATH.exists()


def _load():
    if "booster" not in _cache:
        b = xgb.Booster()
        b.load_model(MODEL_PATH)
        with open(META_PATH) as f:
            _cache["meta"] = json.load(f)
        _cache["booster"] = b
    return _cache["booster"], _cache["meta"]


def forecast_new_outlet(chain: str, sub_county: str | None = None, branch: str | None = None,
                        catchment_pop_2026: float | None = None, built_growth_annual: float | None = None,
                        dominant_income_segment: str | None = None, promo_days_in_week: int = 0,
                        mean_discount_pct: float = 0.0) -> dict:
    booster, meta = _load()
    cats = meta["categories"]

    # existing outlet -> look up its catchment + sub-county
    if branch and (catchment_pop_2026 is None or sub_county is None):
        c = load_catchments()
        row = None if c is None else c[(c["chain"] == chain) & (c["branch"] == branch)]
        if row is None or row.empty:
            raise ValueError(f"No catchment on file for {chain} {branch}; pass catchment_pop_2026 "
                             f"and built_growth_annual (scripts/catchment_for_site.py)")
        row = row.iloc[0]
        catchment_pop_2026 = catchment_pop_2026 if catchment_pop_2026 is not None else float(row["catchment_pop_2026"])
        built_growth_annual = built_growth_annual if built_growth_annual is not None else float(row["built_growth_annual"])
        sub_county = sub_county or row["sub_county"]

    if catchment_pop_2026 is None or catchment_pop_2026 <= 0:
        raise ValueError("catchment_pop_2026 must be a positive number")
    if built_growth_annual is None:
        raise ValueError("built_growth_annual is required")
    segment = dominant_income_segment or meta["default_income_segment_by_chain"].get(chain)
    for col, val in (("chain", chain), ("sub_county", sub_county), ("dominant_income_segment", segment)):
        if val not in cats[col]:
            raise ValueError(f"'{val}' is not a known {col}. Options: {', '.join(cats[col])}")

    skus = pd.DataFrame(meta["skus"])
    X = skus.assign(chain=chain, sub_county=sub_county, dominant_income_segment=segment,
                    ses_index_0_100=meta["ses_by_sub_county"][sub_county],
                    promo_days_in_week=promo_days_in_week, mean_discount_pct=mean_discount_pct,
                    frac_school_closed=0.0, frac_reopen_spike=0.0,          # a typical week
                    log_catchment=np.log(catchment_pop_2026), built_growth_annual=built_growth_annual)
    for col in ("chain", "sub_county", "dominant_income_segment", "flavor", "sku"):
        X[col] = pd.Categorical(X[col], categories=cats[col])
    X = X[meta["features"]]
    pred = np.expm1(booster.predict(xgb.DMatrix(X, enable_categorical=True))).clip(min=0)

    per_sku = [{"sku": s, "flavor": f, "pack_size_g": int(p), "predicted_units_per_week": round(float(u), 2)}
               for s, f, p, u in zip(skus["sku"], skus["flavor"], skus["pack_size_g"], pred)]
    return {"chain": chain, "branch": branch, "sub_county": sub_county,
            "dominant_income_segment": segment,
            "catchment_pop_2026": round(float(catchment_pop_2026)),
            "built_growth_annual": round(float(built_growth_annual), 4),
            "total_units_per_week": round(float(pred.sum()), 1),
            "skus": sorted(per_sku, key=lambda r: -r["predicted_units_per_week"])}
