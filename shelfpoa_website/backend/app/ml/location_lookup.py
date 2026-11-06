"""
Map pin -> satellite catchment, without Earth Engine at request time.

Reads artifacts/nairobi_catchment_grid.csv (built once by scripts/build_catchment_grid.py) and
interpolates the pinned point from the nearest grid points (inverse-distance weighting). The
sub-county is taken from the nearest outlet on file; the user can change it on the page.
"""
from functools import lru_cache

import numpy as np
import pandas as pd

from app.ml import demand_model

GRID_PATH = demand_model.REGISTRY_DIR / "nairobi_catchment_grid.csv"
K = 4                      # grid points used for interpolation
MAX_GAP_KM = 1.0           # nearest grid point further than this -> outside coverage
NEARBY_KM = 3.0
VALUES = ["pop_1km", "pop_2km", "density_per_km2", "catchment_pop_2026", "built_growth_annual"]


class OutsideCoverage(ValueError):
    pass


def available() -> bool:
    return GRID_PATH.exists()


@lru_cache(maxsize=1)
def _grid() -> pd.DataFrame:
    return pd.read_csv(GRID_PATH).dropna(subset=VALUES)


def _km(lat0, lon0, lat, lon):
    """Haversine distance in km (vectorised over lat/lon)."""
    r = np.radians
    a = (np.sin(r(lat - lat0) / 2) ** 2
         + np.cos(r(lat0)) * np.cos(r(lat)) * np.sin(r(lon - lon0) / 2) ** 2)
    return 6371.0 * 2 * np.arcsin(np.sqrt(a))


def lookup(lat: float, lon: float) -> dict:
    g = _grid()
    d = _km(lat, lon, g["lat"].to_numpy(), g["lon"].to_numpy())
    idx = np.argsort(d)[:K]
    if d[idx[0]] > MAX_GAP_KM:
        raise OutsideCoverage("That point is outside the Nairobi catchment grid.")
    w = 1.0 / np.maximum(d[idx], 0.05) ** 2
    vals = {k: float(np.dot(w, g[k].to_numpy()[idx]) / w.sum()) for k in VALUES}

    out = {"lat": lat, "lon": lon, **vals, "sub_county": None, "sub_county_from": None,
           "nearby": [], "in_training_range": True}
    c = demand_model.load_catchments()
    if c is not None and len(c):
        dc = _km(lat, lon, c["lat"].to_numpy(), c["lon"].to_numpy())
        c = c.assign(distance_km=dc).sort_values("distance_km")
        near = c.iloc[0]
        out["sub_county"] = near["sub_county"]
        out["sub_county_from"] = f"{near['chain']} {near['branch']} ({near['distance_km']:.1f} km away)"
        out["nearby"] = (c[c["distance_km"] <= NEARBY_KM]
                         [["chain", "branch", "lat", "lon", "distance_km", "catchment_pop_2026"]]
                         .round({"distance_km": 2}).to_dict(orient="records"))
        lo, hi = c["catchment_pop_2026"].min(), c["catchment_pop_2026"].max()
        out["in_training_range"] = bool(lo * 0.8 <= vals["catchment_pop_2026"] <= hi * 1.2)
    return out


def all_outlet_points() -> list[dict]:
    c = demand_model.load_catchments()
    if c is None:
        return []
    return c[["chain", "branch", "lat", "lon"]].to_dict(orient="records")
