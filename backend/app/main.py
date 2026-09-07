from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import all models to ensure they register with Base.metadata
import app.models
from app.api.demo import router as demo_router
from app.api.v1.router import api_v1_router
from app.core.config import settings
from app.core.database import Base, async_engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database tables for local dev / testing
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Autonomous OSINT, Reconnaissance & Intelligence Research Platform API",
    version=settings.VERSION,
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register Demo UI route
app.include_router(demo_router)

# Register API v1 routes
app.include_router(api_v1_router, prefix=settings.API_V1_STR)


@app.get("/health", tags=["System"])
async def root_health_check():
    return {
        "status": "ok",
        "service": "nexus",
        "version": settings.VERSION,
        "mode": settings.EXECUTION_MODE,
    }
