"""Simple test endpoint for debugging"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from groupchat.db.database import get_db
from groupchat.services.contacts import ContactService
from groupchat.schemas.contacts import ContactCreate

router = APIRouter()

@router.post("/test-create-contact")
async def test_create_contact(db: AsyncSession = Depends(get_db)):
    """Simple test contact creation"""
    try:
        contact_service = ContactService(db)
        
        contact_data = ContactCreate(
            name="Test User",
            phone_number="+1234567890",
            bio="Test bio",
            is_available=True,
            max_queries_per_day=3,
            preferred_contact_method="sms"
        )
        
        contact = await contact_service.create_contact(contact_data)
        await db.commit()
        
        return {
            "success": True,
            "contact_id": str(contact.id),
            "name": contact.name
        }
        
    except Exception as e:
        await db.rollback()
        return {"error": str(e)}