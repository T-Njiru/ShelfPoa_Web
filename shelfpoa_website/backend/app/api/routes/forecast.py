from fastapi import APIRouter, HTTPException, Query

from app.core.config import settings
from app.ml.registry import registry
from app.ml import demand_model as forecast_service
from app.ml import new_outlet, outlet_planner, location_lookup
from app.api import filters
from app.models.schemas import (WeeklyForecast, PlannedPromo, NewOutletRequest, NewOutletForecast,
                                NewOutletOptions, LocationCatchment)
from app.services import mock_data

router = APIRouter(prefix="/api/forecast", tags=["forecast"])


@router.get("", response_model=list[WeeklyForecast])
def get_forecast(
    chain: str | None = Query(None),
    branch: str | None = Query(None),
    sku: str | None = Query(None, description="e.g. 'BB VANILLA 500g'"),
):
    if settings.ml_mode == "live" and registry.ready:
        chain, branch, sku = filters.resolve(chain, branch, sku)   # unknown value -> 422, not []
        return forecast_service.forecast_next_week(chain=chain, branch=branch, sku=sku)
    return mock_data.get_forecast(chain=chain, branch=branch, sku=sku)


@router.post("/with-promo", response_model=list[WeeklyForecast])
def get_forecast_with_promo(
    promo: PlannedPromo,
    chain: str | None = Query(None),
    branch: str | None = Query(None),
    sku: str | None = Query(None),
):
    """Scores the upcoming week against a PLANNED promo -- what the frontend
    calls when checking whether a co-promotion from /api/recommendations is
    worth running."""
    if settings.ml_mode == "live" and registry.ready:
        chain, branch, sku = filters.resolve(chain, branch, sku)
        return forecast_service.forecast_next_week(
            chain=chain, branch=branch, sku=sku, planned_promo=promo.model_dump()
        )
    return mock_data.get_forecast_with_promo(chain=chain, branch=branch, sku=sku, promo=promo)


@router.post("/new-outlet", response_model=NewOutletForecast)
def get_new_outlet_forecast(req: NewOutletRequest):
    """Typical weekly demand per SKU for an outlet with NO sales history (planned branch or
    unserved outlet), from chain, sub-county and the site's satellite catchment. Pass chain +
    branch to score an outlet already on file (catchment looked up)."""
    plan_args = req.model_dump(include={"restock_days", "lead_time_days", "service_level", "blueband_facings"})
    if settings.ml_mode == "live" and new_outlet.available():
        try:
            fc = new_outlet.forecast_new_outlet(**req.model_dump(exclude=set(plan_args)))
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
    else:
        fc = mock_data.get_new_outlet_forecast(req)
    # opening stock, safety stock, facings and comparable-store benchmarks (no extra model)
    return outlet_planner.plan(fc, **plan_args)


@router.get("/new-outlet/options", response_model=NewOutletOptions)
def get_new_outlet_options():
    """What the planner page needs: valid chains / sub-counties / income segments, and every outlet
    with a satellite catchment on file (to plan from an existing site or compare against one)."""
    if new_outlet.available():
        _, meta = new_outlet._load()
        cats = meta["categories"]
    else:
        cats = {"chain": [], "sub_county": [], "dominant_income_segment": []}
    c = forecast_service.load_catchments()
    sites = [] if c is None else (
        c[["chain", "branch", "sub_county", "catchment_pop_2026", "built_growth_annual"]]
        .sort_values(["chain", "branch"]).to_dict(orient="records"))
    return {"chains": cats["chain"], "sub_counties": cats["sub_county"],
            "income_segments": cats["dominant_income_segment"], "sites": sites,
            "points": location_lookup.all_outlet_points(), "grid_available": location_lookup.available()}


@router.get("/new-outlet/location", response_model=LocationCatchment)
def get_location_catchment(lat: float = Query(..., ge=-90, le=90), lon: float = Query(..., ge=-180, le=180)):
    """Map pin -> people within 1 km / 2 km, density, built-up growth, likely sub-county and the
    outlets already within 3 km. Interpolated from the pre-built Nairobi grid (no Earth Engine call)."""
    if not location_lookup.available():
        raise HTTPException(status_code=503, detail="Catchment grid not built yet: run scripts/build_catchment_grid.py once.")
    try:
        return location_lookup.lookup(lat, lon)
    except location_lookup.OutsideCoverage as e:
        raise HTTPException(status_code=422, detail=str(e))
