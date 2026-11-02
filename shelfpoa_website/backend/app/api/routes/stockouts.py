from fastapi import APIRouter, Query

from app.core import normalize
from app.core.config import settings
from app.core.firebase import get_ref
from app.models.schemas import StockoutAlert
from app.services import mock_data

router = APIRouter(prefix="/api/stockouts", tags=["stockouts"])

# How many of the most recent osa_reports records to scan. Must cover at least one full
# sweep of every outlet; 5,000 leaves headroom. (One app capture = 1 record = 15 readings.)
READINGS_WINDOW = 5000


@router.get("", response_model=list[StockoutAlert])
def list_stockouts(limit: int = Query(10, ge=1, le=100)):
    if settings.ml_mode != "live":
        return mock_data.get_stockout_alerts(limit)

    ref = get_ref("osa_reports")
    if ref is None:  # Firebase not configured (reason is logged once by firebase.py)
        return mock_data.get_stockout_alerts(limit)

    # normalize.osa_readings reads both the seeded per-SKU records and the mobile app's
    # skuCounts captures (a SKU with no facings = out of stock).
    users = (get_ref("users").get() or {})
    readings = normalize.osa_readings(ref.order_by_key().limit_to_last(READINGS_WINDOW).get(),
                                      normalize.uid_map(users))
    # "Reported by": the merchandiser's name, else the submitting account's name/email
    by_mid, by_uid = normalize.reporter_names(users, get_ref("merchandisers").get())

    # An alert is CURRENT only if the latest reading for that (outlet, SKU) says unavailable,
    # so repeat audits don't duplicate it and restocked SKUs drop off.
    latest = {}
    for r in readings:
        pair = (r["outlet_id"], r["sku"])
        if pair not in latest or r["timestamp"] > latest[pair]["timestamp"]:
            latest[pair] = r

    alerts = [
        StockoutAlert(id=r["id"], outlet_id=r["outlet_id"], branch_name=r["branch_name"],
                      sku=r["sku"], detected_at=r["timestamp"], status=r["status"],
                      reported_by=by_mid.get(r["merchandiser_id"]) or by_uid.get(r["uid"]))
        for r in latest.values() if not r["available"]
    ]
    alerts.sort(key=lambda a: a.detected_at, reverse=True)
    return alerts[:limit]