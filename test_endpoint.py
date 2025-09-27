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
        from sqlalchemy import text
        result = await db.execute(text("SELECT 1 as test"))
        row = result.fetchone()
        return {"database": "connected", "test_query": row[0]}
    except Exception as e:
        return {"database": "error", "message": str(e)}

@router.post("/test-contact-service")
async def test_contact_service(db: AsyncSession = Depends(get_db)):
    """Test ContactService initialization only"""
    try:
        from groupchat.services.contacts import ContactService
        service = ContactService(db)
        return {"contact_service": "initialized", "success": True}
    except Exception as e:
        return {"contact_service": "error", "message": str(e)}

@router.post("/test-direct-contact")
async def test_direct_contact():
    """Test contact creation without database dependency"""
    try:
        from groupchat.schemas.contacts import ContactCreate
        from groupchat.db.models import Contact
        import uuid
        
        # Just test object creation, no database
        contact_data = ContactCreate(
            name="Test User",
            phone_number="+1234567890",
            bio="Test bio",
            is_available=True,
            max_queries_per_day=3,
            preferred_contact_method="sms"
        )
        
        contact = Contact(
            id=uuid.uuid4(),
            phone_number=contact_data.phone_number,
            name=contact_data.name,
            bio=contact_data.bio,
            is_available=contact_data.is_available,
        )
        
        return {
            "contact_model": "created",
            "name": contact.name,
            "phone": contact.phone_number
        }
    except Exception as e:
        return {"error": str(e)}