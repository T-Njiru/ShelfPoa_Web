from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware

from app.core.auth import require_role
from app.api.routes import (
    forecast, recommendations, basket, stockouts, merchandisers, outlets, users,
)  # ← match your actual file names

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type"],  # ← Authorization must be here
)

dashboard_only = [Depends(require_role("admin", "manager"))]

for r in (forecast, recommendations, basket, stockouts, merchandisers, outlets):
    app.include_router(r.router, prefix="/api", dependencies=dashboard_only)

# users.py carries its own admin-only guard
app.include_router(users.router, prefix="/api")