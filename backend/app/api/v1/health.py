from fastapi import APIRouter

from app.core.config import settings

router = APIRouter(prefix="/health", tags=["System"])


@router.get("", summary="Get system health status")
async def health_check():
    return {
        "status": "ok",
        "service": "nexus",
        "version": settings.VERSION,
        "mode": settings.EXECUTION_MODE,
    }
