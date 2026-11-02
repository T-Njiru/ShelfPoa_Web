"""
Smoke test for the ShelfPoa API. Run against your REAL backend:

    cd C:\\Users\\tednj\\Desktop\\ShelfPoa\\ShelfPoa_Web\\shelfpoa_website\\backend
    uvicorn app.main:app --port 8000        (terminal 1)
    python smoke_test.py                    (terminal 2)

Requires: pip install requests
Optional: python smoke_test.py http://127.0.0.1:8000
"""
import sys
import requests

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
results = []


def check(name, method, path, expect=200, json=None, validate=None):
    try:
        r = requests.request(method, BASE + path, json=json, timeout=30)
        ok = r.status_code == expect
        detail = f"HTTP {r.status_code}"
        if ok and validate:
            msg = validate(r.json())
            if msg:
                ok, detail = False, msg
    except Exception as e:
        ok, detail = False, f"{type(e).__name__}: {e}"
    results.append(ok)
    print(f"[{'PASS' if ok else 'FAIL'}] {name:<48} {detail}")


# --- health: confirms live mode + models loaded ---
check("health: ml_mode=live, models_loaded=true", "GET", "/api/health",
      validate=lambda d: None if d.get("ml_mode") == "live" and d.get("models_loaded") is True
      else f"got {d}")

# --- forecast ---
Q = "?chain=Naivas&branch=Westlands&sku=BB%20ORI%20250g"
# Plausibility, not just "> 0": this row's recent history is ~15 units/week, so a sane
# forecast is within roughly 0.5x-2x of its own rolling mean. A wildly different number
# means the model is being misread (e.g. XGBoost version mismatch) -- exactly the bug
# that a bare "> 0" check let through.
def _plausible(d):
    if len(d) != 1:
        return f"expected 1 row, got {len(d)}"
    row = d[0]
    pred, ref = row["predicted_units_next_week"], row["rolling_mean_3w"]
    if not (0.5 * ref <= pred <= 2.0 * ref):
        return f"forecast {pred:.2f} is implausible vs rolling mean {ref:.2f} -> check xgboost version / model file"
    return None


check("forecast: single branch-SKU is plausible", "GET", "/api/forecast" + Q, validate=_plausible)
check("forecast: all rows (expect 1125)", "GET", "/api/forecast",
      validate=lambda d: None if len(d) == 1125 else f"got {len(d)} rows")
check("forecast: unknown branch -> empty list", "GET", "/api/forecast?branch=Nope",
      validate=lambda d: None if d == [] else f"got {d}")

promo = {"promo_days_in_week": 7, "mean_discount_pct": 20.0, "dominant_promo_type": "price_discount"}
def _promo_sane(d):
    base = requests.get(BASE + "/api/forecast" + Q, timeout=30).json()[0]["predicted_units_next_week"]
    promo_pred = d[0]["predicted_units_next_week"]
    if not (1.05 * base <= promo_pred <= 3.0 * base):
        return f"promo {promo_pred:.2f} vs baseline {base:.2f}: expected +5% to +200% uplift"
    return None


check("forecast/with-promo: sane uplift vs baseline", "POST", "/api/forecast/with-promo" + Q,
      json=promo, validate=_promo_sane)
check("forecast/with-promo: bad body -> 422", "POST", "/api/forecast/with-promo" + Q, expect=422,
      json={"promo_days_in_week": "seven"})

# --- basket ---
check("basket/rules: default", "GET", "/api/basket/rules",
      validate=lambda d: None if len(d) > 0 and "lift" in d[0] else f"got {d}")
check("basket/rules: sku filter", "GET", "/api/basket/rules?sku=BB%20VANILLA%20250g&limit=3",
      validate=lambda d: None if 0 < len(d) <= 3 else f"got {len(d)} rows")
check("basket/rules: limit=0 -> 422", "GET", "/api/basket/rules?limit=0", expect=422)

# --- endpoints I have not seen the code for: just confirm they respond ---
for p in ["/api/recommendations", "/api/stockouts", "/api/merchandisers/performance", "/api/outlets"]:
    check(f"responds: {p}", "GET", p)

print(f"\n{sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)