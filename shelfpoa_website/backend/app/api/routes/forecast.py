from fastapi import APIRouter, Query

from app.core.config import settings
from app.ml.registry import registry
from app.ml import demand_model as forecast_service
from app.models.schemas import WeeklyForecast, PlannedPromo
from app.services import mock_data

router = APIRouter(prefix="/api/forecast", tags=["forecast"])


@router.get("", response_model=list[WeeklyForecast])
def get_forecast(
    chain: str | None = Query(None),
    branch: str | None = Query(None),
    sku: str | None = Query(None, description="e.g. 'BB VANILLA 250g'"),
):
    if settings.ml_mode == "live" and registry.ready:
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
        return forecast_service.forecast_next_week(
            chain=chain, branch=branch, sku=sku, planned_promo=promo.model_dump()
        )
    return mock_data.get_forecast_with_promo(chain=chain, branch=branch, sku=sku, promo=promo)
