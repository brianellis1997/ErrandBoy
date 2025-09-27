"""Simple test endpoint for debugging"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from groupchat.db.database import get_db
# from groupchat.services.contacts import ContactService
# from groupchat.schemas.contacts import ContactCreate

router = APIRouter()

@router.post("/test-create-contact")
async def test_create_contact():
    """Ultra simple test - no database, no services"""
    return {"test": "success", "message": "Simple endpoint works"}

@router.post("/test-with-db")
async def test_with_db(db: AsyncSession = Depends(get_db)):
    """Test with database connection only"""
    try:
        result = await db.execute("SELECT 1 as test")
        row = result.fetchone()
        return {"database": "connected", "test_query": row[0]}
    except Exception as e:
        return {"database": "error", "message": str(e)}