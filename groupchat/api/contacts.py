"""Contact management API endpoints"""

import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from groupchat.db.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/")
async def list_contacts(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
):
    """List all contacts with pagination"""
    # TODO: Implement once models are created
    return {
        "contacts": [],
        "total": 0,
        "skip": skip,
        "limit": limit,
    }


@router.post("/")
async def create_contact(
    db: AsyncSession = Depends(get_db),
):
    """Create a new contact"""
    # TODO: Implement once models are created
    raise HTTPException(status_code=501, detail="Not implemented yet")


@router.get("/{contact_id}")
async def get_contact(
    contact_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get a specific contact by ID"""
    # TODO: Implement once models are created
    raise HTTPException(status_code=501, detail="Not implemented yet")


@router.put("/{contact_id}")
async def update_contact(
    contact_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Update a contact"""
    # TODO: Implement once models are created
    raise HTTPException(status_code=501, detail="Not implemented yet")


@router.delete("/{contact_id}")
async def delete_contact(
    contact_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Soft delete a contact"""
    # TODO: Implement once models are created
    raise HTTPException(status_code=501, detail="Not implemented yet")