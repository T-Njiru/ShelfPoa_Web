r"""
compare_random_forest.py  --  Random Forest vs XGBoost on the weekly demand task (report only)
==============================================================================================
Run from backend\ (takes a few minutes):

    .\.venv\Scripts\python.exe compare_random_forest.py

A fair, like-for-like comparison with the deployed XGBoost demand model:
  * same weekly data, same features, same 70 / 15 / 15 split by week (train / val / test),
    all imported from train_xgboost_shelf.py so nothing can drift
  * same target transform (log1p of weekly units) and the same business rules: forecasts can
    only go UP with recent sales, availability, share of shelf and planogram compliance
    (XGBoost monotone_constraints = Random Forest monotonic_cst)
  * both models tuned the same way: a small grid scored on the validation weeks (MAE)
  * scored on the same untouched test weeks, against observed sales AND true demand
  * same rolling-origin cross-validation over the train+val weeks
  * paired bootstrap over outlets for the MAE difference (is the gap real or noise?)

Two comparisons, because the business rules cost the two libraries differently:
  1. DEPLOYABLE  - both models under the rules the app needs (monotone constraints, log1p target),
                   A (sales only) and B (with shelf). This is the like-for-like test.
  2. BEST EFFORT - shelf model B only, no monotone constraints; each model also chooses its target
                   (log1p or raw units) and, for Random Forest, its category encoding (integer codes
                   or one-hot), all on the validation weeks. Shows each library at its best, so the
                   result can't be blamed on a setup that suits XGBoost.

Random Forest has no native categorical support in scikit-learn, so chain / branch / sku / ... are
given as integer codes (comparison 1) or codes/one-hot, whichever validates better (comparison 2).
XGBoost uses its native categorical splits.

Nothing the API loads is changed. Writes, for the report:
    app\ml\artifacts\model_comparison_rf_vs_xgb.csv    test-week scores, one row per model
    app\ml\artifacts\model_comparison_rf_vs_xgb.json   everything (grid, CV, bootstrap, timings)
    app\ml\artifacts\model_comparison_rf_vs_xgb.png    MAE / WAPE chart (needs matplotlib)
"""

import json
import time

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.ensemble import RandomForestRegressor

from app.ml.demand_model import CATS, SHELF_FEATURES
from app.ml.registry import DIR as ART
from train_xgboost_shelf import (BASE_FEATURES, CV_FOLDS, GRID, MONOTONE_UP, SEED, SHELF_MODEL_FEATURES,
                                 build_weekly, fit as fit_xgb, scores)

RF_GRID = [dict(max_depth=None, min_samples_leaf=5, max_features=0.5),
           dict(max_depth=None, min_samples_leaf=2, max_features=0.5),
           dict(max_depth=20, min_samples_leaf=5, max_features=0.33),
           dict(max_depth=20, min_samples_leaf=10, max_features=0.5),
           dict(max_depth=12, min_samples_leaf=5, max_features=0.7),
           dict(max_depth=None, min_samples_leaf=5, max_features=1.0)]
RF_TREES = 300
BOOTSTRAP_REPS = 2000
TARGETS = {"log1p": (np.log1p, np.expm1), "raw": (lambda y: y, lambda y: y)}
BEST_EFFORT_RF_GRID = [RF_GRID[2], dict(max_depth=None, min_samples_leaf=3, max_features=0.5),
                       dict(max_depth=None, min_samples_leaf=3, max_features=1.0)]


# ----------------------------------------------------------------------------- Random Forest
def as_numeric(df, features, encoding="codes"):
    """Categoricals -> integer codes (same category lists as XGBoost, so codes are stable), or one-hot
    columns (fixed column set, since every frame shares the same category lists)."""
    X = df[features].copy()
    cats = [c for c in features if isinstance(X[c].dtype, pd.CategoricalDtype)]
    if encoding == "onehot":
        return pd.get_dummies(X, columns=cats, dtype=float)
    for c in cats:
        X[c] = X[c].cat.codes
    return X


