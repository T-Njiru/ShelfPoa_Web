from typing import Optional
from pydantic import BaseModel


class SOSResult(BaseModel):
    """Share of Shelf reading from a single YOLOv8 mobile capture."""
    outlet_id: str
    branch_name: str
    sku: str
    share_of_shelf_pct: float
    on_shelf_availability: bool
    planogram_compliant: bool
    captured_at: str


class DemandForecast(BaseModel):
    sku: str
    outlet_id: str
    branch_name: str
    forecast_units_next_7d: float
    forecast_units_next_30d: float
    confidence_interval_low: float
    confidence_interval_high: float


class AssociationRule(BaseModel):
    antecedent: list[str]
    consequent: list[str]
    support: float
    confidence: float
    lift: float


class Recommendation(BaseModel):
    id: str
    outlet_id: str
    branch_name: str
    sku: str
    recommendation_type: str  # e.g. "restock", "co-promotion", "shelf-placement"
    message: str
    priority: str  # "low" | "medium" | "high"
    related_rule: Optional[AssociationRule] = None


class StockoutAlert(BaseModel):
    id: str
    outlet_id: str
    branch_name: str
    sku: str
    detected_at: str
    status: str  # "open" | "acknowledged" | "resolved"
    reported_by: Optional[str] = None


class MerchandiserPerformance(BaseModel):
    merchandiser_id: str
    name: str
    branches_covered: int
    visits_this_month: int
    avg_sos_pct: float
    avg_osa_pct: float
    planogram_compliance_pct: float
    sub_counties: list[str] = []
    outlets: list[str] = []

    # --- add to app/models/schemas.py, alongside AssociationRule ---

class WeeklyForecast(BaseModel):
    chain: str
    branch: str
    sub_county: str
    sku: str
    flavor: str
    pack_size_g: int
    forecast_week_start: str
    lag_1w: float
    rolling_mean_3w: float
    predicted_units_next_week: float


class PlannedPromo(BaseModel):
    promo_days_in_week: int = 0
    mean_discount_pct: float = 0.0
    dominant_promo_type: str = "none"  # price_discount | multi_buy | bundle_with_complement | display_feature | none

