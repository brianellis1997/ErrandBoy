"""Admin API endpoints"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, text
from sqlalchemy.ext.asyncio import AsyncSession

from groupchat.config import settings
from groupchat.db.database import get_db
from groupchat.db.models import Contact, Query, QueryStatus

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/stats")
async def get_system_stats(db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """Get system statistics for admin dashboard"""
    try:
        stats = {}
        
        # Database connectivity check
        try:
            await db.execute(text("SELECT 1"))
            stats["database_status"] = "healthy"
        except Exception as e:
            stats["database_status"] = "unhealthy"
            logger.error(f"Database health check failed: {e}")
        
        # Contact statistics  
        from sqlalchemy import select
        
        total_contacts_result = await db.execute(
            select(func.count(Contact.id)).where(Contact.deleted_at.is_(None))
        )
        total_contacts = total_contacts_result.scalar() or 0
        
        active_contacts_result = await db.execute(
            select(func.count(Contact.id)).where(
                Contact.deleted_at.is_(None),
                Contact.is_available == True
            )
        )
        active_contacts = active_contacts_result.scalar() or 0
        
        # Query statistics
        total_queries_result = await db.execute(select(func.count(Query.id)))
        total_queries = total_queries_result.scalar() or 0
        
        # Recent activity (last 24 hours)
        last_24h = datetime.utcnow() - timedelta(hours=24)
        
        recent_contacts_result = await db.execute(
            select(func.count(Contact.id)).where(Contact.created_at >= last_24h)
        )
        recent_contacts = recent_contacts_result.scalar() or 0
        
        recent_queries_result = await db.execute(
            select(func.count(Query.id)).where(Query.created_at >= last_24h)
        )
        recent_queries = recent_queries_result.scalar() or 0
        
        # Query status breakdown
        pending_queries_result = await db.execute(
            select(func.count(Query.id)).where(Query.status == QueryStatus.PENDING)
        )
        pending_queries = pending_queries_result.scalar() or 0
        
        routing_queries_result = await db.execute(
            select(func.count(Query.id)).where(Query.status == QueryStatus.ROUTING)
        )
        routing_queries = routing_queries_result.scalar() or 0
        
        collecting_queries_result = await db.execute(
            select(func.count(Query.id)).where(Query.status == QueryStatus.COLLECTING)
        )
        collecting_queries = collecting_queries_result.scalar() or 0
        
        completed_queries_result = await db.execute(
            select(func.count(Query.id)).where(Query.status == QueryStatus.COMPLETED)
        )
        completed_queries = completed_queries_result.scalar() or 0
        
        # Build response
        stats.update({
            "timestamp": datetime.utcnow().isoformat(),
            "service_info": {
                "name": "GroupChat API",
                "version": "0.1.0",
                "environment": settings.app_env,
                "debug_mode": settings.app_debug,
            },
            "feature_flags": {
                "sms_enabled": settings.enable_sms,
                "payments_enabled": settings.enable_payments,
                "real_embeddings_enabled": settings.enable_real_embeddings,
            },
            "database": {
                "status": stats["database_status"],
                "url_configured": bool(settings.database_url),
            },
            "redis": {
                "configured": bool(settings.redis_url),
            },
            "contacts": {
                "total": total_contacts,
                "active": active_contacts,
                "recent_24h": recent_contacts,
            },
            "queries": {
                "total": total_queries,
                "recent_24h": recent_queries,
                "by_status": {
                    "pending": pending_queries,
                    "routing": routing_queries,
                    "collecting": collecting_queries,
                    "completed": completed_queries,
                },
            },
            "integrations": {
                "twilio": {
                    "configured": bool(settings.twilio_account_sid and settings.twilio_auth_token),
                    "enabled": settings.enable_sms,
                },
                "openai": {
                    "configured": bool(settings.openai_api_key),
                },
                "stripe": {
                    "configured": bool(settings.stripe_secret_key),
                    "enabled": settings.enable_payments,
                },
            },
        })
        
        return stats
        
    except Exception as e:
        logger.error(f"Error fetching system stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch system statistics",
        )


@router.get("/health")
async def admin_health_check(db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """Detailed health check for admin purposes"""
    try:
        health_status = {
            "timestamp": datetime.utcnow().isoformat(),
            "overall_status": "healthy",
            "checks": {},
        }
        
        # Database check
        try:
            result = await db.execute(text("SELECT version()"))
            db_version = result.scalar()
            health_status["checks"]["database"] = {
                "status": "healthy",
                "version": db_version,
                "connection": "active",
            }
        except Exception as e:
            health_status["checks"]["database"] = {
                "status": "unhealthy",
                "error": str(e),
            }
            health_status["overall_status"] = "degraded"
        
        # Redis check
        if settings.redis_url:
            try:
                import redis.asyncio as redis
                client = redis.from_url(str(settings.redis_url))
                await client.ping()
                info = await client.info()
                health_status["checks"]["redis"] = {
                    "status": "healthy",
                    "version": info.get("redis_version"),
                    "connected_clients": info.get("connected_clients"),
                }
                await client.close()
            except Exception as e:
                health_status["checks"]["redis"] = {
                    "status": "unhealthy", 
                    "error": str(e),
                }
                if health_status["overall_status"] == "healthy":
                    health_status["overall_status"] = "degraded"
        else:
            health_status["checks"]["redis"] = {"status": "not_configured"}
        
        # Configuration checks
        health_status["checks"]["configuration"] = {
            "database_url": "configured" if settings.database_url else "missing",
            "openai_key": "configured" if settings.openai_api_key else "missing",
            "twilio_credentials": "configured" if (
                settings.twilio_account_sid and settings.twilio_auth_token
            ) else "missing",
            "stripe_credentials": "configured" if settings.stripe_secret_key else "missing",
        }
        
        return health_status
        
    except Exception as e:
        logger.error(f"Error in admin health check: {e}")
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "overall_status": "unhealthy",
            "error": str(e),
        }


@router.get("/queries")
async def get_admin_queries(
    limit: int = 50,
    offset: int = 0,
    status_filter: str | None = None,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Get queries for admin dashboard with detailed information"""
    try:
        from sqlalchemy import select, desc
        
        # Build query with filters
        query = select(Query).order_by(desc(Query.created_at))
        
        if status_filter:
            query = query.where(Query.status == status_filter)
            
        query = query.limit(limit).offset(offset)
        
        result = await db.execute(query)
        queries = result.scalars().all()
        
        # Format queries for dashboard
        formatted_queries = []
        for query_obj in queries:
            formatted_queries.append({
                "id": str(query_obj.id),
                "question_text": query_obj.question_text,
                "status": query_obj.status.value if query_obj.status else "unknown",
                "created_at": query_obj.created_at.isoformat() if query_obj.created_at else None,
                "max_spend_cents": query_obj.total_cost_cents,
                "user_phone": query_obj.user_phone,
                "expert_count": len(query_obj.matches) if hasattr(query_obj, 'matches') else 0,
                "response_count": len(query_obj.responses) if hasattr(query_obj, 'responses') else 0,
            })
        
        return {
            "success": True,
            "data": {
                "queries": formatted_queries,
                "total_count": len(formatted_queries),
                "limit": limit,
                "offset": offset,
                "status_filter": status_filter
            }
        }
        
    except Exception as e:
        logger.error(f"Error fetching admin queries: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch queries",
        )


