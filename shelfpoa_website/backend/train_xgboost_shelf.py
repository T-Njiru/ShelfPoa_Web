r"""
train_xgboost_shelf.py  --  retrain the weekly demand model WITH shelf features (OSA, SOS, planogram)
=======================================================================================================
Run from backend\ AFTER simulate_shelf_history.py:

    .\.venv\Scripts\python.exe train_xgboost_shelf.py

Trains two models on the same weeks, same split, same hyperparameter search:
  A  "sales only"   the current feature set
  B  "with shelf"   + osa_pct_week, osa_pct_lag_1w, bb_share_pct_week, planogram_pct_week

Then compares them against TRUE demand (what shoppers wanted, incl. what stock-outs blocked).
A only ever sees censored sales, so it learns stock-outs as "low demand". B, scored with
osa_pct_week = 100, estimates demand if the shelf is kept stocked.

Saves model B as app\ml\artifacts\demand_model_weekly.json (the file registry.py loads).
The previous model + categories are backed up once as *_pre_shelf.json, so you can roll back.
Feature engineering is imported from app.ml.demand_model, so training and serving can't drift.

EVALUATION ADDED (for the report, Chapter 5.4.2) -- training and the saved model are unchanged:
  * dataset summary (rows, weeks, date range, SKUs/outlets)
  * MAE, RMSE, R^2, WAPE and bias on the test weeks
  * naive baselines (last week's sales, 3-week rolling mean)
  * time-aware (rolling-origin) cross-validation over the train+val weeks
  * chosen hyperparameters and number of trees for A and B
  * feature-importance chart (PNG, if matplotlib is installed)
  * everything also saved to model_evaluation_report.json
"""

import json
import shutil

import numpy as np
import pandas as pd
import xgboost as xgb

from app.ml.demand_model import CATS, GROUP_KEYS, SHELF_FEATURES, _aggregate_to_weekly
from app.ml.registry import DIR as ART

SEED = 42
BASE_FEATURES = CATS + ["pack_size_g", "ses_index_0_100", "promo_days_in_week", "mean_discount_pct",
                        "frac_school_closed", "frac_reopen_spike", "lag_1w", "lag_2w", "rolling_mean_3w"]
SHELF_MODEL_FEATURES = BASE_FEATURES + SHELF_FEATURES
GRID = [dict(max_depth=4, learning_rate=0.05, subsample=0.8, colsample_bytree=0.8),
        dict(max_depth=6, learning_rate=0.05, subsample=0.8, colsample_bytree=0.8),
        dict(max_depth=6, learning_rate=0.1, subsample=0.9, colsample_bytree=0.9),
        dict(max_depth=5, learning_rate=0.08, subsample=0.85, colsample_bytree=0.85)]
CV_FOLDS = 5


def build_weekly():
    sales = pd.read_csv(ART / "nairobi_sku_outlet_daily_sales_SHELF.csv", parse_dates=["date"])
    shelf = pd.read_csv(ART / "shelf_history_daily.csv", parse_dates=["date"])
    agg = _aggregate_to_weekly(sales, shelf)

    start = sales["date"].min()
    sales["week_idx"] = (sales["date"] - start).dt.days // 7
    keys = GROUP_KEYS + ["week_idx"]
    true = sales.groupby(keys)["true_demand_units"].sum().rename("true_demand_week")
    active = sales[sales["promo_flag"] == 1]
    promo = active.groupby(keys)["promo_type"].agg(lambda s: s.mode().iloc[0]).rename("dominant_promo_type")
    agg = agg.merge(true.reset_index(), on=keys).merge(promo.reset_index(), on=keys, how="left")
    agg["dominant_promo_type"] = agg["dominant_promo_type"].fillna("none")

    # dataset summary for the report (raw daily file, before weekly aggregation)
    summary = {
        "daily_rows": int(len(sales)),
        "date_from": str(sales["date"].min().date()),
        "date_to": str(sales["date"].max().date()),
        "daily_columns": list(sales.columns),
        "unique_per_group_key": {k: int(sales[k].nunique()) for k in GROUP_KEYS if k in sales.columns},
    }
    return agg.dropna(subset=["lag_1w", "lag_2w", "rolling_mean_3w", "osa_pct_lag_1w"]).reset_index(drop=True), summary


# Business rules the trees must respect: more recent sales, more availability, more share of
# shelf, or better planogram compliance can never LOWER the forecast. Without this, a few
# branch-SKUs gave nonsense what-ifs ("improve the shelf, lose sales"); with it, the
# shelf-opportunity uplifts are always >= 0.
MONOTONE_UP = ["lag_1w", "lag_2w", "rolling_mean_3w",
               "osa_pct_week", "osa_pct_lag_1w", "bb_share_pct_week", "planogram_pct_week"]


