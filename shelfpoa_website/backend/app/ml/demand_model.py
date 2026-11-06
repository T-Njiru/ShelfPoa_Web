"""
app/ml/demand_model.py
==========================
Feature engineering for weekly demand forecasting. Does NOT load its own
model -- uses registry.predict() so there's exactly one Booster in memory,
loaded once in Registry.load(), matching how basket.py already works.

CATEGORY PINNING: Registry.predict() does `df[CATS] = df[CATS].astype(
"category")` with no explicit categories list -- on an ALREADY-categorical
column this is a safe no-op (verified), but on a plain string column it
would re-infer categories from whatever's in that call's data, which can
silently misalign the integer codes XGBoost's trees actually split on if
the inference-time value set differs from training. So the columns are
pinned to the exact training-time category list HERE, before registry.predict()
ever sees them -- registry.py itself doesn't need to change.

SHELF FEATURES (added with train_xgboost_shelf.py): if the loaded model was trained with
SHELF_FEATURES, weekly OSA / Blueband share of shelf / planogram values are merged in from load_shelf_history().
The forecast assumes the SKU is FULLY on shelf next week (osa_pct_week = 100 by default), so
predicted_units_next_week = demand if the shelf is kept stocked -- not sales dragged down by
last week's stock-outs. SOS and planogram are carried forward from the latest week.
An older model without shelf features keeps working unchanged.

CATCHMENT FEATURES (added with resimulate_demand.py): log_catchment (people living within ~2 km,
WorldPop R2025A) and built_growth_annual (area building growth, Open Buildings 2016-2023) come
from outlet_catchments.csv and are merged in per outlet. They let the model tell apart outlets
in the same sub-county. A model trained without them ignores the extra columns.
"""

import json
from datetime import date, timedelta

import numpy as np
import pandas as pd

from app.ml.registry import registry, DIR as REGISTRY_DIR

CATS = ["chain", "branch", "sub_county", "dominant_income_segment",
        "flavor", "sku", "dominant_promo_type"]
SHELF_FEATURES = ["osa_pct_week", "osa_pct_lag_1w", "bb_share_pct_week", "planogram_pct_week"]
GROUP_KEYS = ["chain", "branch", "sku"]

CATEGORIES_PATH = REGISTRY_DIR / "training_categories.json"
SALES_CSV_PATH = REGISTRY_DIR / "nairobi_sku_outlet_daily_sales_SHELF.csv"  # observed sales incl. stock-outs
if not SALES_CSV_PATH.exists():
    SALES_CSV_PATH = REGISTRY_DIR / "nairobi_sku_outlet_daily_sales_EXTENDED.csv"
SHELF_CSV_PATH = REGISTRY_DIR / "shelf_history_daily.csv"
CATCHMENTS_PATH = REGISTRY_DIR / "outlet_catchments.csv"
CATCHMENT_FEATURES = ["log_catchment", "built_growth_annual"]

with open(CATEGORIES_PATH) as f:
    _category_reference = json.load(f)


