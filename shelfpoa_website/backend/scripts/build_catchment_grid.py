r"""
scripts/build_catchment_grid.py  --  satellite catchment for a grid covering Nairobi (run ONCE)
================================================================================================
Lets the New outlet planner work from a map pin: the API looks the clicked point up in this grid,
so nobody needs Earth Engine at request time.

Same method as catchment_for_site.py, computed for every 100 m pixel with neighbourhood sums
(two discs instead of two buffered rings -- the same numbers, far fewer Earth Engine calls):

    pop_1km, pop_2km     people within 1 km / 2 km                      (WorldPop R2025A, 2026)
    catchment_pop_2026   = e^-0.5 * pop_1km + e^-1.5 * (pop_2km - pop_1km)   (distance-decayed, as before)
    density_per_km2      = pop_2km / (pi * 2^2)
    built_growth_annual  = e^b - 1, log(built area_y) = a + b*(y - 2016), y = 2016..2023, within the
                           same distance-decayed rings                    (Open Buildings 2.5D Temporal)

Needs Earth Engine (offline tool, not an API requirement):
    pip install earthengine-api pandas numpy
    earthengine authenticate

Run from backend\ (takes roughly 10-30 minutes; progress is printed per chunk):
    python scripts\build_catchment_grid.py
    python scripts\build_catchment_grid.py --spacing 300          # finer grid, slower

Writes app\ml\artifacts\nairobi_catchment_grid.csv, then checks itself against the per-site
numbers already in outlet_catchments.csv (they should agree closely: same formula).
Re-running resumes: chunks already in the CSV are skipped.
"""

import argparse
import math
import time
from pathlib import Path

import ee
import numpy as np
import pandas as pd

ART = Path(__file__).resolve().parents[1] / "app" / "ml" / "artifacts"
GRID = ART / "nairobi_catchment_grid.csv"
CATCHMENTS = ART / "outlet_catchments.csv"
PROJECT = "shelfpoa-gee"
YEARS = list(range(2016, 2024))
PRESENCE_THRESH = 0.5
W1, W2 = math.exp(-0.5), math.exp(-1.5)          # ring weights: mid-distance 0.5 km and 1.5 km, lambda = 1 km
BBOX = (36.65, -1.45, 37.11, -1.15)              # Nairobi County (lon_min, lat_min, lon_max, lat_max)
SCALE = 100


def disc_sums(img):
    """(sum within 1 km, sum within 2 km) for every pixel."""
    k1 = ee.Kernel.circle(radius=1000, units="meters", normalize=False)
    k2 = ee.Kernel.circle(radius=2000, units="meters", normalize=False)
    return (img.reduceNeighborhood(ee.Reducer.sum(), k1),
            img.reduceNeighborhood(ee.Reducer.sum(), k2))


def catchment_image():
    wp = (ee.ImageCollection("WorldPop/GP/100m/R2025A/v1/pop")
          .filter(ee.Filter.eq("country", "KEN")).filter(ee.Filter.eq("year", 2026)))
    proj = wp.first().select("population").projection()
    pop = wp.mosaic().select("population").setDefaultProjection(proj).unmask(0)
    p1, p2 = disc_sums(pop)
    catch = p1.multiply(W1).add(p2.subtract(p1).multiply(W2))

    bld = ee.ImageCollection("GOOGLE/Research/open-buildings-temporal/v1")
    crs = proj.crs()
    fits = []
    for y in YEARS:
        # pin the 4 m grid explicitly: (100/4)^2 = 625 input pixels per 100 m pixel (< 1024 limit)
        built = (bld.filterDate(f"{y}-01-01", f"{y + 1}-01-01").mosaic().select("building_presence")
                 .gt(PRESENCE_THRESH).unmask(0).reproject(crs=crs, scale=4))
        # fraction of each 100 m pixel that is built, then m^2
        area = (built.reduceResolution(ee.Reducer.mean(), maxPixels=1024)
                .reproject(crs=crs, scale=SCALE).multiply(SCALE * SCALE))
        a1, a2 = disc_sums(area)
        ring_area = a1.multiply(W1).add(a2.subtract(a1).multiply(W2)).max(1).log()
        fits.append(ee.Image.constant(y - YEARS[0]).float().rename("t").addBands(ring_area.rename("y")))
    slope = ee.ImageCollection(fits).reduce(ee.Reducer.linearFit()).select("scale")
    growth = slope.exp().subtract(1)

    return ee.Image.cat([
        p1.rename("pop_1km"), p2.rename("pop_2km"),
        catch.rename("catchment_pop_2026"), growth.rename("built_growth_annual"),
    ])