@router.get("/contacts/summary") 
async def get_contacts_summary(db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """Get contact/expert summary for admin dashboard"""
    try:
        from sqlalchemy import select, func
        
        # Get top experts by activity (mock implementation for now)
        contacts_result = await db.execute(
            select(Contact).where(
                Contact.deleted_at.is_(None),
                Contact.is_available == True
            ).limit(10)
        )
        contacts = contacts_result.scalars().all()
        
        # Format contacts for dashboard
        formatted_contacts = []
        for contact in contacts:
            formatted_contacts.append({
                "id": str(contact.id),
                "name": contact.name,
                "phone": contact.phone_number,
                "expertise_areas": (contact.expertise_summary or "General").split(", ") if contact.expertise_summary else ["General"],
                "trust_score": contact.trust_score or 85,  # Default score
                "response_rate": 90,  # Mock data
                "avg_response_time": "2.5h",  # Mock data  
                "total_earnings": 1250,  # Mock data
                "queries_answered": 12,  # Mock data
                "created_at": contact.created_at.isoformat() if contact.created_at else None
            })
        
        return {
            "success": True,
            "data": {
                "experts": formatted_contacts,
                "total_experts": len(formatted_contacts),
                "metrics": {
                    "avg_trust_score": 87,  # Mock
                    "avg_response_rate": 89,  # Mock
                    "total_earnings": sum(e["total_earnings"] for e in formatted_contacts)
                }
            }
        }
        
    except Exception as e:
        logger.error(f"Error fetching contacts summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch contacts summary",
        )


@router.post("/seed-demo-data")
async def seed_demo_data(db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """Seed the database with demo/test data"""
    try:
        from scripts.enhanced_seed_data import create_enhanced_seed_data

        logger.info("Starting demo data seeding via API...")
        await create_enhanced_seed_data()
        logger.info("Demo data seeding completed successfully")

        return {
            "success": True,
            "message": "Demo data seeded successfully",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Error seeding demo data: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to seed demo data: {str(e)}"
        )