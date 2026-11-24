"""
Unit tests for the backend's own logic (no Firebase, no network). Run from backend\\ :

    pip install -r requirements-dev.txt
    python -m pytest -q

smoke_test.py is the separate end-to-end check against a running server; these tests cover the
rules underneath it: sign-in checks, input validation, the opening-order maths, stock-out
resolution, the public login-page figures and the demo-data seeding.
"""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

# --------------------------------------------------------------------------- fake Realtime Database
STORE: dict = {}


class FakeRef:
    def __init__(self, path):
        self.path = [p for p in str(path).strip("/").split("/") if p]

    def _node(self, create=False):
        d = STORE
        for p in self.path:
            if p not in d:
                if not create:
                    return None
                d[p] = {}
            d = d[p]
        return d

    def get(self):
        return self._node()

    def set(self, value):
        *parent, last = self.path
        d = STORE
        for p in parent:
            d = d.setdefault(p, {})
        d[last] = value

    def update(self, data):
        node = self._node(create=True)
        for k, v in data.items():
            if v is None:
                node.pop(k, None)
            else:
                node[k] = v

    def child(self, c):
        return FakeRef("/".join(self.path + [c]))

    def order_by_key(self):
        return self

    def limit_to_last(self, n):
        return self


@pytest.fixture
def fake_db(monkeypatch):
    STORE.clear()
    import app.core.firebase as fb
    import app.api.routes.stockouts as stockouts
    import app.services.merchandiser_performance as mp
    monkeypatch.setattr(fb, "get_ref", lambda path="/": FakeRef(path))
    monkeypatch.setattr(fb, "ready", lambda: True)
    monkeypatch.setattr(stockouts, "get_ref", lambda path="/": FakeRef(path))
    monkeypatch.setattr(mp, "get_ref", lambda node: FakeRef(node))
    mp._cache.update(at=0.0, data=None, refreshing=False)
    return STORE


# --------------------------------------------------------------------------- allowed domains
def test_email_domains():
    from app.core.config import settings
    assert settings.email_allowed("Jane.Doe@Upfield.com")
    assert settings.email_allowed("a.b@florafoodgroup.com")
    assert not settings.email_allowed("someone@gmail.com")
    assert not settings.email_allowed("upfield.com@gmail.com")
    assert not settings.email_allowed("")
    assert not settings.email_allowed(None)


# --------------------------------------------------------------------------- API sign-in (D-17 + Google)
class _Req:
    def __init__(self, token):
        self.headers = {"Authorization": f"Bearer {token}"} if token else {}


@pytest.fixture
def auth_env(fake_db, monkeypatch):
    from app.core import auth
    from app.core.config import settings
    monkeypatch.setattr(settings, "auth_required", True)
    auth._roles.clear()
    fake_db["users"] = {"admin-pw": {"role": "admin"}, "admin-g": {"role": "admin"},
                        "merch": {"role": "merchandiser"}, "gone": {"role": "admin", "active": False}}
    # "new-g-*": Google accounts nobody has activated yet (no users/{uid} record)
    tokens = {
        "pw": {"uid": "admin-pw", "email": "ted@gmail.com", "firebase": {"sign_in_provider": "password"}},
        "g-ffg": {"uid": "admin-g", "email": "a@upfield.com", "email_verified": True,
                  "firebase": {"sign_in_provider": "google.com"}},
        "g-gmail": {"uid": "admin-g", "email": "a@gmail.com", "email_verified": True,
                    "firebase": {"sign_in_provider": "google.com"}},
        "new-g-gmail": {"uid": "new-1", "email": "x@gmail.com", "email_verified": True,
                        "firebase": {"sign_in_provider": "google.com"}},
        "new-g-ffg": {"uid": "new-2", "email": "x@upfield.com", "email_verified": True,
                      "firebase": {"sign_in_provider": "google.com"}},
        "merch": {"uid": "merch", "firebase": {"sign_in_provider": "password"}},
        "gone": {"uid": "gone", "firebase": {"sign_in_provider": "password"}},
    }

    def verify(token):
        if token not in tokens:
            raise ValueError("bad token")
        return tokens[token]

    monkeypatch.setattr(auth.fb_auth, "verify_id_token", verify)
    return auth.dashboard_user


