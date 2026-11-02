"""
app/ml/recommendations.py
==========================
Live recommendation engine. Combines three things that already exist:

  * registry.rules   FP-Growth basket rules (what gets bought together)
  * demand_model     XGBoost weekly forecast per outlet x SKU (how much sells where)
  * osa_reports      live stock-out readings in Firebase (what is empty right now)

Recommendation types produced:
  "co-promotion"  Bundle a Blueband SKU with the grocery items it is bought with.
                  Score = lift x forecast weekly units of that SKU at the outlet, so a strong
                  pairing is only worth pushing where the SKU actually sells. One recommendation
                  per Blueband SKU: its highest-lift bundle, at the outlet that sells the most of it.
  "restock"       A SKU whose latest OSA reading at an outlet is "unavailable". Priority comes
                  from the forecast weekly units at risk there.

Priority: high = top 20% of the candidates being ranked, medium = next 30%, low = the rest.

NOT produced: "shelf-placement". It needs share-of-shelf audit data (sos_audits), which does
not exist yet. Add it when that data does rather than inventing it.
"""

import re
import time

import numpy as np

from app.core import normalize
from app.core.firebase import get_ref
from app.ml import demand_model
from app.ml.registry import registry
from app.models.schemas import AssociationRule, Recommendation

READINGS_WINDOW = 5000      # same scan window as /api/stockouts
FORECAST_TTL_SECONDS = 300  # the forecast re-reads the sales CSV (~1s), so cache it briefly
_PRIORITY_RANK = {"high": 0, "medium": 1, "low": 2}
_cache = {"at": 0.0, "units": {}, "names": {}}


def _slug(text: str) -> str:
    """Same ids as outlets_universe / osa_reports (seed_outlets.py, seed_osa_reports.py)."""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _forecast():
    """({(outlet_id, sku): weekly units}, {outlet_id: branch_name}), refreshed at most every 5 min."""
    if time.time() - _cache["at"] > FORECAST_TTL_SECONDS or not _cache["units"]:
        units, names = {}, {}
        for r in demand_model.forecast_next_week():
            name = f"{r['chain']} {r['branch']}"
            oid = _slug(name)
            units[(oid, r["sku"])] = r["predicted_units_next_week"]
            names[oid] = name
        _cache.update(at=time.time(), units=units, names=names)
    return _cache["units"], _cache["names"]


def _tiers(values):
    """Return a function mapping a value to a priority: high = top 20% of `values`, medium = next
    30%, low = the rest. Computed over the candidates being ranked (not all outlets), otherwise
    almost everything lands in "high"."""
    values = list(values)
    if not values:
        return lambda v: "medium"
    p50, p80 = np.percentile(values, [50, 80])
    return lambda v: "high" if v >= p80 else "medium" if v >= p50 else "low"


def _to_rule(r) -> AssociationRule:
    """Build the schema object from a registry.rules row. Fields are matched against the model, so
    singular/plural spellings (antecedent/antecedents) both work and unknown fields are dropped."""
    data = {"antecedent": list(r.antecedents), "antecedents": list(r.antecedents),
            "consequent": list(r.consequents), "consequents": list(r.consequents),
            "support": float(r.support), "confidence": float(r.confidence), "lift": float(r.lift)}
    return AssociationRule(**{k: v for k, v in data.items() if k in AssociationRule.model_fields})


def _restock_candidates(units):
    ref = get_ref("osa_reports")
    if ref is None:  # Firebase not configured: no restock recommendations (reason logged by firebase.py)
        return []
    # both the seeded per-SKU records and the app's skuCounts captures (see app/core/normalize.py)
    readings = normalize.osa_readings(ref.order_by_key().limit_to_last(READINGS_WINDOW).get())
    latest = {}  # a stock-out is current only if the LATEST reading for that (outlet, SKU) is unavailable
    for r in readings:
        pair = (r["outlet_id"], r["sku"])
        if pair not in latest or r["timestamp"] > latest[pair]["timestamp"]:
            latest[pair] = r
    return [{"outlet_id": oid, "branch_name": r["branch_name"], "sku": sku, "ts": r["timestamp"],
             "units": units.get((oid, sku))}
            for (oid, sku), r in latest.items() if not r["available"]]


def _copromotion_candidates(units, names):
    # best (highest-lift) bundle per Blueband SKU; every rule has exactly one Blueband SKU and the
    # rest of its items (both sides) are the grocery partners to bundle with
    best = {}
    for r in registry.rules.itertuples():
        items = list(r.antecedents) + list(r.consequents)
        bb = [i for i in items if i.startswith("BB ")]
        if len(bb) == 1 and (bb[0] not in best or r.lift > best[bb[0]].lift):
            best[bb[0]] = r

    top_outlet = {}  # sku -> (forecast units, outlet_id) at the outlet that sells the most of it
    for (oid, sku), u in units.items():
        if sku not in top_outlet or u > top_outlet[sku][0]:
            top_outlet[sku] = (u, oid)

    out = []
    for sku, r in best.items():
        if sku not in top_outlet:
            continue
        u, oid = top_outlet[sku]
        partners = tuple(sorted(i for i in list(r.antecedents) + list(r.consequents) if i != sku))
        out.append({"sku": sku, "partners": partners, "rule": r, "outlet_id": oid,
                    "branch_name": names[oid], "units": u, "score": float(r.lift) * u})
    return out


def generate(limit: int = 10) -> list[Recommendation]:
    units, names = _forecast()
    restock = sorted(_restock_candidates(units), key=lambda c: -(c["units"] or 0))
    promo = sorted(_copromotion_candidates(units, names), key=lambda c: -c["score"])

    # interleave so one type can't crowd out the other, then cut to the limit
    merged = []
    for i in range(max(len(restock), len(promo))):
        if i < len(restock):
            merged.append(("restock", restock[i]))
        if i < len(promo):
            merged.append(("co-promotion", promo[i]))
    merged = merged[:limit]

    stock_tier = _tiers([c["units"] for c in restock if c["units"] is not None])
    promo_tier = _tiers([c["score"] for c in promo])

    recs = []
    for kind, c in merged:
        if kind == "restock":
            at_risk = f"; ~{c['units']:.0f} units/week forecast demand at risk" if c["units"] is not None else ""
            msg = f"{c['sku']} is out of stock at {c['branch_name']} (detected {c['ts'][:10]}) - restock recommended{at_risk}"
            priority = stock_tier(c["units"]) if c["units"] is not None else "medium"
            rule = None
        else:
            r = c["rule"]
            msg = (f"Bundle {c['sku']} with {', '.join(c['partners'])} at {c['branch_name']} - "
                   f"lift {r.lift:.1f}, confidence {r.confidence:.0%}; ~{c['units']:.0f} units/week forecast for this SKU here")
            priority = promo_tier(c["score"])
            rule = _to_rule(r)
        recs.append(Recommendation(
            id="", outlet_id=c["outlet_id"], branch_name=c["branch_name"], sku=c["sku"],
            recommendation_type=kind, message=msg, priority=priority, related_rule=rule))

    recs.sort(key=lambda x: _PRIORITY_RANK[x.priority])  # stable: keeps the interleaved order within a tier
    for i, rec in enumerate(recs):
        rec.id = f"REC-{i:04d}"
    return recs