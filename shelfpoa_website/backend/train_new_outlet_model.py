r"""
train_new_outlet_model.py  --  demand model for outlets with NO sales history (site selection)
==================================================================================================
Run from backend\  AFTER simulate_shelf_history.py:

    .\.venv\Scripts\python.exe train_new_outlet_model.py

Why: the weekly model (train_xgboost_shelf.py) forecasts from last weeks' sales, so it can't say
anything about an outlet that hasn't opened yet or that Flora doesn't serve. This model predicts
typical weekly Blueband demand per SKU from what is known about ANY location:

    chain, sub-county, income segment, SES index        (who shops there)
    log_catchment, built_growth_annual                  (satellite: how many people live within
                                                         ~2 km, how fast the area is building up)
    SKU, flavor, pack size                              (what is sold)
    promo days / discount, school-calendar fractions    (week conditions; 0 for a "typical week")

No lags and no branch -- by design, so it works for a branch it has never seen.
Target is TRUE demand (true_demand_units): what would sell if the shelf were kept stocked.

Evaluation (for the report): 5-fold GroupKFold by outlet -- every fold's outlets are never seen
in training, which is exactly the new-outlet situation. Same model with vs without the
satellite features, scored per outlet (total weekly demand across SKUs).

Outputs (app\ml\artifacts\):
    new_outlet_model.json            booster trained on all outlets (loaded by app\ml\new_outlet.py)
    new_outlet_categories.json       category sets + feature list + defaults for serving
    new_outlet_evaluation.json       cross-validation results
"""

import json

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.model_selection import GroupKFold

from app.ml.demand_model import CATCHMENT_FEATURES, _aggregate_to_weekly
from app.ml.registry import DIR as ART

SEED = 42
N_FOLDS = 5
CATS = ["chain", "sub_county", "dominant_income_segment", "flavor", "sku"]
BASE = CATS + ["ses_index_0_100", "pack_size_g", "promo_days_in_week", "mean_discount_pct",
               "frac_school_closed", "frac_reopen_spike"]
FULL = BASE + CATCHMENT_FEATURES
PARAMS = dict(n_estimators=400, max_depth=5, learning_rate=0.05, subsample=0.8, colsample_bytree=0.8,
              tree_method="hist", enable_categorical=True, random_state=SEED, n_jobs=-1)


def build_weekly():
    sales = pd.read_csv(ART / "nairobi_sku_outlet_daily_sales_SHELF.csv", parse_dates=["date"])
    demand = sales.drop(columns="units_sold").rename(columns={"true_demand_units": "units_sold"})
    agg = _aggregate_to_weekly(demand)      # also merges the catchment features
    if agg[CATCHMENT_FEATURES].isna().any().any():
        raise SystemExit("Some outlets have no catchment -- check app\\ml\\artifacts\\outlet_catchments.csv")
    agg["outlet"] = agg["chain"] + " | " + agg["branch"]
    return agg


def model(features):
    mono = {"log_catchment": 1} if "log_catchment" in features else {}
    return xgb.XGBRegressor(monotone_constraints=mono, **PARAMS)


def outlet_scores(df, pred):
    """Per outlet: mean weekly demand summed across SKUs, predicted vs actual."""
    o = (df.assign(pred=pred).groupby(["outlet", "week_idx"])[["units_sold_week", "pred"]].sum()
         .groupby("outlet").mean())
    err = o["pred"] - o["units_sold_week"]
    return {"outlet_MAE": float(err.abs().mean()),
            "outlet_MAPE_pct": float((err.abs() / o["units_sold_week"]).mean() * 100),
            "outlet_corr": float(o["pred"].corr(o["units_sold_week"])),
            "row_MAE": float(np.mean(np.abs(pred - df["units_sold_week"])))}


def main():
    agg = build_weekly()
    cats = {c: sorted(agg[c].astype(str).unique()) for c in CATS}
    for c in CATS:
        agg[c] = pd.Categorical(agg[c].astype(str), categories=cats[c])
    y = np.log1p(agg["units_sold_week"])
    print(f"{len(agg):,} outlet-SKU-weeks | {agg['outlet'].nunique()} outlets | {agg['week_idx'].nunique()} weeks")

    # cross-validation: hold out whole outlets
    oof = {"baseline": np.zeros(len(agg)), "+ catchment": np.zeros(len(agg))}
    folds = []
    for k, (tr, te) in enumerate(GroupKFold(N_FOLDS).split(agg, groups=agg["outlet"]), 1):
        for name, feats in (("baseline", BASE), ("+ catchment", FULL)):
            m = model(feats).fit(agg.iloc[tr][feats], y.iloc[tr])
            oof[name][te] = np.expm1(m.predict(agg.iloc[te][feats])).clip(min=0)
            s = outlet_scores(agg.iloc[te], oof[name][te])
            folds.append({"fold": k, "model": name, **s})
    folds = pd.DataFrame(folds)
    overall = {name: outlet_scores(agg, p) for name, p in oof.items()}
    wins = int((folds.pivot(index="fold", columns="model", values="outlet_MAE")
                .eval("`+ catchment` < baseline")).sum())

    print("\nOutlet holdout (outlets never seen in training):")
    print(pd.DataFrame(overall).T.round(3).to_string())
    print(f"\n+ catchment beats baseline in {wins}/{N_FOLDS} folds (outlet MAE)")
    b, c = overall["baseline"], overall["+ catchment"]
    print(f"Outlet weekly-demand error: {b['outlet_MAPE_pct']:.1f}% -> {c['outlet_MAPE_pct']:.1f}%  "
          f"(MAE {100 * (c['outlet_MAE'] / b['outlet_MAE'] - 1):+.1f}%)")

    # final model on all outlets
    final = model(FULL).fit(agg[FULL], y)
    imp = pd.Series(final.feature_importances_, index=FULL).sort_values(ascending=False)
    print("\nFeature importance (final model):\n" + imp.round(4).to_string())

    final.get_booster().save_model(str(ART / "new_outlet_model.json"))
    sku_meta = (agg[["sku", "flavor", "pack_size_g"]].astype({"sku": str, "flavor": str})
                .drop_duplicates().sort_values("sku").to_dict(orient="records"))
    ses = agg[["sub_county", "ses_index_0_100"]].astype({"sub_county": str}).drop_duplicates()
    seg = (agg[["chain", "outlet", "dominant_income_segment"]].drop_duplicates()
           .astype(str).groupby("chain")["dominant_income_segment"].agg(lambda s: s.mode().iloc[0]))
    with open(ART / "new_outlet_categories.json", "w") as f:
        json.dump({"categories": cats, "features": FULL, "skus": sku_meta,
                   "ses_by_sub_county": dict(zip(ses["sub_county"], ses["ses_index_0_100"].astype(float))),
                   "default_income_segment_by_chain": seg.to_dict()}, f, indent=2)
    with open(ART / "new_outlet_evaluation.json", "w") as f:
        json.dump({"rows": int(len(agg)), "outlets": int(agg["outlet"].nunique()), "folds": N_FOLDS,
                   "overall": overall, "fold_wins_catchment": wins,
                   "per_fold": folds.round(4).to_dict(orient="records"),
                   "feature_importance": imp.round(5).to_dict()}, f, indent=2)
    print(f"\nSaved -> {ART / 'new_outlet_model.json'}  (+ new_outlet_categories.json, new_outlet_evaluation.json)")
    print("Restart uvicorn to load it.")


if __name__ == "__main__":
    main()
