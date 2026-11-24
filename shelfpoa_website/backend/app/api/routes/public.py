"""
Public, unauthenticated routes. Aggregate counts only -- nothing here identifies a person, an
outlet's results or any model output.

    GET /api/public/stats   live numbers for the admin sign-in page (last 30 days)

The sign-in page calling this also wakes the free-tier server, so the dashboard is ready by the
time the user has signed in.
"""
from fastapi import APIRouter, HTTPException

from app.services import merchandiser_performance

router = APIRouter(prefix="/api/public", tags=["public"])


@router.get("/stats")
def stats():
    data = merchandiser_performance.public_stats()
    if data is None:
        raise HTTPException(503, "Live figures are unavailable right now.")
    return data
