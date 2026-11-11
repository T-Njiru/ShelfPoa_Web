"""
app/services/merchandiser_performance.py
==========================================
Live /api/merchandisers/performance and /api/merchandisers/{id}/submissions.
Reads audits, osa_reports and sos_audits in BOTH the seeded shape and the mobile-app shape
(see app/core/normalize.py) and groups by merchandiser.

A record is credited to a merchandiser via its merchandiser_id, or its uid looked up in
users/{uid}.merchandiser_id. A visit = one audit_id; the app stamps the same auditId on the
OSA, SOS and planogram captures from one store visit.

Metric definitions (state these in the thesis):
  visits_this_month        visits since the 1st of the current month, Nairobi time (EAT, UTC+3)
  branches_covered         distinct outlets visited in the last 30 days
  sub_counties / outlets   where those outlets are (sub-county from outlets_universe)
  avg_osa_pct              % of SKU readings that were "available", last 30 days
  avg_sos_pct              Blueband share of the shelf per visit, averaged, last 30 days
                           (seeded: sum of per-SKU shares; app: coverageScore)
  planogram_compliance_pct planogram compliance per visit, averaged, last 30 days
                           (seeded: % of on-shelf SKUs compliant; app: audits.adherenceScore)

Sorted by avg_osa_pct, then visits. Returns None when Firebase is not configured so the
route can fall back to mock data.

Speed: the six Firebase reads run in parallel. warm() loads them when the server starts, and after
that a request older than CACHE_SECONDS is answered from the copy in memory while a background
thread fetches a fresh one. So only a request in the first seconds after start-up ever waits for
Firebase, and a new audit takes up to about CACHE_SECONDS (plus one read) to show.
"""
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from collections import defaultdict
from datetime import datetime, timedelta, timezone

from app.core import normalize
from app.core.firebase import get_ref
from app.models.schemas import MerchandiserPerformance

WINDOW_DAYS = 30
EAT = timezone(timedelta(hours=3))
READ_LIMITS = {"audits": 3000, "osa_reports": 5000, "sos_audits": 6000}
CACHE_SECONDS = 60
_cache = {"at": 0.0, "data": None, "refreshing": False}
_cache_lock = threading.Lock()


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _raw(node: str):
    ref = get_ref(node)
    return None if ref is None else ref.order_by_key().limit_to_last(READ_LIMITS[node]).get()


def _mean(xs: list) -> float:
    return round(sum(xs) / len(xs), 1) if xs else 0.0


def _fetch():
    """One parallel round of Firebase reads -> the data both endpoints need (None = no Firebase)."""
    small = ("users", "merchandisers", "outlets_universe")
    refs = {n: get_ref(n) for n in (*small, *READ_LIMITS)}
    if any(r is None for r in refs.values()):
        return None
    with ThreadPoolExecutor(max_workers=6) as pool:
        jobs = {n: pool.submit(refs[n].get) for n in small}
        jobs.update({n: pool.submit(_raw, n) for n in READ_LIMITS})
        got = {n: j.result() for n, j in jobs.items()}
    uid_to_merch = normalize.uid_map(got["users"])
    return {
        "names": {k: (v or {}).get("name", k) for k, v in (got["merchandisers"] or {}).items()},
        "sub_county_of": normalize.outlet_sub_counties(got["outlets_universe"]),
        "osa": normalize.osa_readings(got["osa_reports"], uid_to_merch),
        "sos": normalize.sos_visits(got["sos_audits"], uid_to_merch),
        "aud": normalize.audit_visits(got["audits"], uid_to_merch),
    }


def _refresh_in_background():
    try:
        data = _fetch()
        if data is not None:
            _cache.update(at=time.monotonic(), data=data)
    except Exception:
        pass            # keep serving the copy we have; the next request tries again
    finally:
        _cache["refreshing"] = False


def _load():
    """Everything both endpoints need, or None if Firebase isn't configured."""
    if _cache["data"] is not None:
        if time.monotonic() - _cache["at"] >= CACHE_SECONDS:
            with _cache_lock:
                if not _cache["refreshing"]:
                    _cache["refreshing"] = True
                    threading.Thread(target=_refresh_in_background, daemon=True).start()
        return _cache["data"]                     # answered from memory, never waits for Firebase
    with _cache_lock:   # nothing loaded yet: concurrent first requests share one read
        if _cache["data"] is None:
            data = _fetch()
            if data is None:
                return None
            _cache.update(at=time.monotonic(), data=data)
        return _cache["data"]


def warm():
    """Load the data in the background when the server starts, so the first page view is fast."""
    def run():
        try:
            _load()
        except Exception:
            pass        # Firebase down at start-up: the first request will try again
    threading.Thread(target=run, daemon=True).start()


