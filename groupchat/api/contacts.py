"""Contact management API endpoints"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from groupchat.db.database import get_db
from groupchat.schemas.contacts import (
    AddExpertiseRequest,
    ContactCreate,
    ContactListResponse,
    ContactResponse,
    ContactSearchRequest,
    ContactUpdate,
)
from groupchat.schemas.queries import QueryResponse
from groupchat.services.contacts import ContactService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/", response_model=ContactListResponse)
async def list_contacts(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    include_deleted: bool = Query(False),
    db: AsyncSession = Depends(get_db),
) -> ContactListResponse:
    """List all contacts with pagination"""
    try:
        contact_service = ContactService(db)
        contacts, total = await contact_service.list_contacts(
            skip, limit, include_deleted
        )

        return ContactListResponse(
            contacts=[ContactResponse.model_validate(contact) for contact in contacts],
            total=total,
            skip=skip,
            limit=limit,
        )
    except Exception as e:
        logger.error(f"Error listing contacts: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve contacts",
        )


@router.post("/", response_model=ContactResponse, status_code=status.HTTP_201_CREATED)
async def create_contact(
    contact_data: ContactCreate,
    db: AsyncSession = Depends(get_db),
) -> ContactResponse:
    """Create a new contact"""
    try:
        contact_service = ContactService(db)
        contact = await contact_service.create_contact(contact_data)
        await db.commit()

        return ContactResponse.model_validate(contact)
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        await db.rollback()
        logger.error(f"Error creating contact: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create contact",
        )


@router.get("/search", response_model=ContactListResponse)
async def search_contacts(
    query: str | None = Query(None),
    expertise_tags: list[str] = Query([]),
    min_trust_score: float | None = Query(None, ge=0.0, le=1.0),
    available_only: bool = Query(True),
    max_response_time_minutes: int | None = Query(None, ge=1),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> ContactListResponse:
    """Search contacts by expertise and other criteria"""
    try:
        contact_service = ContactService(db)
        search_request = ContactSearchRequest(
            query=query,
            expertise_tags=expertise_tags,
            min_trust_score=min_trust_score,
            available_only=available_only,
            max_response_time_minutes=max_response_time_minutes,
            skip=skip,
            limit=limit,
        )

        contacts, total = await contact_service.search_contacts(search_request)

        return ContactListResponse(
            contacts=[ContactResponse.model_validate(contact) for contact in contacts],
            total=total,
            skip=skip,
            limit=limit,
        )
    except Exception as e:
        logger.error(f"Error searching contacts: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to search contacts",
        )


@router.get("/{contact_id}", response_model=ContactResponse)
async def get_contact(
    contact_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> ContactResponse:
    """Get a specific contact by ID"""
    try:
        contact_service = ContactService(db)
        contact = await contact_service.get_contact(contact_id)

        if not contact:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found"
            )

        return ContactResponse.model_validate(contact)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving contact {contact_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve contact",
        )


@router.put("/{contact_id}", response_model=ContactResponse)
async def update_contact(
    contact_id: UUID,
    update_data: ContactUpdate,
    db: AsyncSession = Depends(get_db),
) -> ContactResponse:
    """Update a contact"""
    try:
        contact_service = ContactService(db)
        contact = await contact_service.update_contact(contact_id, update_data)

        if not contact:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found"
            )

        await db.commit()
        return ContactResponse.model_validate(contact)
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error updating contact {contact_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update contact",
        )


@router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_contact(
    contact_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Soft delete a contact"""
    try:
        contact_service = ContactService(db)
        deleted = await contact_service.delete_contact(contact_id)

        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found"
            )

        await db.commit()
        return None
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error deleting contact {contact_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete contact",
        )


@router.post("/{contact_id}/expertise", response_model=ContactResponse)
async def add_expertise_to_contact(
    contact_id: UUID,
    expertise_request: AddExpertiseRequest,
    db: AsyncSession = Depends(get_db),
) -> ContactResponse:
    """Add expertise tags to a contact"""
    try:
        contact_service = ContactService(db)
        contact = await contact_service.add_expertise_to_contact(
            contact_id, expertise_request
        )

        await db.commit()
        return ContactResponse.model_validate(contact)
    except ValueError as e:
        await db.rollback()
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
                if "not found" in str(e).lower()
                else status.HTTP_400_BAD_REQUEST
            ),
            detail=str(e),
        )
    except Exception as e:
        await db.rollback()
        logger.error(f"Error adding expertise to contact {contact_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add expertise tags",
        )


@router.get("/{contact_id}/pending-questions")
async def get_pending_questions(
    contact_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get questions waiting for this expert to answer"""
    try:
        from sqlalchemy import select
        from groupchat.db.models import Contribution, Query, QueryStatus
        
        # Get contribution requests for this expert that are pending response
        # Include COMPILING status so experts can still respond even if synthesis has started
        stmt = (
            select(Query, Contribution)
            .join(Contribution, Query.id == Contribution.query_id)
            .where(Contribution.contact_id == contact_id)
            .where(Contribution.responded_at.is_(None))
            .where(Query.status.in_([QueryStatus.COLLECTING, QueryStatus.COMPILING]))
            .order_by(Query.created_at.desc())
        )
        
        result = await db.execute(stmt)
        pending_items = result.all()
        
        questions = []
        for query, contribution in pending_items:
            questions.append({
                "query_id": str(query.id),
                "contribution_id": str(contribution.id),
                "question_text": query.question_text,
                "user_phone": query.user_phone,
                "max_spend_cents": query.total_cost_cents,
                "created_at": query.created_at.isoformat(),
                "requested_at": contribution.requested_at.isoformat() if contribution.requested_at else None,
                "timeout_minutes": query.timeout_minutes
            })
        
        return {
            "contact_id": str(contact_id),
            "pending_questions": questions,
            "total": len(questions)
        }
        
    except Exception as e:
        logger.error(f"Error getting pending questions for contact {contact_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve pending questions"
        )
