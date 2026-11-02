import secrets
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from firebase_admin import auth, db
from app.core.auth import require_role               # was app.auth

router = APIRouter(prefix="/admin/users",          # was "/api/admin/users"
                   tags=["users"],
                   dependencies=[Depends(require_role("admin"))])

Role = Literal["admin", "manager", "merchandiser"]

class CreateUser(BaseModel):
    email: EmailStr
    display_name: str
    role: Role

class UpdateRole(BaseModel):
    role: Role

@router.post("", status_code=201)
def create_user(body: CreateUser):
    try:
        u = auth.create_user(email=body.email, display_name=body.display_name,
                             password=secrets.token_urlsafe(24))  # throwaway
    except auth.EmailAlreadyExistsError:
        raise HTTPException(409, "Email already registered")
    auth.set_custom_user_claims(u.uid, {"role": body.role})
    db.reference(f"users/{u.uid}").set({
        "email": body.email, "display_name": body.display_name,
        "role": body.role, "active": True, "created_at": {".sv": "timestamp"},
    })
    return {"uid": u.uid}

@router.get("")
def list_users():
    return db.reference("users").get() or {}

@router.patch("/{uid}/role")
def update_role(uid: str, body: UpdateRole):
    auth.set_custom_user_claims(uid, {"role": body.role})
    auth.revoke_refresh_tokens(uid)  # forces re-login so the new claim takes effect
    db.reference(f"users/{uid}/role").set(body.role)
    return {"ok": True}

@router.post("/{uid}/disable")
def disable_user(uid: str, me: dict = Depends(require_role("admin"))):
    if uid == me["uid"]:
        raise HTTPException(400, "You can't disable yourself")
    auth.update_user(uid, disabled=True)
    auth.revoke_refresh_tokens(uid)
    db.reference(f"users/{uid}/active").set(False)
    return {"ok": True}

@router.post("/{uid}/enable")
def enable_user(uid: str):
    auth.update_user(uid, disabled=False)
    db.reference(f"users/{uid}/active").set(True)
    return {"ok": True}