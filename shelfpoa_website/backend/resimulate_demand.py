r"""
resimulate_demand.py  --  re-simulate the demand layer (EXTENDED) around satellite catchments
================================================================================================
Run from backend\  BEFORE simulate_shelf_history.py:

    .\.venv\Scripts\python.exe resimulate_demand.py
    .\.venv\Scripts\python.exe simulate_shelf_history.py
    .\.venv\Scripts\python.exe train_xgboost_shelf.py
    .\.venv\Scripts\python.exe train_new_outlet_model.py

Why: before, every outlet in a sub-county shared the same population and SES, so outlet size
was set by chain and noise only. Now part of each outlet's volume comes from how many people
live around it (WorldPop R2025A, 0-2 km, distance-decayed) and how fast its area is building
up (Google Open Buildings 2.5D Temporal, 2016-2023). Built in the Google_Earth_proposition
sandbox; values live in app\ml\artifacts\outlet_catchments.csv.

Method (everything else about the data is kept):
  1. Fit a Poisson model to the current demand file:
         log mu = SKU + outlet + date + promo type
     The date term keeps the existing calendar exactly (day of week, school holidays,
     the reopening spike, month-end); the promo term keeps promo uplift.
  2. Rebuild the outlet term. The chain level is kept whole; the within-chain part is
     blended with the catchment:
         outlet_new = chain_level + (1 - W) * within_chain + W * GAMMA * (log C - mean log C)
  3. Add the area's building growth as a slow trend:  t * log(1 + g) / 365
  4. Re-scale so total units match the original file, then draw negative-binomial counts
     (dispersion fitted on the original file).

No stock-outs are added here: this file is UNCONSTRAINED demand. simulate_shelf_history.py
applies stock-outs, SOS and planogram effects on top, as before.

The original file is backed up once as *_pre_catchment.csv and every run reads from that
backup, so re-running gives the same result instead of compounding.
"""

import shutil
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.linear_model import PoissonRegressor

ART = Path(__file__).resolve().parent / "app" / "ml" / "artifacts"
DEMAND = ART / "nairobi_sku_outlet_daily_sales_EXTENDED.csv"
BACKUP = ART / "nairobi_sku_outlet_daily_sales_EXTENDED_pre_catchment.csv"
CATCHMENTS = ART / "outlet_catchments.csv"
SEED = 42

GAMMA = 0.35      # elasticity of outlet volume to catchment population (sub-linear)  # TODO: justify
W_CATCH = 0.5     # share of the within-chain outlet effect explained by catchment      # TODO: justify


def one_hot(df, cols):
    """Sparse one-hot design matrix + the column labels (first level of each dropped)."""
    blocks, names = [], []
    for c in cols:
        d = pd.get_dummies(df[c].astype(str), prefix=c, drop_first=True, sparse=True, dtype=float)
        blocks.append(sparse.csr_matrix(d.sparse.to_coo()))
        names += list(d.columns)
    return sparse.hstack(blocks).tocsr(), names


def main():
    if not BACKUP.exists():
        shutil.copy(DEMAND, BACKUP)
        print(f"Backed up original demand -> {BACKUP.name}")
    df = pd.read_csv(BACKUP, parse_dates=["date"])
    cols = list(df.columns)
    catch = pd.read_csv(CATCHMENTS)

    df["outlet"] = df["chain"] + " | " + df["branch"]
    df["day"] = df["date"].dt.strftime("%Y-%m-%d")
    terms = ["sku", "outlet", "day", "promo_type"]

    # 1. Poisson fit
    X, names = one_hot(df, terms)
    glm = PoissonRegressor(alpha=1e-6, max_iter=1000).fit(X, df["units_sold"])
    mu_fit = glm.predict(X)
    alpha = max((((df["units_sold"] - mu_fit) ** 2 - mu_fit).sum() / (mu_fit ** 2).sum()), 0.05)
    coef = pd.Series(glm.coef_, index=names)

    # 2. Rebuild the outlet term
    outlets = df[["chain", "branch", "outlet"]].drop_duplicates().reset_index(drop=True)
    outlets["old"] = outlets["outlet"].map(lambda o: coef.get(f"outlet_{o}", 0.0))
    outlets["chain_level"] = outlets.groupby("chain")["old"].transform("mean")
    outlets["within"] = outlets["old"] - outlets["chain_level"]
    outlets = outlets.merge(catch[["chain", "branch", "catchment_pop_2026", "built_growth_annual"]],
                            on=["chain", "branch"], how="left")
    if outlets["catchment_pop_2026"].isna().any():
        missing = outlets.loc[outlets["catchment_pop_2026"].isna(), "outlet"].tolist()
        raise SystemExit(f"No catchment for: {missing} -- add them to outlet_catchments.csv")
    logc = np.log(outlets["catchment_pop_2026"])
    outlets["new"] = (outlets["chain_level"] + (1 - W_CATCH) * outlets["within"]
                      + W_CATCH * GAMMA * (logc - logc.mean()))
    shift = outlets.set_index("outlet")["new"] - outlets.set_index("outlet")["old"]

    # 3. Building-growth trend
    g = outlets.set_index("outlet")["built_growth_annual"]
    t = (df["date"] - df["date"].min()).dt.days
    log_mu = np.log(mu_fit) + df["outlet"].map(shift).values + t.values * np.log1p(df["outlet"].map(g).values) / 365

    # 4. Re-scale to the original total, then draw counts
    mu = np.exp(log_mu)
    mu *= df["units_sold"].sum() / mu.sum()
    rng = np.random.default_rng(SEED)
    n = 1 / alpha
    df["units_sold"] = rng.negative_binomial(n, n / (n + mu))

    df["date"] = df["date"].dt.strftime("%Y-%m-%d")
    df[cols].to_csv(DEMAND, index=False)

    # Report
    orig = pd.read_csv(BACKUP)
    per = (df.assign(o=df["chain"] + " | " + df["branch"]).groupby("o")["units_sold"].mean()
           .rename("new").to_frame()
           .join(orig.assign(o=orig["chain"] + " | " + orig["branch"]).groupby("o")["units_sold"].mean().rename("old"))
           .join(outlets.set_index("outlet")["catchment_pop_2026"]))
    print(f"Wrote {DEMAND.name}: {len(df):,} rows   (GAMMA={GAMMA}, W={W_CATCH}, NB alpha={alpha:.3f})")
    print(f"mean units/day  original {orig['units_sold'].mean():.3f}  ->  new {df['units_sold'].mean():.3f}")
    print(f"variance        original {orig['units_sold'].var():.3f}  ->  new {df['units_sold'].var():.3f}")
    print(f"outlet volume vs catchment (Spearman)  original {per['old'].corr(per['catchment_pop_2026'], method='spearman'):.3f}"
          f"  ->  new {per['new'].corr(per['catchment_pop_2026'], method='spearman'):.3f}")
    wk = lambda d: d.groupby(pd.to_datetime(d["date"]).dt.to_period("W"))["units_sold"].mean()
    print(f"weekly pattern kept (corr original vs new): {wk(orig).corr(wk(df)):.3f}")
    print("Next: python simulate_shelf_history.py")


if __name__ == "__main__":
    main()