def make_rf(features, params, n_trees=RF_TREES, monotone=True):
    mono = [1 if f in MONOTONE_UP else 0 for f in features] if monotone else None
    return RandomForestRegressor(n_estimators=n_trees, monotonic_cst=mono, random_state=SEED,
                                 n_jobs=-1, **params)


def fit_rf_best_effort(features, train, val):
    """No monotone rules; grid over target transform x category encoding x a few RF settings."""
    best = (np.inf, None, None)
    for target, (fwd, back) in TARGETS.items():
        for enc in ("codes", "onehot"):
            for p in BEST_EFFORT_RF_GRID:
                m = make_rf(features, p, monotone=False).fit(as_numeric(train, features, enc), fwd(train["units_sold_week"]))
                mae = np.mean(np.abs(back(m.predict(as_numeric(val, features, enc))) - val["units_sold_week"]))
                if mae < best[0]:
                    best = (mae, p | {"target": target, "encoding": enc}, m)
    print(f"    RF best effort: {best[1]} (validation MAE {best[0]:.3f})")
    return best


def fit_xgb_best_effort(features, train, val):
    """No monotone rules; same XGBoost grid, plus the choice of target transform."""
    best = (np.inf, None, None)
    for target, (fwd, back) in TARGETS.items():
        for p in GRID:
            m = xgb.XGBRegressor(n_estimators=400, tree_method="hist", enable_categorical=True, random_state=SEED,
                                 n_jobs=-1, early_stopping_rounds=25, eval_metric="mae", **p)
            m.fit(train[features], fwd(train["units_sold_week"]),
                  eval_set=[(val[features], fwd(val["units_sold_week"]))], verbose=False)
            mae = np.mean(np.abs(back(m.predict(val[features])) - val["units_sold_week"]))
            if mae < best[0]:
                best = (mae, p | {"target": target, "n_trees": int(m.best_iteration + 1)}, m)
    print(f"    XGBoost best effort: {best[1]} (validation MAE {best[0]:.3f})")
    return best


def fit_rf(features, train, val):
    best = (np.inf, None, None)
    for p in RF_GRID:
        m = make_rf(features, p).fit(as_numeric(train, features), np.log1p(train["units_sold_week"]))
        mae = np.mean(np.abs(np.expm1(m.predict(as_numeric(val, features))) - val["units_sold_week"]))
        print(f"    RF {p}: validation MAE {mae:.3f}")
        if mae < best[0]:
            best = (mae, p, m)
    return best


# ----------------------------------------------------------------------------- shared helpers
def rolling_cv(kind, features, params, n_trees, data, pool_weeks, monotone=True, target="log1p", encoding="codes"):
    """Same rolling-origin CV as train_xgboost_shelf.py: fold i trains on blocks 0..i, tests on i+1."""
    mono = {f: 1 for f in MONOTONE_UP if f in features} if monotone else None
    fwd, back = TARGETS[target]
    blocks = np.array_split(np.array(pool_weeks), CV_FOLDS + 1)
    rows = []
    for i in range(CV_FOLDS):
        tr = data[data.week_idx.isin(np.concatenate(blocks[: i + 1]))]
        te = data[data.week_idx.isin(blocks[i + 1])]
        if kind == "xgb":
            m = xgb.XGBRegressor(n_estimators=n_trees, tree_method="hist", enable_categorical=True,
                                 monotone_constraints=mono, random_state=SEED, n_jobs=-1, **params)
            m.fit(tr[features], fwd(tr["units_sold_week"]))
            pred = back(m.predict(te[features]))
        else:
            m = make_rf(features, params, n_trees, monotone).fit(as_numeric(tr, features, encoding), fwd(tr["units_sold_week"]))
            pred = back(m.predict(as_numeric(te, features, encoding)))
        s = scores(pred, te["units_sold_week"])
        s["fold"] = i + 1
        rows.append(s)
    return pd.DataFrame(rows).set_index("fold")


