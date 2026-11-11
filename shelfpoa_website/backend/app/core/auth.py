"""
app/core/auth.py
=================
Who may call the API. Every /api route except /api/health needs a signed-in dashboard user:

    Authorization: Bearer <Firebase ID token>

The token is verified with the Firebase Admin SDK, then the caller's role is checked the same
way the admin console does it: users/{uid}.role in the Realtime Database (and active != false).
If there is no users/{uid} record, a `role` custom claim on the token is used instead (claims can
only be set with the service-account key, e.g. by smoke_test.py).

    401  no token, or the token is invalid / expired
    403  signed in, but not an admin or manager (or the account is deactivated)
    503  the backend has no Firebase credentials, so it cannot verify anyone

AUTH_REQUIRED=false in backend/.env switches the check off (local experiments only; never deploy
with it off).
"""
import time

from fastapi import HTTPException, Request
from firebase_admin import auth as fb_auth

from app.core import firebase
from app.core.config import settings

DASHBOARD_ROLES = ("admin", "manager")       # same as ALLOWED_ROLES in frontend/src/services/session.js
ROLE_CACHE_SECONDS = 300                     # a role change / deactivation takes effect within 5 minutes
_roles: dict[str, tuple[float, str]] = {}    # uid -> (looked up at, role)


def _role_of(uid: str, claims: dict) -> str:
    hit = _roles.get(uid)
    if hit and time.monotonic() - hit[0] < ROLE_CACHE_SECONDS:
        return hit[1]
    record = firebase.get_ref(f"users/{uid}").get()
    if isinstance(record, dict):
        role = "" if record.get("active") is False else str(record.get("role") or "")
    else:
        role = str(claims.get("role") or "")
    _roles[uid] = (time.monotonic(), role)
    return role


def require_role(*roles: str):
    """FastAPI dependency: the caller must be signed in with one of `roles`. Returns {uid, email, role}."""
    def dependency(request: Request) -> dict:
        if not settings.auth_required:
            return {"uid": "", "email": "", "role": "auth-disabled"}
        scheme, _, token = request.headers.get("Authorization", "").partition(" ")
        if scheme.lower() != "bearer" or not token.strip():
            raise HTTPException(401, "Sign in to use the ShelfPoa API.", headers={"WWW-Authenticate": "Bearer"})
        if not firebase.ready():
            raise HTTPException(503, "The API cannot verify sign-ins: Firebase credentials are not configured.")
        try:
            claims = fb_auth.verify_id_token(token.strip())
        except fb_auth.CertificateFetchError:
            raise HTTPException(503, "Could not reach Google to verify the sign-in. Try again.")
        except (ValueError, fb_auth.InvalidIdTokenError):
            raise HTTPException(401, "Your session has expired. Sign in again.",
                                headers={"WWW-Authenticate": "Bearer"})
        role = _role_of(claims["uid"], claims)
        if role not in roles:
            raise HTTPException(403, "This account does not have access to the admin console.")
        return {"uid": claims["uid"], "email": claims.get("email", ""), "role": role}
    return dependency


dashboard_user = require_role(*DASHBOARD_ROLES)
