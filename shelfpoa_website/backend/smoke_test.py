"""
Smoke test for the ShelfPoa API. Run against your REAL backend:

    cd C:\\Users\\tednj\\Desktop\\ShelfPoa\\ShelfPoa_Web\\shelfpoa_website\\backend
    uvicorn app.main:app --port 8000        (terminal 1)
    python smoke_test.py                    (terminal 2)

Requires: pip install requests
Optional: python smoke_test.py http://127.0.0.1:8000

Signing in: the API needs a signed-in admin (app/core/auth.py). The test signs itself in using the
service-account key from backend/.env and the web API key from frontend/.env.local (it appears in
Firebase Authentication as the user "smoke-test"). Or pass a token yourself: set SHELFPOA_TOKEN.
"""
import os
import sys
import time
from pathlib import Path

import requests

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
HERE = Path(__file__).resolve().parent
HEADERS = {}
results = []


def _env_value(path: Path, key: str) -> str:
    if not path.exists():
        return ""
    for line in path.read_text(encoding="utf-8").splitlines():
        k, _, v = line.partition("=")
        if k.strip() == key:
            return v.strip().strip('"').strip("'")
    return ""


def _sign_in() -> str:
    """A Firebase ID token for an admin: SHELFPOA_TOKEN, or minted with the service-account key."""
    if os.getenv("SHELFPOA_TOKEN"):
        return os.environ["SHELFPOA_TOKEN"]
    import firebase_admin
    from firebase_admin import auth, credentials
    key_file = os.getenv("GOOGLE_APPLICATION_CREDENTIALS") or _env_value(HERE / ".env", "GOOGLE_APPLICATION_CREDENTIALS")
    web_key = os.getenv("FIREBASE_WEB_API_KEY") or next(
        (v for v in (_env_value(HERE.parent / "frontend" / f, "VITE_FIREBASE_API_KEY")
                     for f in (".env.local", ".env.production", ".env")) if v), "")
    if not key_file or not web_key:
        raise RuntimeError("need GOOGLE_APPLICATION_CREDENTIALS (backend/.env) and VITE_FIREBASE_API_KEY "
                           "(frontend/.env.local), or set SHELFPOA_TOKEN")
    key_path = Path(key_file) if Path(key_file).is_absolute() else (HERE / key_file).resolve()
    if not firebase_admin._apps:
        firebase_admin.initialize_app(credentials.Certificate(str(key_path)))
    custom = auth.create_custom_token("smoke-test", {"role": "admin"})
    r = requests.post("https://identitytoolkit.googleapis.com/v1/accounts:signInWithCustomToken",
                      params={"key": web_key}, timeout=30,
                      json={"token": custom.decode() if isinstance(custom, bytes) else custom,
                            "returnSecureToken": True})
    r.raise_for_status()
    return r.json()["idToken"]


def check(name, method, path, expect=200, json=None, validate=None, headers=None, max_seconds=None):
    try:
        t0 = time.perf_counter()
        r = requests.request(method, BASE + path, json=json, timeout=30,
                             headers=HEADERS if headers is None else headers)
        took = time.perf_counter() - t0
        ok = r.status_code == expect
        detail = f"HTTP {r.status_code}"
        if ok and max_seconds is not None:
            detail += f" in {took:.2f} s"
            if took > max_seconds:
                ok, detail = False, f"took {took:.2f} s (limit {max_seconds} s)"
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

# --- sign-in (D-17): no token -> 401; then sign in for the rest ---
try:
    AUTH_ON = bool(requests.get(BASE + "/api/health", timeout=30).json().get("auth_required"))
except Exception:
    AUTH_ON = False
if AUTH_ON:
    check("auth: no token -> 401", "GET", "/api/forecast", expect=401, headers={})
    check("auth: made-up token -> 401", "GET", "/api/forecast", expect=401,
          headers={"Authorization": "Bearer not-a-real-token"})
    try:
        HEADERS = {"Authorization": f"Bearer {_sign_in()}"}
        print("       signed in for the remaining checks")
    except Exception as e:
        sys.exit(f"Could not sign in ({type(e).__name__}: {e}).")
else:
    print("[NOTE] AUTH_REQUIRED is off on this server: the sign-in checks are skipped")

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
# D-08: unknown filter values are an error, not an empty list
check("forecast: unknown branch -> 422", "GET", "/api/forecast?branch=Nope", expect=422)
check("forecast: unknown SKU -> 422", "GET", "/api/forecast?sku=BB%20NOPE%201Kg", expect=422)
check("forecast: branch not in that chain -> 422", "GET", "/api/forecast?chain=Naivas&branch=Junction", expect=422)
check("forecast: filter ignores case", "GET", "/api/forecast?chain=naivas&branch=umoja",
      validate=lambda d: None if d and all(r["chain"] == "Naivas" for r in d) else f"got {len(d)} rows")

promo = {"promo_days_in_week": 7, "mean_discount_pct": 20.0, "dominant_promo_type": "price_discount"}
def _promo_sane(d):
    base = requests.get(BASE + "/api/forecast" + Q, timeout=30, headers=HEADERS).json()[0]["predicted_units_next_week"]
    promo_pred = d[0]["predicted_units_next_week"]
    if not (1.05 * base <= promo_pred <= 3.0 * base):
        return f"promo {promo_pred:.2f} vs baseline {base:.2f}: expected +5% to +200% uplift"
    return None


