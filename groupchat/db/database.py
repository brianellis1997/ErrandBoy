"""Database connection and session management"""

import logging
import os
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base

from groupchat.config import settings

logger = logging.getLogger(__name__)

# Create async engine
engine = create_async_engine(
    str(settings.database_url),
    echo=settings.app_debug,
    pool_pre_ping=True,
    pool_size=20,
    max_overflow=40,
)

# Create session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Create declarative base
Base = declarative_base()


async def init_db() -> None:
    """Initialize database connection and create tables if needed"""
    try:
        # Import models to register them with Base.metadata
        from groupchat.db import models  # noqa: F401

        # Skip if using default placeholder URL
        db_url = str(settings.database_url)
        if "user:password@localhost" in db_url and "DATABASE_URL" not in os.environ:
            logger.warning("Database not configured - using mock mode")
            return

        # Test connection
        logger.info(f"Connecting to database...")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database connection established successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}", exc_info=True)
        # Don't raise for now to allow app to start without database
        logger.warning("Running without database connection")


async def close_db() -> None:
    """Close database connections"""
    await engine.dispose()
    logger.info("Database connections closed")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to get database session"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
