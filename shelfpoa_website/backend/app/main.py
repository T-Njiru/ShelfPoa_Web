from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.ml.registry import registry
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

app.include_router(forecast.router)
app.include_router(recommendations.router)
app.include_router(basket.router)
app.include_router(stockouts.router)
app.include_router(merchandisers.router)
app.include_router(outlets.router)
app.include_router(shelf.router)


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "ml_mode": settings.ml_mode,
        "models_loaded": registry.ready,
    }