check("forecast/with-promo: sane uplift vs baseline", "POST", "/api/forecast/with-promo" + Q,
      json=promo, validate=_promo_sane)
check("forecast/with-promo: bad body -> 422", "POST", "/api/forecast/with-promo" + Q, expect=422,
      json={"promo_days_in_week": "seven"})

# D-08: impossible promotion values
for label, bad in [("9 promo days", {"promo_days_in_week": 9, "mean_discount_pct": 10, "dominant_promo_type": "price_discount"}),
                   ("150% discount", {"promo_days_in_week": 3, "mean_discount_pct": 150, "dominant_promo_type": "price_discount"}),
                   ("negative discount", {"promo_days_in_week": 3, "mean_discount_pct": -5, "dominant_promo_type": "price_discount"}),
                   ("unknown promo type", {"promo_days_in_week": 3, "mean_discount_pct": 10, "dominant_promo_type": "free_car"}),
                   ("discount with 0 promo days", {"promo_days_in_week": 0, "mean_discount_pct": 20, "dominant_promo_type": "none"})]:
    check(f"forecast/with-promo: {label} -> 422", "POST", "/api/forecast/with-promo" + Q, expect=422, json=bad)

# --- new outlet (satellite catchment) ---
def _bigger_catchment_sells_more(_):
    def total(pop):
        return requests.post(BASE + "/api/forecast/new-outlet", timeout=30, headers=HEADERS, json={
            "chain": "Naivas", "sub_county": "EMBAKASI", "catchment_pop_2026": pop,
            "built_growth_annual": 0.03}).json()["total_units_per_week"]
    small, big = total(20000), total(100000)
    return None if big > small > 0 else f"20k -> {small}, 100k -> {big}"


check("new-outlet: existing outlet looked up", "POST", "/api/forecast/new-outlet",
      json={"chain": "Naivas", "branch": "Umoja"},
      validate=lambda d: None if d["total_units_per_week"] > 0 and len(d["skus"]) == 13 else f"got {d}")
check("new-outlet: opening plan (stock >= 1 week, facings add up)", "POST", "/api/forecast/new-outlet",
      json={"chain": "Naivas", "branch": "Umoja", "blueband_facings": 40},
      validate=lambda d: None if d["facings_total"] == 40 and all(
          s["opening_stock_units"] >= s["predicted_units_per_week"] for s in d["skus"]) else f"got {d}")
check("new-outlet: options list sites", "GET", "/api/forecast/new-outlet/options",
      validate=lambda d: None if d["chains"] and len(d["sites"]) > 0 else f"got {d}")
check("new-outlet: map pin -> catchment (needs scripts/build_catchment_grid.py run once)", "GET",
      "/api/forecast/new-outlet/location?lat=-1.2891&lon=36.7620",
      validate=lambda d: None if d["pop_2km"] > d["pop_1km"] > 0 and d["sub_county"] else f"got {d}")
check("new-outlet: pin outside Nairobi -> 422", "GET", "/api/forecast/new-outlet/location?lat=-0.5&lon=36.7",
      expect=422)
check("new-outlet: more people nearby -> more demand", "POST", "/api/forecast/new-outlet",
      json={"chain": "Naivas", "sub_county": "EMBAKASI", "catchment_pop_2026": 20000,
            "built_growth_annual": 0.03}, validate=_bigger_catchment_sells_more)
check("new-outlet: unknown sub-county -> 422", "POST", "/api/forecast/new-outlet", expect=422,
      json={"chain": "Naivas", "sub_county": "NOWHERE", "catchment_pop_2026": 20000,
            "built_growth_annual": 0.03})

# --- basket ---
check("basket/rules: default", "GET", "/api/basket/rules",
      validate=lambda d: None if len(d) > 0 and "lift" in d[0] else f"got {d}")
check("basket/rules: sku filter", "GET", "/api/basket/rules?sku=BB%20VANILLA%20500g&limit=3",
      validate=lambda d: None if 0 < len(d) <= 3 else f"got {len(d)} rows")
check("basket/rules: limit=0 -> 422", "GET", "/api/basket/rules?limit=0", expect=422)
check("basket/rules: unknown SKU -> 422", "GET", "/api/basket/rules?sku=BB%20NOPE%201Kg", expect=422)

# --- endpoints I have not seen the code for: just confirm they respond ---
for p in ["/api/recommendations", "/api/stockouts", "/api/outlets"]:
    check(f"responds: {p}", "GET", p)

# D-09: merchandiser performance. The server loads this at startup and refreshes it in the background,
# so neither call should wait for Firebase. Set PERF_LIMIT_S to the limit in your test plan (TC-14).
PERF_LIMIT_S = 2.0
check("merchandisers/performance: first call", "GET", "/api/merchandisers/performance", max_seconds=PERF_LIMIT_S)
check("merchandisers/performance: repeat call", "GET", "/api/merchandisers/performance", max_seconds=0.5)

print(f"\n{sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)