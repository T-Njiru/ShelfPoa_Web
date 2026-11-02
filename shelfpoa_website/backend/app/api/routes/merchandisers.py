from typing import Literal, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.core.config import settings
from app.models.schemas import MerchandiserPerformance
from app.services import mock_data, merchandiser_performance

router = APIRouter(prefix="/api/merchandisers", tags=["merchandisers"])


class Submission(BaseModel):
    """One store visit: what the merchandiser submitted for OSA, SOS and planogram."""
    audit_id: str
    timestamp: str
    outlet_id: str
    branch_name: str
    sub_county: str = ""
    osa_pct: Optional[float] = None       # % of SKUs on shelf at that visit
    skus_checked: int = 0
    out_of_stock: list[str] = []
    sos_pct: Optional[float] = None       # Blueband share of shelf
    planogram_pct: Optional[float] = None


@router.get("/performance", response_model=list[MerchandiserPerformance])
def list_performance(limit: int = Query(8, ge=1, le=100)):
    if settings.ml_mode == "live":
        rows = merchandiser_performance.performance(limit)
        if rows is not None:  # None = Firebase not configured -> fall through to mock
            return rows
    return mock_data.get_merchandiser_performance(limit)


@router.get("/{merchandiser_id}/submissions", response_model=list[Submission])
def list_submissions(merchandiser_id: str,
                     period: Literal["latest", "day", "week"] = "latest",
                     limit: int = Query(20, ge=1, le=100)):
    """period: latest = most recent visits ever; day = last 24 hours; week = last 7 days."""
    if settings.ml_mode != "live":
        return []
    rows = merchandiser_performance.submissions(
        merchandiser_id, days={"latest": None, "day": 1, "week": 7}[period], limit=limit)
    if rows is None:
        raise HTTPException(503, "Firebase isn't configured")
    return rows