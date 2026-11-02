"""
app/core/normalize.py
======================
One place that understands BOTH record shapes in Firebase, so the routes don't care
who wrote a record:

  * seeded / contract shape  (seed_osa_reports.py, seed_audits.py)
        snake_case, one record per SKU, ISO timestamps, merchandiser_id on every record
  * mobile-app shape         (OSAScreen.kt, Share_of_shelf.kt, the planogram audit screen)
        camelCase, one record per capture, millisecond timestamps,
        osa_reports.skuCounts {sku: facings}, sos_audits.coverageScore, audits.adherenceScore

Merchandiser attribution: merchandiser_id / merchandiserId on the record, else the record's
uid looked up in users/{uid}.merchandiser_id. Records with neither still count for stock-outs
and recommendations, just not for a merchandiser's scorecard.
"""

import re
from datetime import datetime, timezone

# The 13 Blueband SKUs on the market. Must match OSA.EXPECTED_SKUS (mobile) and SKUS in
# frontend recommendationStore.js. (BB CHOCO 1Kg and BB VANILLA 250g don't exist.)
SKUS = [
    "BB ORI 100g", "BB ORI 250g", "BB ORI 500g", "BB ORI 1Kg",
    "BB S4B 100g", "BB S4B 250g", "BB S4B 500g", "BB S4B 1Kg",
    "BB CHOCO 100g", "BB CHOCO 250g", "BB CHOCO 500g",
    "BB VANILLA 500g", "BB VANILLA 1Kg",
]
_PLACEHOLDERS = {"", "unknown", "n/a", "N/A"}


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def iso(ts) -> str:
    """Millisecond epoch (app) or ISO string (seeded) -> 'YYYY-MM-DDTHH:MM:SSZ'."""
    if isinstance(ts, (int, float)):
        return datetime.fromtimestamp(ts / 1000, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return str(ts or "")


def _outlet(rec: dict):
    oid = rec.get("outlet_id") or rec.get("outletId") or ""
    name = rec.get("branch_name") or rec.get("outletName") or ""
    name = "" if name in _PLACEHOLDERS else name
    # app records from the old outlet list carry Firebase push ids ("-Onw..."); use the name instead
    if (oid in _PLACEHOLDERS or oid.startswith("-")) and name:
        oid = slug(name)
    return ("" if oid in _PLACEHOLDERS else oid), name


def _common(key: str, rec: dict, uid_to_merch: dict) -> dict:
    oid, name = _outlet(rec)
    uid = rec.get("uid") or ""
    return {
        "outlet_id": oid,
        "branch_name": name,
        "timestamp": iso(rec.get("timestamp")),
        "merchandiser_id": rec.get("merchandiser_id") or rec.get("merchandiserId") or uid_to_merch.get(uid, ""),
        "audit_id": rec.get("audit_id") or rec.get("auditId") or key,  # no visit id -> the capture is its own visit
        "uid": uid,
        "sub_county": rec.get("sub_county") or "",
    }


def outlet_sub_counties(outlets: dict | None) -> dict:
    """outlets_universe -> {outlet_id: sub_county}. Keys are slugs (seed_outlets.py) or legacy push ids,
    so both the key and the slug of outlet_name are mapped."""
    out = {}
    for key, o in (outlets or {}).items():
        if isinstance(o, dict) and o.get("sub_county"):
            out[key] = o["sub_county"]
            if o.get("outlet_name"):
                out[slug(o["outlet_name"])] = o["sub_county"]
    return out


def reporter_names(users: dict | None, merchandisers: dict | None) -> tuple[dict, dict]:
    """({merchandiser_id: name}, {uid: name}) for showing who submitted a record."""
    by_mid = {k: (v or {}).get("name", k) for k, v in (merchandisers or {}).items() if isinstance(v, dict)}
    by_uid = {uid: (u.get("display_name") or u.get("email") or uid)
              for uid, u in (users or {}).items() if isinstance(u, dict)}
    return by_mid, by_uid


def uid_map(users: dict | None) -> dict:
    return {uid: u["merchandiser_id"] for uid, u in (users or {}).items()
            if isinstance(u, dict) and u.get("merchandiser_id")}


def osa_readings(raw: dict | None, uid_to_merch: dict | None = None) -> list[dict]:
    """One dict per (capture, SKU): id, outlet_id, branch_name, sku, available, timestamp,
    merchandiser_id, audit_id, status."""
    out, m = [], uid_to_merch or {}
    for key, rec in (raw or {}).items():
        if not isinstance(rec, dict):
            continue
        if "sku" in rec and "available" in rec:  # contract shape
            out.append({**_common(key, rec, m), "id": key, "sku": rec["sku"],
                        "available": bool(rec["available"]), "status": rec.get("status", "open")})
        elif isinstance(rec.get("availability"), dict):  # app shape (OsaRepository): explicit per SKU,
            c = _common(key, rec, m)                     # incl. the merchandiser's manual corrections
            if not c["outlet_id"]:
                continue
            for sku, avail in rec["availability"].items():
                out.append({**c, "id": f"{key}:{sku}", "sku": sku, "available": bool(avail), "status": "open"})
        elif isinstance(rec.get("skuCounts"), dict):  # older app shape: a SKU with no facings is out of stock
            c = _common(key, rec, m)
            if not c["outlet_id"]:
                continue
            counts = rec["skuCounts"]
            for sku in SKUS:
                out.append({**c, "id": f"{key}:{sku}", "sku": sku,
                            "available": (counts.get(sku) or 0) > 0, "status": "open"})
        # app records with no skuCounts (detection returned nothing) are skipped, not read as 15 stock-outs
    return out


def sos_visits(raw: dict | None, uid_to_merch: dict | None = None) -> list[dict]:
    """One dict per visit: audit_id, merchandiser_id, outlet_id, timestamp,
    sos_pct (Blueband share of the shelf), planogram_pct (or None)."""
    visits, m = {}, uid_to_merch or {}
    for key, rec in (raw or {}).items():
        if not isinstance(rec, dict):
            continue
        c = _common(key, rec, m)
        if "share_of_shelf_pct" in rec:  # contract: per-SKU records, sum them per visit
            v = visits.setdefault(c["audit_id"], {**c, "sos_pct": 0.0, "_plano": [0, 0]})
            v["sos_pct"] += float(rec.get("share_of_shelf_pct") or 0)
            if rec.get("on_shelf_availability"):
                v["_plano"][0] += bool(rec.get("planogram_compliant"))
                v["_plano"][1] += 1
        elif "coverageScore" in rec:  # app: brand-level score per capture
            visits[c["audit_id"]] = {**c, "sos_pct": float(rec["coverageScore"]), "_plano": [0, 0]}
    for v in visits.values():
        ok, n = v.pop("_plano")
        v["planogram_pct"] = 100.0 * ok / n if n else None
    return list(visits.values())


def audit_visits(raw: dict | None, uid_to_merch: dict | None = None) -> list[dict]:
    """One dict per audits record: audit_id, merchandiser_id, outlet_id, timestamp,
    planogram_pct (app adherenceScore, or None for seeded visit records)."""
    out, m = [], uid_to_merch or {}
    for key, rec in (raw or {}).items():
        if isinstance(rec, dict):
            score = rec.get("adherenceScore")
            out.append({**_common(key, rec, m), "planogram_pct": float(score) if score is not None else None})
    return out