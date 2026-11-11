from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.auth import dashboard_user
from app.core.config import settings
from app.ml.registry import registry
from app.services import merchandiser_performance
from app.api.routes import forecast, recommendations, basket, stockouts, merchandisers, outlets, shelf


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.ml_mode == "live":
        try:
            registry.load()
            print("ML models loaded")
        except Exception as e:
            # fall back to mock instead of crashing the API
            print(f"ML load failed, staying on mock: {e}")
        merchandiser_performance.warm()   # D-09: read Firebase now, not on the first page view
    yield


app = FastAPI(
    title="ShelfPoa API",
    description="ML-serving layer for the ShelfPoa merchandising intelligence platform.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# every data route needs a signed-in admin or manager; /api/health stays open (uptime checks)
signed_in = [Depends(dashboard_user)]
app.include_router(forecast.router, dependencies=signed_in)
app.include_router(recommendations.router, dependencies=signed_in)
app.include_router(basket.router, dependencies=signed_in)
app.include_router(stockouts.router, dependencies=signed_in)
app.include_router(merchandisers.router, dependencies=signed_in)
app.include_router(outlets.router, dependencies=signed_in)
app.include_router(shelf.router, dependencies=signed_in)


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "ml_mode": settings.ml_mode,
        "models_loaded": registry.ready,
        "auth_required": settings.auth_required,
    }