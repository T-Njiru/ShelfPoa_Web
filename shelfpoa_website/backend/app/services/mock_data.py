"""
Mock implementations of the ML-backed services.

Each function here mirrors the exact response shape the real XGBoost /
FP-Growth / YOLOv8-aggregation logic will eventually return. When a model
is ready, replace the body of the matching function (or swap it out based
on settings.ml_mode) — routes and the frontend never need to change.
"""
import random
from datetime import datetime, timedelta

from app.models.schemas import (
    DemandForecast,
    AssociationRule,
    Recommendation,
    StockoutAlert,
    MerchandiserPerformance,
)

SKUS = [
    f"BB {flavor} {size}"
    for flavor in ["CHOCO", "ORI"]
    for size in ["100g", "250g", "500g", "1Kg"]
] + [f"BB S4B {size}" for size in ["250g", "500g", "1Kg"]] + ["OTHERS"]

CHAINS = ["Carrefour", "Naivas", "Quickmart", "Chandarana Foodplus", "Cleanshelf", "Magunas", "AFCOS"]
SUB_COUNTIES = [
    "Westlands", "Dagoretti North", "Dagoretti South", "Langata", "Kibra",
    "Roysambu", "Kasarani", "Ruaraka", "Embakasi", "Makadara", "Kamukunji",
]

_BRANCHES = [
    {"outlet_id": f"OUT-{i:03d}", "branch_name": f"{random.choice(CHAINS)} {sc}", "sub_county": sc}
    for i, sc in enumerate(SUB_COUNTIES * 2, start=1)
]

COMPLEMENTS = ["Bread", "Jam", "Tea", "Cocoa", "Flour", "Eggs", "Baking Powder"]


def _rand_branch():
    return random.choice(_BRANCHES)


def get_forecasts(limit: int = 10) -> list[DemandForecast]:
    results = []
    for _ in range(limit):
        b = _rand_branch()
        base = round(random.uniform(15, 120), 1)
        results.append(
            DemandForecast(
                sku=random.choice(SKUS),
                outlet_id=b["outlet_id"],
                branch_name=b["branch_name"],
                forecast_units_next_7d=base,
                forecast_units_next_30d=round(base * 4.2, 1),
                confidence_interval_low=round(base * 0.85, 1),
                confidence_interval_high=round(base * 1.15, 1),
            )
        )
    return results


def get_basket_rules(limit: int = 10) -> list[AssociationRule]:
    results = []
    for _ in range(limit):
        sku = random.choice(SKUS[:-1])
        results.append(
            AssociationRule(
                antecedent=[sku],
                consequent=[random.choice(COMPLEMENTS)],
                support=round(random.uniform(0.02, 0.18), 3),
                confidence=round(random.uniform(0.3, 0.85), 3),
                lift=round(random.uniform(1.05, 3.2), 2),
            )
        )
    return sorted(results, key=lambda r: r.lift, reverse=True)


def get_recommendations(limit: int = 10) -> list[Recommendation]:
    rules = get_basket_rules(limit)
    types = ["restock", "co-promotion", "shelf-placement"]
    results = []
    for i, rule in enumerate(rules):
        b = _rand_branch()
        rtype = random.choice(types)
        sku = rule.antecedent[0]
        if rtype == "co-promotion":
            msg = f"Bundle {sku} with {rule.consequent[0]} — lift {rule.lift}, confidence {rule.confidence:.0%}"
        elif rtype == "restock":
            msg = f"{sku} trending low on shelf at {b['branch_name']} — restock recommended"
        else:
            msg = f"Move {sku} to eye-level shelf at {b['branch_name']} to improve share of shelf"
        results.append(
            Recommendation(
                id=f"REC-{i:04d}",
                outlet_id=b["outlet_id"],
                branch_name=b["branch_name"],
                sku=sku,
                recommendation_type=rtype,
                message=msg,
                priority=random.choice(["low", "medium", "high"]),
                related_rule=rule if rtype == "co-promotion" else None,
            )
        )
    return results


def get_stockout_alerts(limit: int = 10) -> list[StockoutAlert]:
    results = []
    for i in range(limit):
        b = _rand_branch()
        detected = datetime.utcnow() - timedelta(hours=random.randint(1, 72))
        results.append(
            StockoutAlert(
                id=f"SO-{i:04d}",
                outlet_id=b["outlet_id"],
                branch_name=b["branch_name"],
                sku=random.choice(SKUS[:-1]),
                detected_at=detected.isoformat() + "Z",
                status=random.choice(["open", "acknowledged", "resolved"]),
            )
        )
    return results


def get_merchandiser_performance(limit: int = 8) -> list[MerchandiserPerformance]:
    results = []
    for i in range(limit):
        results.append(
            MerchandiserPerformance(
                merchandiser_id=f"MER-{i:03d}",
                name=f"Merchandiser {i+1}",
                branches_covered=random.randint(3, 9),
                visits_this_month=random.randint(10, 40),
                avg_sos_pct=round(random.uniform(15, 45), 1),
                avg_osa_pct=round(random.uniform(70, 98), 1),
                planogram_compliance_pct=round(random.uniform(60, 95), 1),
            )
        )
    return results

# --- add to app/services/mock_data.py ---

def get_forecast(chain: str | None = None, branch: str | None = None, sku: str | None = None):
    rows = [
        {"chain": "Naivas", "branch": "Westlands", "sub_county": "WESTLANDS", "sku": "BB ORI 250g",
         "flavor": "ORI", "pack_size_g": 250, "forecast_week_start": "2026-10-15",
         "lag_1w": 18, "rolling_mean_3w": 16.3, "predicted_units_next_week": 17.1},
        {"chain": "Carrefour", "branch": "Sarit", "sub_county": "WESTLANDS", "sku": "BB VANILLA 250g",
         "flavor": "VANILLA", "pack_size_g": 250, "forecast_week_start": "2026-10-15",
         "lag_1w": 9, "rolling_mean_3w": 8.1, "predicted_units_next_week": 8.6},
    ]
    if chain:
        rows = [r for r in rows if r["chain"] == chain]
    if branch:
        rows = [r for r in rows if r["branch"] == branch]
    if sku:
        rows = [r for r in rows if r["sku"] == sku]
    return rows


def get_forecast_with_promo(chain=None, branch=None, sku=None, promo=None):
    base = get_forecast(chain, branch, sku)
    return [dict(row, predicted_units_next_week=round(row["predicted_units_next_week"] * 1.3, 2))
            for row in base]


def get_new_outlet_forecast(req):
    catch = req.catchment_pop_2026 or 40000
    scale = (catch / 40000) ** 0.35
    skus = [("BB ORI 500g", "ORI", 500, 9.4), ("BB ORI 250g", "ORI", 250, 8.1),
            ("BB S4B 250g", "S4B", 250, 6.2), ("BB CHOCO 100g", "CHOCO", 100, 4.0),
            ("BB VANILLA 250g", "VANILLA", 250, 2.3)]
    rows = [{"sku": s, "flavor": f, "pack_size_g": p, "predicted_units_per_week": round(u * scale, 2)}
            for s, f, p, u in skus]
    return {"chain": req.chain, "branch": req.branch, "sub_county": req.sub_county or "EMBAKASI",
            "dominant_income_segment": req.dominant_income_segment or "middle",
            "catchment_pop_2026": catch, "built_growth_annual": req.built_growth_annual or 0.025,
            "total_units_per_week": round(sum(r["predicted_units_per_week"] for r in rows), 1),
            "skus": rows}