def grid_points(spacing_m):
    lon0, lat0, lon1, lat1 = BBOX
    dlat = spacing_m / 111_320
    dlon = spacing_m / (111_320 * math.cos(math.radians((lat0 + lat1) / 2)))
    lats = np.arange(lat0, lat1 + 1e-9, dlat)
    lons = np.arange(lon0, lon1 + 1e-9, dlon)
    return [(round(float(la), 6), round(float(lo), 6)) for la in lats for lo in lons]


def sample(img, pts):
    fc = ee.FeatureCollection([ee.Feature(ee.Geometry.Point([lo, la]), {"lat": la, "lon": lo}) for la, lo in pts])
    out = img.reduceRegions(collection=fc, reducer=ee.Reducer.first(), scale=SCALE).getInfo()
    rows = []
    for f in out["features"]:
        p = f["properties"]
        if p.get("catchment_pop_2026") is None:
            continue
        rows.append({k: p.get(k) for k in ("lat", "lon", "pop_1km", "pop_2km", "catchment_pop_2026", "built_growth_annual")})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spacing", type=int, default=400, help="grid spacing in metres (default 400)")
    ap.add_argument("--chunk", type=int, default=300, help="points per Earth Engine request")
    ap.add_argument("--project", default=PROJECT)
    a = ap.parse_args()

    ee.Initialize(project=a.project)
    img = catchment_image()
    pts = grid_points(a.spacing)
    done = pd.read_csv(GRID) if GRID.exists() else pd.DataFrame()
    have = set(zip(done["lat"].round(6), done["lon"].round(6))) if len(done) else set()
    todo = [p for p in pts if p not in have]
    print(f"{len(pts):,} grid points at {a.spacing} m; {len(todo):,} to fetch")

    for i in range(0, len(todo), a.chunk):
        chunk = todo[i:i + a.chunk]
        for attempt in range(3):
            try:
                rows = sample(img, chunk)
                break
            except Exception as e:  # EE timeouts / quota: back off and retry
                print(f"  chunk {i // a.chunk + 1}: {e} -- retrying")
                time.sleep(10 * (attempt + 1))
        else:
            raise SystemExit("Earth Engine kept failing; re-run later (finished chunks are kept).")
        new = pd.DataFrame(rows)
        new["density_per_km2"] = new["pop_2km"] / (math.pi * 4)
        done = pd.concat([done, new], ignore_index=True)
        done.to_csv(GRID, index=False)
        print(f"  {min(i + a.chunk, len(todo)):,}/{len(todo):,} done")

    # self-check against the per-site method for the outlets on file
    if CATCHMENTS.exists():
        c = pd.read_csv(CATCHMENTS)
        got = pd.DataFrame(sample(img, list(zip(c["lat"].round(6), c["lon"].round(6)))))
        m = c.merge(got, on=["lat", "lon"], suffixes=("_site", "_grid"))
        r = np.corrcoef(m["catchment_pop_2026_site"], m["catchment_pop_2026_grid"])[0, 1]
        ratio = (m["catchment_pop_2026_grid"] / m["catchment_pop_2026_site"]).median()
        print(f"Self-check on {len(m)} outlets: catchment correlation {r:.3f}, median grid/site ratio {ratio:.3f}"
              f"  (expect ~1.0; small differences come from disc vs buffered-ring edges)")
    print(f"Saved {len(done):,} points -> {GRID}")


if __name__ == "__main__":
    main()