def _pin_categories(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in CATS:
        df[col] = pd.Categorical(df[col], categories=_category_reference[col])
        if df[col].isna().any():
            raise ValueError(f"Unrecognized value(s) in '{col}' -- not in training categories. "
                              f"Retrain before serving this entity.")
    return df


def load_sales_history() -> pd.DataFrame:
    """TODO once real data exists: swap this for FFG sales instead of the CSV. Everything
    downstream only cares about getting back a dataframe with these columns: date, chain,
    branch, sub_county, dominant_income_segment, ses_index_0_100, flavor, pack_size_g, sku,
    promo_flag, promo_type, discount_pct, units_sold."""
    return pd.read_csv(SALES_CSV_PATH, parse_dates=["date"])


def load_shelf_history() -> pd.DataFrame | None:
    """TODO once real audits exist: build this from Firebase osa_reports / sos_audits / audits
    (one row per date x chain x branch x sku). Columns: date, chain, branch, sku,
    on_shelf (0/1), sos_pct, planogram_pct. None if there is no shelf history."""
    if not SHELF_CSV_PATH.exists():
        return None
    return pd.read_csv(SHELF_CSV_PATH, parse_dates=["date"])


def load_catchments() -> pd.DataFrame | None:
    """One row per outlet: chain, branch, log_catchment, built_growth_annual (+ lat/lon, source).
    Built offline from Google Earth Engine (Google_Earth_proposition sandbox / catchment_for_site.py).
    None if the file is missing."""
    if not CATCHMENTS_PATH.exists():
        return None
    c = pd.read_csv(CATCHMENTS_PATH)
    c["log_catchment"] = np.log(c["catchment_pop_2026"])
    return c


def add_catchment_features(df: pd.DataFrame) -> pd.DataFrame:
    """Merge CATCHMENT_FEATURES onto any frame with chain + branch. Shared by both models."""
    c = load_catchments()
    if c is None:
        return df
    return df.merge(c[["chain", "branch"] + CATCHMENT_FEATURES], on=["chain", "branch"], how="left")


def weekly_shelf_features(shelf: pd.DataFrame, start: pd.Timestamp) -> pd.DataFrame:
    """Daily shelf rows -> one row per (chain, branch, sku, week_idx) with SHELF_FEATURES.
    Shared by training and serving so both compute them identically."""
    s = shelf.copy()
    s["week_idx"] = (s["date"] - start).dt.days // 7
    w = s.groupby(GROUP_KEYS + ["week_idx"]).agg(
        osa_pct_week=("on_shelf", "mean"), sos_pct_week=("sos_pct", "mean"),
        planogram_pct_week=("planogram_pct", "mean")).reset_index()
    w["osa_pct_week"] *= 100
    # Blueband's share of the whole spreads shelf at the branch (sum of its SKUs' shares) -- the
    # same brand-level number the mobile app's SoS capture produces (sos_audits.coverageScore)
    w["bb_share_pct_week"] = w.groupby(["chain", "branch", "week_idx"])["sos_pct_week"].transform("sum")
    w = w.sort_values(GROUP_KEYS + ["week_idx"])
    w["osa_pct_lag_1w"] = w.groupby(GROUP_KEYS)["osa_pct_week"].shift(1)
    return w


def _uses_shelf() -> bool:
    return all(f in registry.booster.feature_names for f in SHELF_FEATURES)


def _aggregate_to_weekly(df: pd.DataFrame, shelf: pd.DataFrame | None = None) -> pd.DataFrame:
    start = df["date"].min()
    df = df.copy()
    df["days_since_start"] = (df["date"] - start).dt.days
    df["week_idx"] = df["days_since_start"] // 7
    df["week_start"] = start + pd.to_timedelta(df["week_idx"] * 7, unit="D")

    school_close, school_reopen = date(2026, 7, 31), date(2026, 8, 24)
    spike_lo = pd.Timestamp(school_reopen) - pd.Timedelta(days=4)
    spike_hi = pd.Timestamp(school_reopen) + pd.Timedelta(days=4)
    df["is_closed_day"] = ((df["date"].dt.date >= school_close) & (df["date"] < spike_lo)).astype(int)
    df["is_spike_day"] = ((df["date"] >= spike_lo) & (df["date"] <= spike_hi)).astype(int)

    week_day_counts = df.groupby("week_idx")["date"].nunique()
    complete_weeks = week_day_counts[week_day_counts == 7].index
    df = df[df["week_idx"].isin(complete_weeks)]

    agg = df.groupby(GROUP_KEYS + ["week_idx"]).agg(
        week_start=("week_start", "first"), sub_county=("sub_county", "first"),
        dominant_income_segment=("dominant_income_segment", "first"),
        ses_index_0_100=("ses_index_0_100", "first"), flavor=("flavor", "first"),
        pack_size_g=("pack_size_g", "first"), units_sold_week=("units_sold", "sum"),
        promo_days_in_week=("promo_flag", "sum"), mean_discount_pct=("discount_pct", "mean"),
        frac_school_closed=("is_closed_day", "mean"), frac_reopen_spike=("is_spike_day", "mean"),
    ).reset_index().sort_values(GROUP_KEYS + ["week_idx"])

    g = agg.groupby(GROUP_KEYS)["units_sold_week"]
    agg["lag_1w"] = g.shift(1)
    agg["lag_2w"] = g.shift(2)
    agg["rolling_mean_3w"] = g.transform(lambda x: x.shift(1).rolling(3).mean())

    if shelf is not None:
        agg = agg.merge(weekly_shelf_features(shelf, start), on=GROUP_KEYS + ["week_idx"], how="left")
    return add_catchment_features(agg)


def forecast_next_week(chain: str | None = None, branch: str | None = None,
                        sku: str | None = None, planned_promo: dict | None = None,
                        planned_osa_pct: float = 100.0) -> list[dict]:
    next_week = next_week_frame(chain, branch, sku, planned_promo, planned_osa_pct)
    if next_week is None:
        return []
    next_week["predicted_units_next_week"] = registry.predict(next_week)
    next_week["forecast_week_start"] = (next_week["week_start"] + timedelta(days=7)).dt.date.astype(str)

    out_cols = ["chain", "branch", "sub_county", "sku", "flavor", "pack_size_g",
                "forecast_week_start", "lag_1w", "rolling_mean_3w", "predicted_units_next_week"]
    return next_week[out_cols].round(2).to_dict(orient="records")


def next_week_frame(chain: str | None = None, branch: str | None = None,
                    sku: str | None = None, planned_promo: dict | None = None,
                    planned_osa_pct: float = 100.0) -> pd.DataFrame | None:
    """Model-ready feature rows for next week (categories pinned), or None if nothing matches.
    Used by forecast_next_week() and by the what-if scenarios in shelf_opportunities.py."""
    use_shelf = _uses_shelf()
    shelf = load_shelf_history() if use_shelf else None
    if use_shelf and shelf is None:
        raise RuntimeError("The model uses shelf features but shelf_history_daily.csv is missing - "
                           "run simulate_shelf_history.py (or connect Firebase audits).")
    history = load_sales_history()
    agg = _aggregate_to_weekly(history, shelf)

    latest_week = agg["week_idx"].max()
    latest = agg[agg["week_idx"] == latest_week].copy()
    if chain:
        latest = latest[latest["chain"] == chain]
    if branch:
        latest = latest[latest["branch"] == branch]
    if sku:
        latest = latest[latest["sku"] == sku]
    if len(latest) == 0:
        return None

    next_week = latest.copy()
    next_week["lag_2w"] = latest["lag_1w"]
    next_week["lag_1w"] = latest["units_sold_week"]
    next_week["rolling_mean_3w"] = (latest["units_sold_week"] + latest["lag_1w"] + latest["lag_2w"]) / 3
    if use_shelf:
        next_week["osa_pct_lag_1w"] = latest["osa_pct_week"]   # last week's availability
        next_week["osa_pct_week"] = planned_osa_pct            # assume the shelf is kept stocked
        # bb_share_pct_week / planogram_pct_week: carried forward from the latest week

    p = planned_promo or {}
    next_week["promo_days_in_week"] = p.get("promo_days_in_week", 0)
    next_week["mean_discount_pct"] = p.get("mean_discount_pct", 0.0)
    next_week["dominant_promo_type"] = p.get("dominant_promo_type", "none")

    return _pin_categories(next_week)