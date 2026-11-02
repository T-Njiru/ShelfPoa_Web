"""
Outlet master data lives in outlets_universe already — this isn't model
output, so unlike the other routes it doesn't have a mock/live split.
It just reads straight from the Realtime Database.
"""
from fastapi import APIRouter, HTTPException

from app.core.firebase import get_ref

router = APIRouter(prefix="/api/outlets", tags=["outlets"])


@router.get("")
def list_outlets():
    ref = get_ref("outlets_universe")
    if ref is None:
        raise HTTPException(
            status_code=503,
            detail="Realtime Database not configured — check GOOGLE_APPLICATION_CREDENTIALS.",
        )
    data = ref.get() or {}
    # TODO: shape below assumes each child is a dict of outlet fields keyed
    # by an id — adjust once you confirm outlets_universe's exact structure.
    return [{"id": key, **val} for key, val in data.items()]