def _visits(d: dict) -> dict:
    """audit_id -> {m, outlet, branch_name, sub_county, ts} for every credited visit, at its earliest timestamp."""
    visits = {}
    for r in [*d["aud"], *d["sos"], *d["osa"]]:
        if not r["merchandiser_id"]:
            continue
        v = visits.setdefault(r["audit_id"], {"m": r["merchandiser_id"], "outlet": r["outlet_id"],
                                              "branch_name": r["branch_name"], "sub_county": r["sub_county"],
                                              "ts": r["timestamp"]})
        v["ts"] = min(v["ts"], r["timestamp"])
        v["outlet"] = v["outlet"] or r["outlet_id"]
        v["branch_name"] = v["branch_name"] or r["branch_name"]
        v["sub_county"] = v["sub_county"] or r["sub_county"]
    for v in visits.values():
        v["sub_county"] = d["sub_county_of"].get(v["outlet"]) or v["sub_county"] or ""
    return visits


def performance(limit: int = 8, now: datetime | None = None):
    d = _load()
    if d is None:
        return None
    now = now or datetime.now(timezone.utc)
    cutoff = _iso(now - timedelta(days=WINDOW_DAYS))
    month_start = _iso(now.astimezone(EAT).replace(day=1, hour=0, minute=0, second=0, microsecond=0))

    m = defaultdict(lambda: {"visits": 0, "outlets": {}, "osa": [], "sos": [], "plano": []})
    for v in _visits(d).values():
        if v["ts"] >= month_start:
            m[v["m"]]["visits"] += 1
        if v["ts"] >= cutoff and v["outlet"]:
            m[v["m"]]["outlets"][v["outlet"]] = (v["branch_name"], v["sub_county"])
    for r in d["osa"]:
        if r["merchandiser_id"] and r["timestamp"] >= cutoff:
            m[r["merchandiser_id"]]["osa"].append(100.0 if r["available"] else 0.0)
    for r in [*d["sos"], *d["aud"]]:
        if not r["merchandiser_id"] or r["timestamp"] < cutoff:
            continue
        if "sos_pct" in r:
            m[r["merchandiser_id"]]["sos"].append(r["sos_pct"])
        if r["planogram_pct"] is not None:
            m[r["merchandiser_id"]]["plano"].append(r["planogram_pct"])

    rows = []
    for mid in sorted(set(m) | set(d["names"])):  # registered merchandisers with no visits show as zeros
        x = m[mid]
        rows.append(MerchandiserPerformance(
            merchandiser_id=mid,
            name=d["names"].get(mid, mid),
            branches_covered=len(x["outlets"]),
            visits_this_month=x["visits"],
            avg_sos_pct=_mean(x["sos"]),
            avg_osa_pct=_mean(x["osa"]),
            planogram_compliance_pct=_mean(x["plano"]),
            sub_counties=sorted({sc for _, sc in x["outlets"].values() if sc}),
            outlets=sorted({name for name, _ in x["outlets"].values() if name}),
        ))
    rows.sort(key=lambda r: (-r.avg_osa_pct, -r.visits_this_month))
    return rows[:limit]


def submissions(merchandiser_id: str, days: int | None = None, limit: int = 20, now: datetime | None = None):
    """One row per visit by this merchandiser, newest first: OSA / SOS / planogram for that visit.
    days=None -> the latest `limit` visits ever; days=1 or 7 -> visits in the last 24 h / 7 days."""
    d = _load()
    if d is None:
        return None
    now = now or datetime.now(timezone.utc)
    cutoff = _iso(now - timedelta(days=days)) if days else ""

    visits = {aid: v for aid, v in _visits(d).items() if v["m"] == merchandiser_id and v["ts"] >= cutoff}
    osa = defaultdict(lambda: [0, 0, []])  # audit_id -> [available, total, out-of-stock SKUs]
    for r in d["osa"]:
        if r["audit_id"] in visits:
            o = osa[r["audit_id"]]
            o[0] += r["available"]
            o[1] += 1
            if not r["available"]:
                o[2].append(r["sku"])
    sos = {r["audit_id"]: r for r in d["sos"] if r["audit_id"] in visits}
    plano = {r["audit_id"]: r["planogram_pct"] for r in d["aud"]
             if r["audit_id"] in visits and r["planogram_pct"] is not None}

    out = []
    for aid, v in visits.items():
        o = osa.get(aid)
        s = sos.get(aid)
        p = plano.get(aid, s["planogram_pct"] if s else None)
        out.append({
            "audit_id": aid, "timestamp": v["ts"], "outlet_id": v["outlet"],
            "branch_name": v["branch_name"], "sub_county": v["sub_county"],
            "osa_pct": round(100 * o[0] / o[1], 1) if o and o[1] else None,
            "skus_checked": o[1] if o else 0,
            "out_of_stock": sorted(o[2]) if o else [],
            "sos_pct": round(s["sos_pct"], 1) if s else None,
            "planogram_pct": round(p, 1) if p is not None else None,
        })
    out.sort(key=lambda r: r["timestamp"], reverse=True)
    return out[:limit]