@pytest.mark.parametrize("token,expected", [
    ("pw", 200),        # admin, email/password (any domain: admin-created)
    ("g-ffg", 200),     # admin, Google, Flora Food Group domain
    ("g-gmail", 200),   # Gmail via Google, but an admin already set the account up -> allowed
    ("new-g-gmail", 403),  # Gmail via Google, never set up -> "FFG accounts only"
    ("new-g-ffg", 403),    # FFG Google account, not activated yet -> no access
    ("merch", 403),     # merchandisers can't use the admin API
    ("gone", 403),      # deactivated account
    ("junk", 401),      # invalid token
    (None, 401),        # no token
])
def test_api_sign_in(auth_env, token, expected):
    if expected == 200:
        assert auth_env(_Req(token))["role"] == "admin"
    else:
        with pytest.raises(HTTPException) as e:
            auth_env(_Req(token))
        assert e.value.status_code == expected
        if token == "new-g-gmail":
            assert "Flora Food Group" in e.value.detail


# --------------------------------------------------------------------------- input validation (D-08)
def test_filters_resolve_case_and_unknowns():
    from app.api import filters
    chain, branch, sku = filters.resolve("naivas", "  umoja ", "bb ori 500g")
    assert (chain, branch, sku) == ("Naivas", "Umoja", "BB ORI 500g")
    for bad in ({"branch": "Nope"}, {"sku": "BB NOPE"}, {"chain": "Naivas", "branch": "Junction"}):
        with pytest.raises(HTTPException) as e:
            filters.resolve(**bad)
        assert e.value.status_code == 422


@pytest.mark.parametrize("promo,ok", [
    ({"promo_days_in_week": 7, "mean_discount_pct": 20, "dominant_promo_type": "price_discount"}, True),
    ({}, True),
    ({"promo_days_in_week": 9, "mean_discount_pct": 10, "dominant_promo_type": "price_discount"}, False),
    ({"promo_days_in_week": 3, "mean_discount_pct": 150, "dominant_promo_type": "price_discount"}, False),
    ({"promo_days_in_week": 0, "mean_discount_pct": 20}, False),
    ({"promo_days_in_week": 3, "mean_discount_pct": 0}, False),
])
def test_promo_bounds(promo, ok):
    from pydantic import ValidationError
    from app.models.schemas import PlannedPromo
    if ok:
        PlannedPromo(**promo)
    else:
        with pytest.raises(ValidationError):
            PlannedPromo(**promo)


# --------------------------------------------------------------------------- opening order / facings
def test_facings_add_up_and_follow_demand():
    from app.ml.outlet_planner import _allocate_facings
    f = _allocate_facings([50, 30, 15, 5, 0.5], 40)
    assert sum(f) == 40 and min(f) >= 1
    assert f == sorted(f, reverse=True)          # more demand never gets fewer facings
    assert _allocate_facings([], 40) == []


def test_opening_order_covers_the_restock_cycle():
    from app.ml.outlet_planner import plan
    fc = {"skus": [{"sku": "BB ORI 500g", "predicted_units_per_week": 70.0},
                   {"sku": "BB S4B 250g", "predicted_units_per_week": 14.0},
                   {"sku": "BB CHOCO 1Kg", "predicted_units_per_week": 9.0}],   # legacy SKU: dropped
          "total_units_per_week": 93.0, "chain": "Naivas", "sub_county": "EMBAKASI"}
    out = plan(fc, restock_days=7, lead_time_days=2, service_level=0.95, blueband_facings=40)
    skus = {s["sku"]: s for s in out["skus"]}
    assert "BB CHOCO 1Kg" not in skus
    for s in skus.values():
        cycle = s["predicted_units_per_week"] * 9 / 7         # demand over delivery + lead time
        assert s["opening_stock_units"] >= cycle              # never below expected demand
        assert s["safety_stock_units"] > 0
    assert sum(s["facings"] for s in skus.values()) == 40


