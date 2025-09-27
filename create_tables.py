#!/usr/bin/env python3
"""Simple script to create database tables for Railway deployment"""

import asyncio
import logging
import os
import sys
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from groupchat.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def create_tables():
    """Create database tables"""
    try:
        logger.info("Starting table creation...")
        logger.info(f"Database URL (masked): {str(settings.database_url)[:50]}...")
        
        # Create engine
        engine = create_async_engine(str(settings.database_url))
        
        # Test connection first
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT 1"))
            logger.info("Database connection successful")
        
        # Import models to register them with Base
        from groupchat.db.models import (
            Contact, Query, Contribution, CompiledAnswer, Citation,
            LedgerEntry, ExpertNotification, ExpertResponse,
            TimestampMixin, SoftDeleteMixin, QueryStatus, 
            ContactStatus, ContributionStatus, NotificationStatus,
            PaymentStatus, LedgerEntryType
        )
        from groupchat.db.database import Base
        
        logger.info("Models imported successfully")
        
        # Create all tables
        async with engine.begin() as conn:
            # First check if pgvector extension exists, if not skip it
            try:
                await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                logger.info("pgvector extension created/verified")
            except Exception as e:
                logger.warning(f"Could not create pgvector extension: {e}")
                logger.info("Proceeding without pgvector - embeddings will be disabled")
            
            # Create all tables
            await conn.run_sync(Base.metadata.create_all)
            logger.info("All tables created successfully")
        
        await engine.dispose()
        logger.info("Table creation completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"Failed to create tables: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(create_tables())
    sys.exit(0 if success else 1)