def fit(features, train, val):
    best = (np.inf, None, None)
    mono = {f: 1 for f in MONOTONE_UP if f in features}
    for p in GRID:
        m = xgb.XGBRegressor(n_estimators=400, tree_method="hist", enable_categorical=True,
                             monotone_constraints=mono, random_state=SEED, n_jobs=-1,
                             early_stopping_rounds=25, eval_metric="mae", **p)
        m.fit(train[features], np.log1p(train["units_sold_week"]),
              eval_set=[(val[features], np.log1p(val["units_sold_week"]))], verbose=False)
        mae = np.mean(np.abs(np.expm1(m.predict(val[features])) - val["units_sold_week"]))
        if mae < best[0]:
            best = (mae, p, m)
    return best


def scores(pred, actual):
    """MAE, RMSE, R^2, WAPE (% of total actual) and bias, all in units/week."""
    pred = np.asarray(pred, dtype=float)
    actual = np.asarray(actual, dtype=float)
    err = pred - actual
    ss_res = np.sum(err ** 2)
    ss_tot = np.sum((actual - actual.mean()) ** 2)
    return {"MAE": np.mean(np.abs(err)),
            "RMSE": np.sqrt(np.mean(err ** 2)),
            "R2": 1 - ss_res / ss_tot if ss_tot else np.nan,
            "WAPE_pct": np.sum(np.abs(err)) / actual.sum() * 100,
            "bias_pct": (pred.sum() / actual.sum() - 1) * 100}


def rolling_cv(features, params, n_trees, data, pool_weeks):
    """Time-aware CV: split the train+val weeks into CV_FOLDS+1 consecutive blocks;
    fold i trains on blocks 0..i and tests on block i+1 (never trains on the future).
    Uses the hyperparameters and tree count chosen in the main run, so it measures stability."""
    mono = {f: 1 for f in MONOTONE_UP if f in features}
    blocks = np.array_split(np.array(pool_weeks), CV_FOLDS + 1)
    rows = []
    for i in range(CV_FOLDS):
        tr_w = np.concatenate(blocks[: i + 1])
        te_w = blocks[i + 1]
        tr = data[data.week_idx.isin(tr_w)]
        te = data[data.week_idx.isin(te_w)]
        m = xgb.XGBRegressor(n_estimators=n_trees, tree_method="hist", enable_categorical=True,
                             monotone_constraints=mono, random_state=SEED, n_jobs=-1, **params)
        m.fit(tr[features], np.log1p(tr["units_sold_week"]))
        s = scores(np.expm1(m.predict(te[features])), te["units_sold_week"])
        s.update(fold=i + 1, train_weeks=len(tr_w), test_weeks=len(te_w), test_rows=len(te))
        rows.append(s)
    return pd.DataFrame(rows).set_index("fold")


def save_importance_chart(imp, path):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not installed - skipping the chart (pip install matplotlib to get it)")
        return
    top = imp.head(15)[::-1]
    shelf = set(SHELF_FEATURES)
    colors = ["#f4784e" if f in shelf else "#5b6b8c" for f in top.index]
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.barh(top.index, top.values, color=colors)
    ax.set_xlabel("Importance (gain)")
    ax.set_title("Model B feature importance (orange = shelf features)")
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)
    print(f"Saved chart -> {path}")


