"""
GET /health — Health check for Render.
Returns 200 with basic status info. Render pings this to keep the service alive.
"""
from datetime import datetime, timezone

from fastapi import APIRouter

from app.core.config import settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "provider": settings.DEFAULT_LLM_PROVIDER,
        "model": settings.DEFAULT_MODEL,
        "database": "postgresql" if settings.is_postgres else "sqlite",
    }
