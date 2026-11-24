import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core import normalize
from app.core.auth import dashboard_user
from app.core.config import settings
from app.core.firebase import get_ref
from app.models.schemas import ResolveStockout, StockoutAlert, StockoutEvent
from app.services import mock_data

router = APIRouter(prefix="/api/stockouts", tags=["stockouts"])

# How many of the most recent osa_reports records to scan. Must cover at least one full
# sweep of every outlet; 5,000 leaves headroom. (One app capture = 1 record = 15 readings.)
READINGS_WINDOW = 5000
RESOLUTIONS = "stockout_resolutions"   # {outlet__sku: {resolved_at, resolved_by, reading_ts}}
HISTORY_READINGS = 20                  # audit readings shown in an alert's history


def _key(outlet_id: str, sku: str) -> str:
    """Realtime Database key for one (outlet, SKU); keys can't contain . # $ [ ] /"""
    return re.sub(r"[.#$\[\]/\s]+", "_", f"{outlet_id}__{sku}")


def _readings():
    """(readings, name_of) for the recent OSA readings; None if Firebase isn't configured.
    name_of(reading) -> "Reported by": the merchandiser's name, else the account's name/email."""
    ref = get_ref("osa_reports")
    if ref is None:  # Firebase not configured (reason is logged once by firebase.py)
        return None
    # normalize.osa_readings reads both the seeded per-SKU records and the mobile app's
    # skuCounts captures (a SKU with no facings = out of stock).
    users = get_ref("users").get() or {}
    readings = normalize.osa_readings(ref.order_by_key().limit_to_last(READINGS_WINDOW).get(),
                                      normalize.uid_map(users))
    by_mid, by_uid = normalize.reporter_names(users, get_ref("merchandisers").get())
    return readings, lambda r: by_mid.get(r["merchandiser_id"]) or by_uid.get(r["uid"])


def _resolution_for(resolutions: dict, r: dict) -> dict | None:
    """The resolution covering this reading, if any. A resolution covers the reading it was made
    against (and earlier ones); if a later audit finds the SKU missing again, the alert re-opens."""
    res = resolutions.get(_key(r["outlet_id"], r["sku"]))
    if isinstance(res, dict) and str(res.get("reading_ts", "")) >= str(r["timestamp"]):
        return res
    return None


@router.get("", response_model=list[StockoutAlert])
def list_stockouts(limit: int = Query(10, ge=1, le=500)):   # page loads all; ~140 with seeded data
    if settings.ml_mode != "live":
        return mock_data.get_stockout_alerts(limit)
    loaded = _readings()
    if loaded is None:
        return mock_data.get_stockout_alerts(limit)
    readings, name_of = loaded

    # An alert is CURRENT only if the latest reading for that (outlet, SKU) says unavailable,
    # so repeat audits don't duplicate it and restocked SKUs drop off.
    latest = {}
    for r in readings:
        pair = (r["outlet_id"], r["sku"])
        if pair not in latest or r["timestamp"] > latest[pair]["timestamp"]:
            latest[pair] = r

    resolutions = get_ref(RESOLUTIONS).get() or {}
    alerts = []
    for r in latest.values():
        if r["available"]:
            continue
        res = _resolution_for(resolutions, r)
        alerts.append(StockoutAlert(
            id=r["id"], outlet_id=r["outlet_id"], branch_name=r["branch_name"], sku=r["sku"],
            detected_at=r["timestamp"], status="resolved" if res else r["status"], reported_by=name_of(r),
            resolved_by=res.get("resolved_by") if res else None, resolved_at=res.get("resolved_at") if res else None))
    alerts.sort(key=lambda a: a.detected_at, reverse=True)
    alerts.sort(key=lambda a: a.status == "resolved")   # open first, newest first within each group
    return alerts[:limit]


@router.get("/history", response_model=list[StockoutEvent])
def stockout_history(outlet_id: str = Query(..., min_length=1), sku: str = Query(..., min_length=1)):
    """Timeline for one (outlet, SKU), newest first: each audit reading (in stock / out of stock,
    who reported it) and when it was marked resolved, by whom."""
    if settings.ml_mode != "live":
        raise HTTPException(503, "History needs the live Firebase database.")
    loaded = _readings()
    if loaded is None:
        raise HTTPException(503, "History needs the live Firebase database.")
    readings, name_of = loaded

    mine = sorted((r for r in readings if r["outlet_id"] == outlet_id and r["sku"] == sku),
                  key=lambda r: r["timestamp"], reverse=True)[:HISTORY_READINGS]
    events = [StockoutEvent(kind="in_stock" if r["available"] else "out_of_stock", at=r["timestamp"],
                            by=name_of(r)) for r in mine]
    res = (get_ref(RESOLUTIONS).get() or {}).get(_key(outlet_id, sku))
    if isinstance(res, dict) and res.get("resolved_at"):
        events.append(StockoutEvent(kind="resolved", at=res["resolved_at"], by=res.get("resolved_by")))
    events.sort(key=lambda e: e.at, reverse=True)
    return events


@router.post("/resolve")
def resolve_stockout(body: ResolveStockout, user: dict = Depends(dashboard_user)):
    """Mark one (outlet, SKU) stock-out as resolved, e.g. after the outlet confirmed a restock.
    Saved in Firebase with who did it and when, so it survives a refresh and every admin sees it."""
    if settings.ml_mode != "live" or get_ref(RESOLUTIONS) is None:
        raise HTTPException(503, "Resolving needs the live Firebase database.")
    profile = (get_ref(f"users/{user['uid']}").get() or {}) if user.get("uid") else {}
    name = (profile.get("display_name") if isinstance(profile, dict) else None) or user.get("email") or "Admin"
    record = {"outlet_id": body.outlet_id, "sku": body.sku, "reading_ts": body.detected_at,
              "resolved_by": name, "resolved_by_uid": user.get("uid", ""),
              "resolved_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    get_ref(RESOLUTIONS).child(_key(body.outlet_id, body.sku)).set(record)
    return {"status": "resolved", **record}
