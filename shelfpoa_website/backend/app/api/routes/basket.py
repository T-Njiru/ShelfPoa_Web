from fastapi import APIRouter, Query

from app.core.config import settings
from app.ml.registry import registry
from app.ml import basket as basket_service
from app.models.schemas import AssociationRule
from app.services import mock_data

router = APIRouter(prefix="/api/basket", tags=["basket"])


@router.get("/rules", response_model=list[AssociationRule])
def list_rules(
    limit: int = Query(10, ge=1, le=100),
    sku: str | None = Query(None, description="Filter by antecedent SKU, e.g. 'BB VANILLA 250g'"),
):
    if settings.ml_mode == "live" and registry.ready:
        return basket_service.get_rules(limit=limit, sku=sku)
    return mock_data.get_basket_rules(limit)