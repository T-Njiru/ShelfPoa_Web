"""
app/api/routes/shelf.py  --  GET /api/shelf/opportunities

Register in app/main.py next to the other routers:
    from app.api.routes import shelf
    app.include_router(shelf.router)
"""

from typing import Literal, Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.core.config import settings
from app.ml import shelf_opportunities

router = APIRouter(prefix="/api/shelf", tags=["shelf"])


class ShelfOpportunity(BaseModel):
    id: str
    kind: str                 # "sos" | "planogram" | "availability"
    outlet_id: str
    branch_name: str
    chain: str
    branch: str
    sku: Optional[str] = None  # set for "availability"; None for branch-level levers
    current_value: float       # % now (share of shelf / compliance / on-shelf availability)
    target_value: float        # % the scenario moves it to
    baseline_units: float      # forecast units/week as things are
    uplift_units: float        # extra units/week at the target
    uplift_pct: float
    message: str


_MOCK = [
    ShelfOpportunity(id="SHELF-0000", kind="sos", outlet_id="naivas-westlands", branch_name="Naivas Westlands",
                     chain="Naivas", branch="Westlands", current_value=36.0, target_value=42.0,
                     baseline_units=210.0, uplift_units=4.0, uplift_pct=1.9,
                     message="Raise Blueband share of shelf at Naivas Westlands from 36% to 42% -> about +1.9% sales (+4 units/week)"),
    ShelfOpportunity(id="SHELF-0001", kind="availability", outlet_id="magunas-kahawa", branch_name="Magunas Kahawa",
                     chain="Magunas", branch="Kahawa", sku="BB ORI 250g", current_value=71.0, target_value=100.0,
                     baseline_units=9.0, uplift_units=3.0, uplift_pct=33.3,
                     message="Keep BB ORI 250g on the shelf at Magunas Kahawa (it was available 71% of last week) -> about +33.3% sales (+3 units/week)"),
]


@router.get("/opportunities", response_model=list[ShelfOpportunity])
def list_opportunities(limit: int = Query(10, ge=1, le=200),
                       kind: Optional[Literal["sos", "planogram", "availability"]] = None):
    if settings.ml_mode == "live" and shelf_opportunities.available():
        return shelf_opportunities.opportunities(limit, kind)
    return [m for m in _MOCK if kind in (None, m.kind)][:limit]