def main():
    agg, summary = build_weekly()

    # category sets fixed at training time, shared by both models and by serving
    cats = {c: sorted(agg[c].astype(str).unique()) for c in CATS}
    cats["dominant_promo_type"] = sorted(set(cats["dominant_promo_type"]) | {"none"})
    for c in CATS:
        agg[c] = pd.Categorical(agg[c].astype(str), categories=cats[c])

    weeks = sorted(agg["week_idx"].unique())
    tr_end, va_end = weeks[int(len(weeks) * 0.70)], weeks[int(len(weeks) * 0.85)]
    train, val = agg[agg.week_idx <= tr_end], agg[(agg.week_idx > tr_end) & (agg.week_idx <= va_end)]
    test = agg[agg.week_idx > va_end].copy()
    print(f"{len(agg):,} weekly rows, {len(weeks)} weeks | train {len(train):,}  val {len(val):,}  test {len(test):,}")

    print("\nDataset summary:")
    print(f"  daily rows {summary['daily_rows']:,}  |  {summary['date_from']} to {summary['date_to']}")
    for k, v in summary["unique_per_group_key"].items():
        print(f"  unique {k}: {v}")
    print(f"  daily columns: {', '.join(summary['daily_columns'])}")

    _, pa, model_a = fit(BASE_FEATURES, train, val)
    _, pb, model_b = fit(SHELF_MODEL_FEATURES, train, val)
    trees_a, trees_b = model_a.best_iteration + 1, model_b.best_iteration + 1
    print(f"\nChosen hyperparameters  A: {pa} ({trees_a} trees)   B: {pb} ({trees_b} trees)")

    full = test.copy()
    full["osa_pct_week"] = 100.0                                   # "if the shelf had been stocked"
    pred_a = np.expm1(model_a.predict(test[BASE_FEATURES]))
    pred_b_actual = np.expm1(model_b.predict(test[SHELF_MODEL_FEATURES]))
    pred_b_full = np.expm1(model_b.predict(full[SHELF_MODEL_FEATURES]))

    rows = {
        "Baseline: last week's sales -> observed sales": scores(test["lag_1w"], test["units_sold_week"]),
        "Baseline: 3-week rolling mean -> observed sales": scores(test["rolling_mean_3w"], test["units_sold_week"]),
        "A sales only -> observed sales": scores(pred_a, test["units_sold_week"]),
        "B with shelf (actual OSA) -> observed sales": scores(pred_b_actual, test["units_sold_week"]),
        "A sales only -> TRUE demand": scores(pred_a, test["true_demand_week"]),
        "B with shelf (OSA=100) -> TRUE demand": scores(pred_b_full, test["true_demand_week"]),
    }
    report = pd.DataFrame(rows).T.round(3)
    print("\nTest weeks (MAE/RMSE in units/week; WAPE and bias in %):")
    print(report.to_string())
    low = test["osa_pct_week"] < 100
    so_a = np.mean(np.abs(pred_a[low] - test['true_demand_week'][low]))
    so_b = np.mean(np.abs(pred_b_full[low] - test['true_demand_week'][low]))
    print(f"\nWeeks with a stock-out ({low.sum():,} rows): true-demand MAE  A {so_a:.2f}  vs  B {so_b:.2f}")

    # time-aware cross-validation over the train+val weeks (test weeks stay untouched)
    pool = [w for w in weeks if w <= va_end]
    cv_a = rolling_cv(BASE_FEATURES, pa, trees_a, agg, pool)
    cv_b = rolling_cv(SHELF_MODEL_FEATURES, pb, trees_b, agg, pool)
    for name, cv in (("A sales only", cv_a), ("B with shelf", cv_b)):
        print(f"\nRolling-origin CV, {name} (observed sales):")
        print(cv.round(3).to_string())
        print("  mean " + "  ".join(f"{m} {cv[m].mean():.3f} (sd {cv[m].std():.3f})" for m in ("MAE", "RMSE", "R2")))

    imp = pd.Series(model_b.feature_importances_, index=SHELF_MODEL_FEATURES).sort_values(ascending=False)
    print("\nModel B feature importance (gain):\n" + imp.round(4).to_string())
    shelf_share = imp[[f for f in SHELF_FEATURES if f in imp.index]].sum() / imp.sum() * 100
    print(f"Shelf features' share of total importance: {shelf_share:.1f}%")

    for name in ("demand_model_weekly.json", "training_categories.json"):
        backup = ART / name.replace(".json", "_pre_shelf.json")
        if (ART / name).exists() and not backup.exists():
            shutil.copy(ART / name, backup)
    model_b.get_booster().save_model(str(ART / "demand_model_weekly.json"))
    with open(ART / "training_categories.json", "w") as f:
        json.dump(cats, f, indent=2)
    report.to_csv(ART / "model_evaluation_shelf_vs_sales_only.csv")
    imp.to_csv(ART / "feature_importance_shelf.csv", header=["importance"])
    save_importance_chart(imp, ART / "feature_importance_shelf.png")

    full_report = {
        "dataset": summary | {"weekly_rows": int(len(agg)), "weeks": int(len(weeks)),
                              "train_rows": int(len(train)), "val_rows": int(len(val)), "test_rows": int(len(test))},
        "hyperparameters": {"A": pa | {"n_trees": int(trees_a)}, "B": pb | {"n_trees": int(trees_b)}},
        "test_scores": report.to_dict(orient="index"),
        "stockout_weeks_true_demand_MAE": {"rows": int(low.sum()), "A": float(so_a), "B": float(so_b)},
        "cv_A": cv_a.round(4).to_dict(orient="index"),
        "cv_B": cv_b.round(4).to_dict(orient="index"),
        "feature_importance_B": imp.round(5).to_dict(),
        "shelf_feature_importance_share_pct": float(shelf_share),
    }
    with open(ART / "model_evaluation_report.json", "w") as f:
        json.dump(full_report, f, indent=2, default=float)
    print(f"\nSaved full evaluation -> {ART / 'model_evaluation_report.json'}")

    print(f"\nSaved model B ({trees_b} trees, {pb}) -> {ART / 'demand_model_weekly.json'}")
    print("Backups: demand_model_weekly_pre_shelf.json, training_categories_pre_shelf.json")
    print("Restart uvicorn to load it.")


if __name__ == "__main__":
    main()