def paired_bootstrap(err_a, err_b, groups, reps=BOOTSTRAP_REPS):
    """MAE(a) - MAE(b) with a 95% CI, resampling whole outlets (rows from one outlet are correlated).
    Negative = model a is more accurate."""
    rng = np.random.default_rng(SEED)
    d = pd.DataFrame({"a": np.abs(err_a), "b": np.abs(err_b), "g": np.asarray(groups)})
    per = d.groupby("g")[["a", "b"]].agg(["sum", "count"])
    sa, sb, n = per[("a", "sum")].to_numpy(), per[("b", "sum")].to_numpy(), per[("a", "count")].to_numpy()
    k = len(per)
    diffs = np.empty(reps)
    for r in range(reps):
        idx = rng.integers(0, k, k)
        diffs[r] = sa[idx].sum() / n[idx].sum() - sb[idx].sum() / n[idx].sum()
    point = d["a"].mean() - d["b"].mean()
    lo, hi = np.percentile(diffs, [2.5, 97.5])
    return {"mae_diff": float(point), "ci95": [float(lo), float(hi)],
            "share_of_resamples_a_better": float(np.mean(diffs < 0)), "outlets": int(k)}


def timed(fn):
    t = time.perf_counter()
    out = fn()
    return out, time.perf_counter() - t


def save_chart(table, path):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not installed - skipping the chart")
        return
    rows = [r for r in table.index if "-> observed sales" in r]
    labels = [r.replace(" -> observed sales", "").replace("with shelf", "shelf") for r in rows]
    colors = ["#a8a6ad" if r.startswith("Baseline") else "#f4784e" if "XGBoost" in r else "#3a7bd5" for r in rows]
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))
    for ax, metric, unit in zip(axes, ("MAE", "WAPE_pct"), ("units / week", "% of actual sales")):
        vals = table.loc[rows, metric].to_numpy()
        ax.barh(labels[::-1], vals[::-1], color=colors[::-1])
        for y, v in enumerate(vals[::-1]):
            ax.text(v, y, f" {v:.2f}", va="center", fontsize=8)
        ax.set_xlabel(f"{metric.replace('_pct', '')} ({unit}), lower is better")
        ax.spines[["top", "right"]].set_visible(False)
    fig.suptitle("Weekly demand forecast, test weeks: Random Forest (blue) vs XGBoost (orange)")
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)
    print(f"Saved chart -> {path}")


