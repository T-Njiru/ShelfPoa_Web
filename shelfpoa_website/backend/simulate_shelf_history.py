r"""
simulate_shelf_history.py  --  shelf history (OSA, SOS, planogram) that actually drives sales
================================================================================================
Run from backend\  (reads/writes app\ml\artifacts\):

    .\.venv\Scripts\python.exe simulate_shelf_history.py

Why: XGBoost can only learn from SOS/OSA/compliance if past sales weeks have shelf data next to
them. Firebase only holds ~1 week of audits, so this simulates shelf history for the whole sales
period (Jun-Oct 2026) and applies its EFFECT to sales, the way it works in a real store:

  OSA        A SKU is either on the shelf or not each day (a Markov chain: once out, it tends to
             stay out ~2-3 days). Out-of-stock day -> 0 units sold, whatever the demand was.
             Outages are likelier at value chains, for slow SKUs, and on promo / school-reopening
             days (demand spikes empty shelves).
  SOS        Blueband's share of the spreads shelf per branch drifts week to week around the
             chain's norm. +1 point above the norm -> +1.5% sales.
  Planogram  Compliance % per branch drifts around 80%. +1 point -> +0.4% sales.

Inputs : app\ml\artifacts\nairobi_sku_outlet_daily_sales_EXTENDED.csv   (unconstrained demand)
Outputs: app\ml\artifacts\nairobi_sku_outlet_daily_sales_SHELF.csv      (observed sales; adds
                                                                         true_demand_units = ground truth, never a feature)
         app\ml\artifacts\shelf_history_daily.csv                       (date, chain, branch, sku,
                                                                         on_shelf, sos_pct, planogram_pct)
The shelf file has the shape a weekly roll-up of Firebase osa_reports / sos_audits / audits gives,
so real audits can replace it later (demand_model.load_shelf_history()).
"""

from pathlib import Path

import numpy as np
import pandas as pd

ART = Path(__file__).resolve().parent / "app" / "ml" / "artifacts"
SEED = 42

# daily probability an on-shelf SKU goes out of stock (before multipliers)
CHAIN_OUT = {"Carrefour": 0.010, "Chandarana Foodplus": 0.012, "Naivas": 0.020, "Quickmart": 0.020,
             "Cleanshelf": 0.025, "Magunas": 0.035, "AFCOS": 0.035}
SLOW_SKUS = {"BB VANILLA 1Kg", "BB CHOCO 1Kg", "BB S4B 1Kg", "BB VANILLA 500g"}
P_STAY_OUT = 0.60                       # mean outage ~2.5 days
CHAIN_BB_SHARE = {"Carrefour": 30, "Chandarana Foodplus": 32, "Naivas": 38, "Quickmart": 40,
                  "Cleanshelf": 42, "Magunas": 46, "AFCOS": 46}
SOS_EFFECT, PLANO_EFFECT = 0.015, 0.004  # sales multiplier per point above the norm
FLAVOR_W = {"ORI": 0.42, "S4B": 0.28, "CHOCO": 0.20, "VANILLA": 0.10}
SIZE_W = {100: 0.30, 250: 0.30, 500: 0.25, 1000: 0.15}


