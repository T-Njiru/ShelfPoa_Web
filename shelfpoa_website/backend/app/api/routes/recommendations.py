from fastapi import APIRouter, Query

from app.core.config import settings
from app.ml.registry import registry
from app.ml import recommendations as recommendation_service
from app.models.schemas import Recommendation
from app.services import mock_data

router = APIRouter(prefix="/api/recommendations", tags=["recommendations"])


@router.get("", response_model=list[Recommendation])
def list_recommendations(limit: int = Query(10, ge=1, le=100)):
    if settings.ml_mode == "live" and registry.ready:
        return recommendation_service.generate(limit=limit)
    return mock_data.get_recommendations(limit)