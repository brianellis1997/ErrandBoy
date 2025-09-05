"""Health check endpoints"""

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from groupchat.config import settings
from groupchat.db.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/")
async def health_check() -> dict[str, Any]:
    """Basic health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "GroupChat API",
        "version": "0.1.0",
    }


@router.get("/ready")
async def readiness_check(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Readiness check including database connectivity"""
    checks = {
        "api": "healthy",
        "database": "unknown",
        "redis": "unknown",
    }

    # Check database
    try:
        result = await db.execute(text("SELECT 1"))
        checks["database"] = "healthy" if result.scalar() == 1 else "unhealthy"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        checks["database"] = "unhealthy"

    # Check Redis (if enabled)
    if settings.redis_url:
        try:
            import redis.asyncio as redis
            client = redis.from_url(str(settings.redis_url))
            await client.ping()
            checks["redis"] = "healthy"
            await client.close()
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            checks["redis"] = "unhealthy"
    else:
        checks["redis"] = "disabled"

    # Determine overall status
    overall_status = "healthy"
    if "unhealthy" in checks.values():
        overall_status = "degraded"
    if checks["database"] == "unhealthy":
        overall_status = "unhealthy"

    return {
        "status": overall_status,
        "timestamp": datetime.utcnow().isoformat(),
        "checks": checks,
    }


@router.get("/live")
async def liveness_check() -> dict[str, str]:
    """Kubernetes liveness probe endpoint"""
    return {"status": "alive"}
