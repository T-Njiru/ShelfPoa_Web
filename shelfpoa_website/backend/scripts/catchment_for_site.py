r"""
scripts/catchment_for_site.py  --  satellite catchment for one location (candidate site or new outlet)
========================================================================================================
Same method as the Google_Earth_proposition sandbox, for a single point:

    catchment_pop_2026  = sum over rings (0-1 km, 1-2 km) of exp(-d_mid / 1 km) * WorldPop R2025A 2026
    built_growth_annual = e^b - 1, where  log(built area_y) = a + b * (y - 2016),  y = 2016..2023
                          (Open Buildings 2.5D Temporal, 2D footprint, presence > 0.5)

Needs Earth Engine (not part of the API's requirements -- offline tool):
    pip install earthengine-api
    earthengine authenticate

Run from backend\ :
    python scripts\catchment_for_site.py --lat -1.2700 --lon 36.9900
    # add an outlet so the API and next retrain pick it up:
    python scripts\catchment_for_site.py --lat -1.2700 --lon 36.9900 --chain Naivas --branch "Ruai" --sub-county NJIRU --append

Then POST /api/forecast/new-outlet with chain, sub_county and the two printed numbers.
"""

import argparse
import math
from pathlib import Path

import ee
import numpy as np
import pandas as pd

CATCHMENTS = Path(__file__).resolve().parents[1] / "app" / "ml" / "artifacts" / "outlet_catchments.csv"
PROJECT = "shelfpoa-gee"
YEARS = list(range(2016, 2024))
RINGS_KM = [(0, 1), (1, 2)]
LAMBDA_KM = 1.0
PRESENCE_THRESH = 0.5


def rings(lat, lon):
    pt = ee.Geometry.Point([lon, lat])
    out = []
    for inner, outer in RINGS_KM:
        g = pt.buffer(outer * 1000)
        if inner > 0:
            g = g.difference(pt.buffer(inner * 1000), 1)
        out.append((g, math.exp(-((inner + outer) / 2) / LAMBDA_KM)))
    return out


def catchment(lat, lon):
    pop_img = (ee.ImageCollection("WorldPop/GP/100m/R2025A/v1/pop")
               .filter(ee.Filter.eq("country", "KEN")).filter(ee.Filter.eq("year", 2026))
               .mosaic().select("population"))
    bld = ee.ImageCollection("GOOGLE/Research/open-buildings-temporal/v1")
    built = ee.Image.cat([
        bld.filterDate(f"{y}-01-01", f"{y + 1}-01-01").mosaic().select("building_presence")
        .gt(PRESENCE_THRESH).multiply(ee.Image.pixelArea()).rename(f"b{y}") for y in YEARS])

    pop, area = 0.0, np.zeros(len(YEARS))
    for geom, w in rings(lat, lon):
        p = pop_img.reduceRegion(ee.Reducer.sum(), geom, scale=100, maxPixels=1e9).getInfo()
        a = built.reduceRegion(ee.Reducer.sum(), geom, scale=4, maxPixels=1e10, tileScale=8).getInfo()
        pop += w * (p.get("population") or 0.0)
        area += w * np.array([a.get(f"b{y}") or 0.0 for y in YEARS])
    slope = np.polyfit(np.array(YEARS) - YEARS[0], np.log(np.maximum(area, 1.0)), 1)[0]
    return pop, float(np.exp(slope) - 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lat", type=float, required=True)
    ap.add_argument("--lon", type=float, required=True)
    ap.add_argument("--project", default=PROJECT)
    ap.add_argument("--chain")
    ap.add_argument("--branch")
    ap.add_argument("--sub-county")
    ap.add_argument("--append", action="store_true", help="add/update this outlet in outlet_catchments.csv")
    a = ap.parse_args()

    ee.Initialize(project=a.project)
    pop, growth = catchment(a.lat, a.lon)
    print(f"catchment_pop_2026  = {pop:,.0f}")
    print(f"built_growth_annual = {growth:.4f}  ({growth * 100:.2f}% a year)")

    if a.append:
        if not (a.chain and a.branch and a.sub_county):
            raise SystemExit("--append needs --chain, --branch and --sub-county")
        c = pd.read_csv(CATCHMENTS)
        c = c[~((c["chain"] == a.chain) & (c["branch"] == a.branch))]
        row = {"chain": a.chain, "branch": a.branch, "sub_county": a.sub_county.upper(), "lat": a.lat,
               "lon": a.lon, "geo_confidence": "high", "catchment_pop_2026": pop,
               "built_growth_annual": growth, "catchment_source": "catchment_for_site.py"}
        pd.concat([c, pd.DataFrame([row])], ignore_index=True).to_csv(CATCHMENTS, index=False)
        print(f"Saved {a.chain} {a.branch} -> {CATCHMENTS.name}")


if __name__ == "__main__":
    main()