def main():
    rng = np.random.default_rng(SEED)
    sales = pd.read_csv(ART / "nairobi_sku_outlet_daily_sales_EXTENDED.csv", parse_dates=["date"])
    sales = sales.sort_values(["chain", "branch", "sku", "date"]).reset_index(drop=True)
    start = sales["date"].min()
    sales["week_idx"] = (sales["date"] - start).dt.days // 7
    reopen = pd.Timestamp("2026-08-24")
    spike = (sales["date"] - reopen).abs() <= pd.Timedelta(days=4)

    # --- weekly SOS + planogram per branch: random walks around the chain norm / 80% -------------
    branches = sales[["chain", "branch"]].drop_duplicates()
    weeks = np.sort(sales["week_idx"].unique())
    rows = []
    for c, b in branches.itertuples(index=False):
        norm = CHAIN_BB_SHARE.get(c, 38)
        sos = norm + rng.normal(0, 3)
        plano = 80 + rng.normal(0, 5)
        for w in weeks:
            sos = float(np.clip(sos + rng.normal(0, 2) + 0.2 * (norm - sos), 10, 70))
            plano = float(np.clip(plano + rng.normal(0, 3) + 0.2 * (80 - plano), 45, 98))
            rows.append((c, b, w, sos, plano, norm))
    wk = pd.DataFrame(rows, columns=["chain", "branch", "week_idx", "bb_share", "planogram_pct", "norm"])
    sales = sales.merge(wk, on=["chain", "branch", "week_idx"], how="left")

    # SKU-level share of shelf = brand share x the SKU's slice of Blueband facings
    sku_w = sales["flavor"].map(FLAVOR_W).fillna(0.1) * sales["pack_size_g"].map(SIZE_W).fillna(0.2)
    slice_sum = sku_w.groupby([sales["branch"], sales["chain"], sales["date"]]).transform("sum")
    sales["sos_pct"] = (sales["bb_share"] * sku_w / slice_sum).round(2)

    # --- daily on-shelf state per (chain, branch, sku) ----------------------------------------------
    p_out = (sales["chain"].map(CHAIN_OUT).fillna(0.02)
             * np.where(sales["sku"].isin(SLOW_SKUS), 1.8, 1.0)
             * np.where(sales["promo_flag"] == 1, 2.0, 1.0)
             * np.where(spike, 2.0, 1.0)).to_numpy()
    u = rng.random(len(sales))
    series_start = (sales[["chain", "branch", "sku"]] != sales[["chain", "branch", "sku"]].shift()).any(axis=1).to_numpy()
    on = np.empty(len(sales), dtype=np.int8)
    state = 1
    for i in range(len(sales)):
        if series_start[i]:
            state = 1
        state = (0 if u[i] < p_out[i] else 1) if state == 1 else (0 if u[i] < P_STAY_OUT else 1)
        on[i] = state
    sales["on_shelf"] = on

    # --- apply the shelf effects to sales -----------------------------------------------------------
    mult = (1 + SOS_EFFECT * (sales["bb_share"] - sales["norm"])) * (1 + PLANO_EFFECT * (sales["planogram_pct"] - 80))
    demand = sales["units_sold"] * mult.clip(lower=0.5)
    demand = np.floor(demand + rng.random(len(sales))).astype(int)    # stochastic rounding, no extra noise
    sales["true_demand_units"] = demand
    sales["units_sold"] = demand * sales["on_shelf"]                   # stock-out = no sale

    sales["planogram_pct"] = sales["planogram_pct"].round(1)
    shelf_cols = ["date", "chain", "branch", "sku", "on_shelf", "sos_pct", "planogram_pct"]
    sales[shelf_cols].to_csv(ART / "shelf_history_daily.csv", index=False)
    keep = [c for c in pd.read_csv(ART / "nairobi_sku_outlet_daily_sales_EXTENDED.csv", nrows=1).columns]
    sales[keep + ["true_demand_units"]].to_csv(ART / "nairobi_sku_outlet_daily_sales_SHELF.csv", index=False)

    lost = 1 - sales["units_sold"].sum() / sales["true_demand_units"].sum()
    print(f"{len(sales):,} daily rows, {sales['date'].min().date()} to {sales['date'].max().date()}")
    print(f"On-shelf availability: {sales['on_shelf'].mean() * 100:.1f}% of SKU-days")
    print(f"Sales lost to stock-outs: {lost * 100:.1f}% of true demand")
    print(sales.groupby("chain")["on_shelf"].mean().mul(100).round(1).rename("OSA % by chain").to_string())
    print(f"\nWrote {ART / 'shelf_history_daily.csv'}\n      {ART / 'nairobi_sku_outlet_daily_sales_SHELF.csv'}")


if __name__ == "__main__":
    main()
