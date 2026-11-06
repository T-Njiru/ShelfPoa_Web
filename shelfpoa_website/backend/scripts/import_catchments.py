r"""
scripts/import_catchments.py  --  bring the sandbox's catchments into the app
=============================================================================
Builds app\ml\artifacts\outlet_catchments.csv from the Google_Earth_proposition sandbox:

    python scripts\import_catchments.py --sandbox C:\Users\tednj\Desktop\Google_Earth_proposition

Reads  <sandbox>\data\external\outlets_geo.csv            (chain, branch, sub_county, lat, lon, geo_confidence)
       <sandbox>\data\external\outlet_catchments_gee.csv  (catchment_pop_2026 from WorldPop R2025A,
                                                           built_growth_annual from 01b)
Then rerun: resimulate_demand.py -> simulate_shelf_history.py -> train_xgboost_shelf.py
            -> train_new_outlet_model.py
"""

import argparse
from pathlib import Path

import pandas as pd

OUT = Path(__file__).resolve().parents[1] / "app" / "ml" / "artifacts" / "outlet_catchments.csv"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sandbox", required=True, type=Path)
    ext = ap.parse_args().sandbox / "data" / "external"

    geo = pd.read_csv(ext / "outlets_geo.csv")
    gee = pd.read_csv(ext / "outlet_catchments_gee.csv")
    out = geo.merge(gee[["chain", "branch", "catchment_pop_2026", "built_growth_annual"]],
                    on=["chain", "branch"], how="left")
    if out["catchment_pop_2026"].isna().any():
        raise SystemExit(f"Missing catchments for: {out.loc[out.catchment_pop_2026.isna(), 'branch'].tolist()}")
    out["catchment_source"] = gee["pop_source"].iloc[0] if "pop_source" in gee else "worldpop"
    out.to_csv(OUT, index=False)
    print(f"Wrote {OUT} ({len(out)} outlets, population source: {out['catchment_source'].iloc[0]})")
    print(out["catchment_pop_2026"].describe().round(0).to_string())


if __name__ == "__main__":
    main()