# ----------------------------------------------------------------------------- main
def main():
    agg, _ = build_weekly()
    cats = {c: sorted(agg[c].astype(str).unique()) for c in CATS}
    for c in CATS:
        agg[c] = pd.Categorical(agg[c].astype(str), categories=cats[c])
    weeks = sorted(agg["week_idx"].unique())
    tr_end, va_end = weeks[int(len(weeks) * 0.70)], weeks[int(len(weeks) * 0.85)]
    train = agg[agg.week_idx <= tr_end]
    val = agg[(agg.week_idx > tr_end) & (agg.week_idx <= va_end)]
    test = agg[agg.week_idx > va_end].copy()
    full = test.copy()
    full["osa_pct_week"] = 100.0                      # "if the shelf had been stocked"
    print(f"{len(agg):,} weekly rows, {len(weeks)} weeks | train {len(train):,}  val {len(val):,}  test {len(test):,}")

    models, timings, params = {}, {}, {}
    for tag, feats in (("A sales only", BASE_FEATURES), ("B with shelf", SHELF_MODEL_FEATURES)):
        print(f"\nTuning {tag} ...")
        (_, p, m), t = timed(lambda: fit_xgb(feats, train, val))
        models[f"XGBoost {tag}"], params[f"XGBoost {tag}"] = m, p | {"n_trees": int(m.best_iteration + 1)}
        timings[f"XGBoost {tag}"] = {"tuning_s": t}
        (_, p, m), t = timed(lambda: fit_rf(feats, train, val))
        models[f"Random Forest {tag}"], params[f"Random Forest {tag}"] = m, p | {"n_trees": RF_TREES}
        timings[f"Random Forest {tag}"] = {"tuning_s": t}

    def predict(name, df):
        feats = SHELF_MODEL_FEATURES if "B with shelf" in name else BASE_FEATURES
        m = models[name]
        X = df[feats] if name.startswith("XGBoost") else as_numeric(df, feats)
        out, t = timed(lambda: np.expm1(m.predict(X)))
        timings[name]["predict_test_ms"] = t * 1000
        return out

    preds = {n: predict(n, test) for n in models}
    preds_full = {n: predict(n, full) for n in models if "B with shelf" in n}
    obs, true = test["units_sold_week"].to_numpy(), test["true_demand_week"].to_numpy()

    rows = {"Baseline: last week's sales -> observed sales": scores(test["lag_1w"], obs),
            "Baseline: 3-week rolling mean -> observed sales": scores(test["rolling_mean_3w"], obs)}
    for n in models:
        rows[f"{n} -> observed sales"] = scores(preds[n], obs)
    for n in models:
        if "A sales only" in n:
            rows[f"{n} -> TRUE demand"] = scores(preds[n], true)
    for n in preds_full:
        rows[f"{n} (OSA=100) -> TRUE demand"] = scores(preds_full[n], true)
    table = pd.DataFrame(rows).T.round(3)
    print("\nTest weeks (MAE/RMSE in units/week; WAPE and bias in %):")
    print(table.to_string())

    low = (test["osa_pct_week"] < 100).to_numpy()
    stockout = {n: float(np.mean(np.abs(preds_full[n][low] - true[low]))) for n in preds_full}
    print(f"\nWeeks with a stock-out ({low.sum():,} rows), true-demand MAE at OSA=100: "
          + "  ".join(f"{n}: {v:.3f}" for n, v in stockout.items()))

    # is the gap real? paired bootstrap over outlets, observed sales, shelf-aware models
    outlets = (test["chain"].astype(str) + "|" + test["branch"].astype(str)).to_numpy()
    boot = paired_bootstrap(preds["Random Forest B with shelf"] - obs, preds["XGBoost B with shelf"] - obs, outlets)
    print(f"\nMAE(Random Forest B) - MAE(XGBoost B) = {boot['mae_diff']:+.3f} units/week, "
          f"95% CI [{boot['ci95'][0]:+.3f}, {boot['ci95'][1]:+.3f}] over {boot['outlets']} outlets "
          f"(Random Forest better in {boot['share_of_resamples_a_better'] * 100:.1f}% of resamples)")

    # ---- comparison 2: each library at its best (shelf model B, no monotone rules) ----
    print("\nBest-effort tuning (shelf model B, no monotone rules) ...")
    best_effort = {}
    for name, fitter, kind in (("XGBoost best effort B", fit_xgb_best_effort, "xgb"),
                               ("Random Forest best effort B", fit_rf_best_effort, "rf")):
        (_, p, m), t = timed(lambda: fitter(SHELF_MODEL_FEATURES, train, val))
        back = TARGETS[p["target"]][1]
        X = test[SHELF_MODEL_FEATURES] if kind == "xgb" else as_numeric(test, SHELF_MODEL_FEATURES, p["encoding"])
        Xf = full[SHELF_MODEL_FEATURES] if kind == "xgb" else as_numeric(full, SHELF_MODEL_FEATURES, p["encoding"])
        best_effort[name] = {"model": m, "params": p, "kind": kind,
                             "pred": back(m.predict(X)), "pred_full": back(m.predict(Xf))}
        params[name] = p | ({} if kind == "xgb" else {"n_trees": RF_TREES})
        timings[name] = {"tuning_s": t}
    for name, b in best_effort.items():
        table.loc[f"{name} -> observed sales"] = pd.Series(scores(b["pred"], obs)).round(3)
    for name, b in best_effort.items():
        table.loc[f"{name} (OSA=100) -> TRUE demand"] = pd.Series(scores(b["pred_full"], true)).round(3)
    print(table.loc[[i for i in table.index if "best effort" in i]].to_string())
    boot_best = paired_bootstrap(best_effort["Random Forest best effort B"]["pred"] - obs,
                                 best_effort["XGBoost best effort B"]["pred"] - obs, outlets)
    print(f"Best effort: MAE(Random Forest) - MAE(XGBoost) = {boot_best['mae_diff']:+.3f} units/week, "
          f"95% CI [{boot_best['ci95'][0]:+.3f}, {boot_best['ci95'][1]:+.3f}] "
          f"(Random Forest better in {boot_best['share_of_resamples_a_better'] * 100:.1f}% of resamples)")
    for name, b in best_effort.items():
        stockout[name] = float(np.mean(np.abs(b["pred_full"][low] - true[low])))

    pool = [w for w in weeks if w <= va_end]
    cv = {}
    for n in models:
        kind = "xgb" if n.startswith("XGBoost") else "rf"
        feats = SHELF_MODEL_FEATURES if "B with shelf" in n else BASE_FEATURES
        p = {k: v for k, v in params[n].items() if k != "n_trees"}
        cv[n], t = timed(lambda: rolling_cv(kind, feats, p, params[n]["n_trees"], agg, pool))
        timings[n]["cv_s"] = t
    for n, b in best_effort.items():
        p = {k: v for k, v in b["params"].items() if k not in ("n_trees", "target", "encoding")}
        cv[n], t = timed(lambda: rolling_cv(b["kind"], SHELF_MODEL_FEATURES, p, params[n]["n_trees"], agg, pool,
                                            monotone=False, target=b["params"]["target"],
                                            encoding=b["params"].get("encoding", "codes")))
        timings[n]["cv_s"] = t
    print("\nRolling-origin CV over train+val weeks (observed sales), mean (sd) of 5 folds:")
    for n, c in cv.items():
        print(f"  {n:<30} " + "  ".join(f"{m} {c[m].mean():.3f} ({c[m].std():.3f})" for m in ("MAE", "RMSE", "R2", "WAPE_pct")))

    rf_imp = pd.Series(models["Random Forest B with shelf"].feature_importances_,
                       index=SHELF_MODEL_FEATURES).sort_values(ascending=False)
    shelf_share = rf_imp[[f for f in SHELF_FEATURES if f in rf_imp.index]].sum() / rf_imp.sum() * 100
    print(f"\nRandom Forest B: shelf features' share of importance (impurity): {shelf_share:.1f}%")
    print("Timings (s):", {n: {k: round(v, 2) for k, v in t.items()} for n, t in timings.items()})

    table.to_csv(ART / "model_comparison_rf_vs_xgb.csv")
    report = {
        "split": {"train_rows": int(len(train)), "val_rows": int(len(val)), "test_rows": int(len(test)),
                  "weeks": int(len(weeks))},
        "hyperparameters": params,
        "random_forest_grid": RF_GRID,
        "test_scores": table.to_dict(orient="index"),
        "stockout_weeks_true_demand_MAE": {"rows": int(low.sum()), **stockout},
        "bootstrap_rf_minus_xgb_shelf_model": boot,
        "bootstrap_rf_minus_xgb_best_effort": boot_best,
        "cv": {n: c.round(4).to_dict(orient="index") for n, c in cv.items()},
        "cv_mean": {n: c[["MAE", "RMSE", "R2", "WAPE_pct"]].mean().round(4).to_dict() for n, c in cv.items()},
        "random_forest_B_importance": rf_imp.round(5).to_dict(),
        "random_forest_B_shelf_importance_share_pct": float(shelf_share),
        "timings_seconds": timings,
        "notes": "Deployable comparison: same monotone constraints, log1p target, split and tuning protocol; "
                 "Random Forest categoricals as integer codes. Best-effort comparison: shelf model only, no "
                 "monotone constraints, target (and RF encoding) chosen on validation. Report only; the API "
                 "still serves XGBoost.",
    }
    with open(ART / "model_comparison_rf_vs_xgb.json", "w") as f:
        json.dump(report, f, indent=2, default=float)
    save_chart(table, ART / "model_comparison_rf_vs_xgb.png")
    print(f"\nSaved -> {ART / 'model_comparison_rf_vs_xgb.csv'} and .json")


if __name__ == "__main__":
    main()