# --------------------------------------------------------------------------- stock-out resolution
def test_stockout_resolution_persists_and_reopens(fake_db, monkeypatch):
    from fastapi.testclient import TestClient
    from app.core.config import settings
    from app.main import app
    monkeypatch.setattr(settings, "auth_required", False)
    monkeypatch.setattr(settings, "ml_mode", "live")
    fake_db["users"], fake_db["merchandisers"] = {}, {"m-01": {"name": "Brian Otieno"}}

    def reading(key, ts, available):
        fake_db.setdefault("osa_reports", {})[key] = {
            "outlet_id": "naivas-umoja", "branch_name": "Naivas Umoja", "sku": "BB ORI 500g",
            "available": available, "timestamp": ts, "audit_id": key, "merchandiser_id": "m-01"}

    reading("k1", "2026-11-20T08:00:00Z", False)
    c = TestClient(app)
    [alert] = c.get("/api/stockouts?limit=50").json()
    assert alert["status"] == "open"

    r = c.post("/api/stockouts/resolve", json={"outlet_id": alert["outlet_id"], "sku": alert["sku"],
                                               "detected_at": alert["detected_at"]})
    assert r.status_code == 200
    after = c.get("/api/stockouts?limit=50").json()[0]
    assert after["status"] == "resolved"                                         # survives a reload
    assert after["resolved_by"] and after["resolved_at"]                         # who and when

    q = {"outlet_id": alert["outlet_id"], "sku": alert["sku"]}
    events = c.get("/api/stockouts/history", params=q).json()
    assert [e["kind"] for e in events] == ["resolved", "out_of_stock"]           # newest first
    assert events[0]["by"] == after["resolved_by"] and events[1]["by"] == "Brian Otieno"

    reading("k2", "2026-11-23T08:00:00Z", False)                                # found missing again
    assert c.get("/api/stockouts?limit=50").json()[0]["status"] == "open"


def test_resolved_alert_still_listed_when_many_are_open(fake_db, monkeypatch):
    """Regression: with more open alerts than the page asked for, a resolved alert (listed after
    the open ones) fell off the end and vanished after a refresh."""
    from fastapi.testclient import TestClient
    from app.core.config import settings
    from app.main import app
    monkeypatch.setattr(settings, "auth_required", False)
    monkeypatch.setattr(settings, "ml_mode", "live")
    fake_db.update(users={}, merchandisers={}, osa_reports={
        f"k{i}": {"outlet_id": f"o{i}", "branch_name": f"Outlet {i}", "sku": "BB ORI 500g", "available": False,
                  "timestamp": f"2026-11-20T08:{i % 60:02d}:00Z", "audit_id": f"a{i}", "merchandiser_id": "m-01"}
        for i in range(150)})
    c = TestClient(app)
    page = "/api/stockouts?limit=500"                 # what StockoutAlerts.jsx requests
    first = c.get(page).json()[0]
    c.post("/api/stockouts/resolve", json={k: first[k] for k in ("outlet_id", "sku", "detected_at")})
    again = {a["id"]: a["status"] for a in c.get(page).json()}
    assert again[first["id"]] == "resolved" and len(again) == 150


# --------------------------------------------------------------------------- demo data + login figures
def test_seeding_is_recent_and_uses_real_skus():
    import seed_osa_reports
    now = datetime(2026, 11, 24, 12, tzinfo=timezone.utc)
    outlets = [{"chain": "Naivas", "branch": "Umoja", "sub_county": "EMBAKASI"},
               {"chain": "Carrefour", "branch": "Junction", "sub_county": "DAGORETTI"}]
    recs = seed_osa_reports.generate(outlets, days=14, now=now)
    skus = {r["sku"] for r in recs.values()}
    assert len(skus) == 13 and not skus & {"BB CHOCO 1Kg", "BB VANILLA 250g"}
    oldest = min(r["timestamp"] for r in recs.values())
    assert oldest >= (now - timedelta(days=14)).strftime("%Y-%m-%dT%H:%M:%SZ")
    assert all(r["source"] == "simulated" for r in recs.values())


def test_public_stats_count_only_the_last_30_days(fake_db):
    from app.services import merchandiser_performance as mp
    now = datetime(2026, 11, 24, 12, tzinfo=timezone.utc)
    iso = lambda d: (now - timedelta(days=d)).strftime("%Y-%m-%dT%H:%M:%SZ")
    fake_db.update(users={}, merchandisers={}, sos_audits={}, osa_reports={},
                   outlets_universe={"o1": {}, "o2": {}, "o3": {}},
                   audits={"a": {"audit_id": "v1", "merchandiser_id": "m-01", "outlet_id": "o1", "timestamp": iso(2)},
                           "b": {"audit_id": "v2", "merchandiser_id": "m-02", "outlet_id": "o2", "timestamp": iso(10)},
                           "c": {"audit_id": "v3", "merchandiser_id": "m-03", "outlet_id": "o3", "timestamp": iso(45)}})
    s = mp.public_stats(now=now)
    assert (s["active_merchandisers"], s["outlets_audited"], s["store_visits"], s["outlets_total"]) == (2, 2, 2, 3)
    assert set(s) == {"window_days", "active_merchandisers", "outlets_audited", "store_visits", "outlets_total", "as_of"}
