r"""
forecast_feedback_demo.py  --  show the forecast reacting to new sales WITHOUT retraining
==========================================================================================
Place in backend\ and run from there (uses your real app.ml.demand_model + registry):

    .\.venv\Scripts\python.exe forecast_feedback_demo.py
    .\.venv\Scripts\python.exe forecast_feedback_demo.py --factor 0.5          # demand drop
    .\.venv\Scripts\python.exe forecast_feedback_demo.py --chain Naivas --branch Westlands

What it does:
  1. BEFORE: forecasts next week from the current sales history.
  2. Simulates one new completed week of sales = the last completed week x --factor
     (1.5 = a 50% demand surge), for every outlet x SKU.
  3. AFTER: forecasts again with that week added. Same model file, no retraining --
     only lag_1w / lag_2w / rolling_mean_3w change.

Read-only: the new week is added in memory. Your sales CSV and model are not modified.
"""

import argparse

import pandas as pd

from app.ml import demand_model
from app.ml.registry import registry


def simulated_next_week(history: pd.DataFrame, factor: float) -> pd.DataFrame:
    """Copy of the last COMPLETE week, shifted +7 days, units scaled by `factor`."""
    start = history["date"].min()
    week_idx = (history["date"] - start).dt.days // 7
    days_per_week = history.groupby(week_idx)["date"].nunique()
    last_full = days_per_week[days_per_week == 7].index.max()
    complete = history[week_idx <= last_full]            # drop any partial trailing week
    new = complete[week_idx[week_idx <= last_full] == last_full].copy()
    new["date"] = new["date"] + pd.Timedelta(days=7)
    new["units_sold"] = new["units_sold"] * factor  # unrounded, so lag_1w scales exactly
    new[["promo_flag", "discount_pct"]] = 0
    new["promo_type"] = "none"
    return pd.concat([complete, new], ignore_index=True), new["date"].min().date()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--factor", type=float, default=1.5, help="new week's sales vs the last week (1.5 = +50%%)")
    ap.add_argument("--chain")
    ap.add_argument("--branch")
    ap.add_argument("--sku")
    args = ap.parse_args()

    registry.load()
    real_history = demand_model.load_sales_history()
    extended, new_week_start = simulated_next_week(real_history, args.factor)

    before = demand_model.forecast_next_week(args.chain, args.branch, args.sku)
    demand_model.load_sales_history = lambda: extended   # the single swap point, pointed at new data
    after = demand_model.forecast_next_week(args.chain, args.branch, args.sku)
    if not before:
        raise SystemExit("No rows matched - check --chain/--branch/--sku spelling.")

    b = pd.DataFrame(before).set_index(["chain", "branch", "sku"])
    a = pd.DataFrame(after).set_index(["chain", "branch", "sku"])
    t = pd.DataFrame({
        "lag_1w before": b["lag_1w"], "lag_1w after": a["lag_1w"],
        "forecast before": b["predicted_units_next_week"], "forecast after": a["predicted_units_next_week"],
    }).dropna()
    t["change %"] = ((t["forecast after"] / t["forecast before"] - 1) * 100).round(1)

    print(f"Simulated new week starting {new_week_start}: last week's sales x {args.factor}")
    print(f"Forecast week: {before[0]['forecast_week_start']} -> {after[0]['forecast_week_start']}  "
          f"(same model, {registry.n_trees} trees, no retraining)\n")
    print(t.sort_values("forecast before", ascending=False).head(10).round(1).to_string())  # busiest 10
    print(f"\nAll {len(t)} branch-SKUs: total forecast {t['forecast before'].sum():,.0f} -> "
          f"{t['forecast after'].sum():,.0f} units ({(t['forecast after'].sum() / t['forecast before'].sum() - 1) * 100:+.1f}%)")


if __name__ == "__main__":
    main()
