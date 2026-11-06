from typing import Optional
from pydantic import BaseModel, Field


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
    osa_last_week_pct: Optional[float] = None  # % of last week the SKU was on shelf (None: no shelf data)


class PlannedPromo(BaseModel):
    promo_days_in_week: int = 0
    mean_discount_pct: float = 0.0
    dominant_promo_type: str = "none"  # price_discount | multi_buy | bundle_with_complement | display_feature | none


class NewOutletRequest(BaseModel):
    """A site with no sales history. Either chain + branch of an outlet already on file
    (catchment looked up), or chain + sub_county + the site's satellite catchment
    (from scripts/catchment_for_site.py)."""
    chain: str
    sub_county: Optional[str] = None             # e.g. "EMBAKASI"
    branch: Optional[str] = None
    catchment_pop_2026: Optional[float] = None   # people within ~2 km, distance-decayed
    built_growth_annual: Optional[float] = None  # e.g. 0.035 = 3.5% a year
    dominant_income_segment: Optional[str] = None  # high | middle | low; defaults to the chain's usual
    promo_days_in_week: int = 0
    mean_discount_pct: float = 0.0
    # opening plan (app/ml/outlet_planner.py)
    restock_days: int = Field(7, ge=1, le=60)          # days between deliveries
    lead_time_days: int = Field(2, ge=0, le=30)        # order -> on shelf
    service_level: float = Field(0.95, gt=0.5, lt=1)   # chance of NOT running out before the next delivery
    blueband_facings: int = Field(40, ge=1, le=500)    # Blueband facings the branch will give the brand


class NewOutletSkuForecast(BaseModel):
    sku: str
    flavor: str
    pack_size_g: int
    predicted_units_per_week: float
    opening_stock_units: Optional[int] = None
    safety_stock_units: Optional[int] = None
    facings: Optional[int] = None


class OutletBenchmark(BaseModel):
    bb_share_pct: float   # Blueband share of the spreads shelf, last 28 days
    osa_pct: float        # on-shelf availability, last 28 days
    outlets: int


class CatchmentSite(BaseModel):
    chain: str
    branch: str
    sub_county: str
    catchment_pop_2026: float
    built_growth_annual: float


class NearbyOutlet(BaseModel):
    chain: str
    branch: str
    lat: float
    lon: float
    distance_km: float
    catchment_pop_2026: float


class LocationCatchment(BaseModel):
    """Satellite catchment for a pinned point (interpolated from the Nairobi grid)."""
    lat: float
    lon: float
    pop_1km: float
    pop_2km: float
    density_per_km2: float
    catchment_pop_2026: float
    built_growth_annual: float
    sub_county: Optional[str] = None
    sub_county_from: Optional[str] = None
    nearby: list[NearbyOutlet] = []
    in_training_range: bool = True


class OutletPoint(BaseModel):
    chain: str
    branch: str
    lat: float
    lon: float


class NewOutletOptions(BaseModel):
    chains: list[str]
    sub_counties: list[str]
    income_segments: list[str]
    sites: list[CatchmentSite]
    points: list[OutletPoint] = []
    grid_available: bool = False


class NewOutletForecast(BaseModel):
    chain: str
    branch: Optional[str] = None
    sub_county: str
    dominant_income_segment: str
    catchment_pop_2026: float
    built_growth_annual: float
    total_units_per_week: float
    skus: list[NewOutletSkuForecast]
    opening_stock_total: Optional[int] = None
    facings_total: Optional[int] = None
    comparable_chain: Optional[OutletBenchmark] = None
    comparable_chain_in_area: Optional[OutletBenchmark] = None
    assumptions: Optional[dict] = None

