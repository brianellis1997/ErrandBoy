"""API endpoints for expert notification preferences and response management"""

import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from groupchat.db.database import get_db
from groupchat.db.models import (
    Contact,
    ContactStatus,
    ExpertAvailabilitySchedule,
    ExpertNotificationPreferences,
    Query as QueryModel,
    QueryStatus,
    ResponseDraft,
    ResponseQualityReview,
)
from groupchat.schemas.expert_notifications import (
    ExpertAvailabilityScheduleCreate,
    ExpertAvailabilityScheduleResponse,
    ExpertAvailabilityScheduleUpdate,
    ExpertNotificationPreferencesCreate,
    ExpertNotificationPreferencesResponse,
    ExpertNotificationPreferencesUpdate,
    ExpertQueueResponse,
    ExpertQueueItem,
    ResponseDraftCreate,
    ResponseDraftResponse,
    ResponseDraftUpdate,
    ResponseQualityReviewCreate,
    ResponseQualityReviewResponse,
)
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/expert", tags=["Expert Preferences"])


async def get_expert_contact(contact_id: UUID, db: AsyncSession) -> Contact:
    """Get and validate expert contact"""
    result = await db.execute(
        select(Contact).where(
            and_(
                Contact.id == contact_id,
                Contact.status == ContactStatus.ACTIVE
            )
        )
    )
    contact = result.scalar_one_or_none()
    
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Expert contact not found"
        )
    
    return contact


# Notification Preferences Endpoints

@router.get("/{contact_id}/preferences", response_model=ExpertNotificationPreferencesResponse)
async def get_expert_preferences(
    contact_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Get expert notification preferences"""
    await get_expert_contact(contact_id, db)
    
    result = await db.execute(
        select(ExpertNotificationPreferences).where(
            ExpertNotificationPreferences.contact_id == contact_id
        )
    )
    preferences = result.scalar_one_or_none()
    
    if not preferences:
        # Create default preferences if none exist
        preferences = ExpertNotificationPreferences(contact_id=contact_id)
        db.add(preferences)
        await db.commit()
        await db.refresh(preferences)
    
    return preferences


@router.post("/{contact_id}/preferences", response_model=ExpertNotificationPreferencesResponse)
async def create_expert_preferences(
    contact_id: UUID,
    preferences_data: ExpertNotificationPreferencesCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create or update expert notification preferences"""
    await get_expert_contact(contact_id, db)
    
    # Check if preferences already exist
    result = await db.execute(
        select(ExpertNotificationPreferences).where(
            ExpertNotificationPreferences.contact_id == contact_id
        )
    )
    existing_preferences = result.scalar_one_or_none()
    
    if existing_preferences:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Preferences already exist. Use PUT to update."
        )
    
    preferences = ExpertNotificationPreferences(
        contact_id=contact_id,
        **preferences_data.dict(exclude={"contact_id"})
    )
    
    db.add(preferences)
    await db.commit()
    await db.refresh(preferences)
    
    logger.info(f"Created notification preferences for expert {contact_id}")
    return preferences


@router.put("/{contact_id}/preferences", response_model=ExpertNotificationPreferencesResponse)
async def update_expert_preferences(
    contact_id: UUID,
    preferences_update: ExpertNotificationPreferencesUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update expert notification preferences"""
    await get_expert_contact(contact_id, db)
    
    result = await db.execute(
        select(ExpertNotificationPreferences).where(
            ExpertNotificationPreferences.contact_id == contact_id
        )
    )
    preferences = result.scalar_one_or_none()
    
    if not preferences:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Preferences not found. Use POST to create."
        )
    
    # Update only provided fields
    update_data = preferences_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(preferences, field, value)
    
    await db.commit()
    await db.refresh(preferences)
    
    logger.info(f"Updated notification preferences for expert {contact_id}")
    return preferences


# Availability Schedule Endpoints

@router.get("/{contact_id}/availability", response_model=ExpertAvailabilityScheduleResponse)
async def get_expert_availability(
    contact_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Get expert availability schedule"""
    await get_expert_contact(contact_id, db)
    
    result = await db.execute(
        select(ExpertAvailabilitySchedule).where(
            ExpertAvailabilitySchedule.contact_id == contact_id
        )
    )
    schedule = result.scalar_one_or_none()
    
    if not schedule:
        # Create default schedule if none exists
        schedule = ExpertAvailabilitySchedule(
            contact_id=contact_id,
            weekly_schedule={
                "monday": {"available": True, "start": "09:00", "end": "17:00"},
                "tuesday": {"available": True, "start": "09:00", "end": "17:00"},
                "wednesday": {"available": True, "start": "09:00", "end": "17:00"},
                "thursday": {"available": True, "start": "09:00", "end": "17:00"},
                "friday": {"available": True, "start": "09:00", "end": "17:00"},
                "saturday": {"available": False, "start": "09:00", "end": "17:00"},
                "sunday": {"available": False, "start": "09:00", "end": "17:00"}
            }
        )
        db.add(schedule)
        await db.commit()
        await db.refresh(schedule)
    
    return schedule


@router.put("/{contact_id}/availability", response_model=ExpertAvailabilityScheduleResponse)
async def update_expert_availability(
    contact_id: UUID,
    availability_update: ExpertAvailabilityScheduleUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update expert availability schedule"""
    await get_expert_contact(contact_id, db)
    
    result = await db.execute(
        select(ExpertAvailabilitySchedule).where(
            ExpertAvailabilitySchedule.contact_id == contact_id
        )
    )
    schedule = result.scalar_one_or_none()
    
    if not schedule:
        # Create with provided data
        schedule_data = availability_update.dict(exclude_unset=True)
        schedule = ExpertAvailabilitySchedule(
            contact_id=contact_id,
            **schedule_data
        )
        db.add(schedule)
    else:
        # Update existing schedule
        update_data = availability_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(schedule, field, value)
    
    await db.commit()
    await db.refresh(schedule)
    
    logger.info(f"Updated availability schedule for expert {contact_id}")
    return schedule


@router.post("/{contact_id}/availability/toggle")
async def toggle_expert_availability(
    contact_id: UUID,
    available: bool,
    reason: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Toggle expert availability (quick on/off)"""
    contact = await get_expert_contact(contact_id, db)
    
    # Update contact availability status
    contact.is_available = available
    
    # Update availability schedule if exists
    result = await db.execute(
        select(ExpertAvailabilitySchedule).where(
            ExpertAvailabilitySchedule.contact_id == contact_id
        )
    )
    schedule = result.scalar_one_or_none()
    
    if schedule:
        if not available:
            from datetime import datetime
            schedule.temporary_unavailable_start = datetime.utcnow()
            schedule.temporary_unavailable_end = None  # Indefinite
            schedule.unavailable_reason = reason or "Manually set unavailable"
        else:
            schedule.temporary_unavailable_start = None
            schedule.temporary_unavailable_end = None
            schedule.unavailable_reason = None
    
    await db.commit()
    
    status_msg = "available" if available else "unavailable"
    logger.info(f"Expert {contact_id} set to {status_msg}")
    
    return {
        "contact_id": contact_id,
        "available": available,
        "reason": reason,
        "message": f"Expert availability updated to {status_msg}"
    }


# Expert Queue Management

@router.get("/{contact_id}/queue", response_model=ExpertQueueResponse)
async def get_expert_queue(
    contact_id: UUID,
    status_filter: Optional[str] = Query(None, description="Filter by query status"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """Get expert's query queue with filtering and pagination"""
    await get_expert_contact(contact_id, db)
    
    # Build query to get contributions for this expert
    query = (
        select(QueryModel)
        .join(QueryModel.contributions)
        .where(QueryModel.contributions.any(contact_id=contact_id))
    )
    
    if status_filter:
        try:
            query_status = QueryStatus(status_filter)
            query = query.where(QueryModel.status == query_status)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status filter: {status_filter}"
            )
    
    # Get paginated results
    query = query.offset(offset).limit(limit)
    result = await db.execute(query.options(selectinload(QueryModel.contributions)))
    queries = result.scalars().all()
    
    # Convert to queue items
    from datetime import datetime, timedelta
    queue_items = []
    
    for query_obj in queries:
        # Find this expert's contribution
        expert_contribution = next(
            (c for c in query_obj.contributions if c.contact_id == contact_id),
            None
        )
        
        if expert_contribution:
            # Handle timezone-aware datetime comparison
            from datetime import timezone
            now_utc = datetime.now(timezone.utc)
            requested_at = expert_contribution.requested_at
            
            # Ensure both datetimes are timezone-aware
            if requested_at.tzinfo is None:
                requested_at = requested_at.replace(tzinfo=timezone.utc)
            
            time_remaining = max(0, query_obj.timeout_minutes - 
                               (now_utc - requested_at).total_seconds() / 60)
            
            queue_items.append(ExpertQueueItem(
                query_id=query_obj.id,
                question_text=query_obj.question_text,
                user_phone=query_obj.user_phone,
                urgency="normal",  # TODO: Add urgency to Query model
                estimated_payout_cents=query_obj.total_cost_cents // max(1, len(query_obj.contributions)),
                expertise_match_score=0.8,  # TODO: Calculate based on embedding similarity
                time_remaining_minutes=int(time_remaining),
                status=query_obj.status.value,
                received_at=expert_contribution.requested_at,
                response_deadline=expert_contribution.requested_at + timedelta(minutes=query_obj.timeout_minutes)
            ))
    
    # Calculate summary statistics
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    
    pending_count = sum(1 for item in queue_items if item.status in ["pending", "routing"])
    in_progress_count = sum(1 for item in queue_items if item.status == "collecting")
    
    return ExpertQueueResponse(
        items=queue_items,
        total_items=len(queue_items),
        pending_items=pending_count,
        in_progress_items=in_progress_count,
        completed_today=0,  # TODO: Calculate from contributions
        earnings_today_cents=0  # TODO: Calculate from payouts
    )


# Response Draft Management

@router.get("/{contact_id}/drafts", response_model=List[ResponseDraftResponse])
async def get_expert_drafts(
    contact_id: UUID,
    query_id: Optional[UUID] = Query(None, description="Filter by specific query"),
    db: AsyncSession = Depends(get_db)
):
    """Get expert's response drafts"""
    await get_expert_contact(contact_id, db)
    
    query = select(ResponseDraft).where(ResponseDraft.contact_id == contact_id)
    
    if query_id:
        query = query.where(ResponseDraft.query_id == query_id)
    
    query = query.order_by(ResponseDraft.updated_at.desc())
    result = await db.execute(query)
    drafts = result.scalars().all()
    
    return drafts


@router.post("/{contact_id}/drafts", response_model=ResponseDraftResponse)
async def create_response_draft(
    contact_id: UUID,
    draft_data: ResponseDraftCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new response draft"""
    await get_expert_contact(contact_id, db)
    
    # Validate the query exists and expert has access
    result = await db.execute(
        select(QueryModel).where(QueryModel.id == draft_data.query_id)
    )
    query_obj = result.scalar_one_or_none()
    
    if query_obj:
        # Check if expert has a contribution for this query
        from groupchat.db.models import Contribution
        contrib_result = await db.execute(
            select(Contribution).where(
                and_(
                    Contribution.query_id == draft_data.query_id,
                    Contribution.contact_id == contact_id
                )
            )
        )
        has_contribution = contrib_result.first() is not None
    
    if not query_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Query not found"
        )
    
    # For demo purposes, allow drafts for any query
    # In production, you might want to enforce expert access
    # if not has_contribution:
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN,
    #         detail="Expert not invited to this query"
    #     )
    
    # Check if draft already exists
    result = await db.execute(
        select(ResponseDraft).where(
            and_(
                ResponseDraft.query_id == draft_data.query_id,
                ResponseDraft.contact_id == contact_id
            )
        )
    )
    existing_draft = result.scalar_one_or_none()
    
    if existing_draft:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Draft already exists for this query. Use PUT to update."
        )
    
    draft = ResponseDraft(
        query_id=draft_data.query_id,
        contact_id=contact_id,
        draft_content=draft_data.draft_content,
        confidence_score=draft_data.confidence_score,
        content_format=draft_data.content_format,
        attachments=draft_data.attachments
    )
    
    db.add(draft)
    await db.commit()
    await db.refresh(draft)
    
    logger.info(f"Created draft for query {draft_data.query_id} by expert {contact_id}")
    return draft


@router.put("/{contact_id}/drafts/{draft_id}", response_model=ResponseDraftResponse)
async def update_response_draft(
    contact_id: UUID,
    draft_id: UUID,
    draft_update: ResponseDraftUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update an existing response draft (auto-save)"""
    await get_expert_contact(contact_id, db)
    
    result = await db.execute(
        select(ResponseDraft).where(
            and_(
                ResponseDraft.id == draft_id,
                ResponseDraft.contact_id == contact_id
            )
        )
    )
    draft = result.scalar_one_or_none()
    
    if not draft:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Draft not found"
        )
    
    # Update draft with provided fields
    update_data = draft_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(draft, field, value)
    
    # Increment auto-save counter
    draft.auto_save_count += 1
    
    await db.commit()
    await db.refresh(draft)
    
    return draft


@router.delete("/{contact_id}/drafts/{draft_id}")
async def delete_response_draft(
    contact_id: UUID,
    draft_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Delete a response draft"""
    await get_expert_contact(contact_id, db)
    
    result = await db.execute(
        select(ResponseDraft).where(
            and_(
                ResponseDraft.id == draft_id,
                ResponseDraft.contact_id == contact_id
            )
        )
    )
    draft = result.scalar_one_or_none()
    
    if not draft:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Draft not found"
        )
    
    await db.delete(draft)
    await db.commit()
    
    logger.info(f"Deleted draft {draft_id} for expert {contact_id}")
    return {"message": "Draft deleted successfully"}


# New endpoints for expert authentication and question management

class ExpertAuthRequest(BaseModel):
    phone_number: str

class ExpertAuthResponse(BaseModel):
    expert: dict
    success: bool = True

class ExpertQuestionResponse(BaseModel):
    id: str
    question_text: str
    user_phone: str
    created_at: str
    status: str
    max_spend_cents: int
    response: Optional[str] = None

class ExpertResponseRequest(BaseModel):
    question_id: str
    expert_id: str
    response: str


@router.post("/authenticate", response_model=ExpertAuthResponse)
async def authenticate_expert(
    auth_request: ExpertAuthRequest,
    db: AsyncSession = Depends(get_db)
):
    """Authenticate expert by phone number and return profile"""
    try:
        # Find expert by phone number
        result = await db.execute(
            select(Contact).where(
                and_(
                    Contact.phone_number == auth_request.phone_number,
                    Contact.status.in_([ContactStatus.ACTIVE, ContactStatus.PENDING])
                )
            )
        )
        expert = result.scalar_one_or_none()
        
        if not expert:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Expert profile not found. Please check your phone number or create a profile first."
            )
        
        # Return expert data
        expert_data = {
            "id": str(expert.id),
            "name": expert.name,
            "phone_number": expert.phone_number,
            "email": expert.email,
            "bio": expert.bio,
            "trust_score": expert.trust_score,
            "response_rate": expert.response_rate,
            "total_responses": expert.total_contributions
        }
        
        logger.info(f"Expert authenticated: {expert.name} ({expert.phone_number})")
        return ExpertAuthResponse(expert=expert_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Expert authentication error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication failed"
        )


@router.get("/questions/{expert_id}")
async def get_expert_questions(
    expert_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Get questions that have been routed to this expert"""
    try:
        # Get contributions for this expert (questions they've been contacted about)
        from groupchat.db.models import Contribution
        
        result = await db.execute(
            select(Contribution, QueryModel)
            .join(QueryModel, Contribution.query_id == QueryModel.id)
            .where(Contribution.contact_id == expert_id)
            .order_by(Contribution.requested_at.desc())
        )
        
        contributions = result.all()
        
        questions = []
        for contribution, query in contributions:
            question_data = {
                "id": str(query.id),
                "question_text": query.question_text,
                "user_phone": query.user_phone,
                "created_at": query.created_at.isoformat(),
                "status": "answered" if contribution.response_text and contribution.response_text != "PASS" else "pending",
                "max_spend_cents": query.total_cost_cents,
                "response": contribution.response_text if contribution.response_text and contribution.response_text != "PASS" else None
            }
            questions.append(question_data)
        
        logger.info(f"Retrieved {len(questions)} questions for expert {expert_id}")
        return {"questions": questions, "success": True}
        
    except Exception as e:
        logger.error(f"Error retrieving questions for expert {expert_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve questions"
        )


@router.post("/respond")
async def submit_expert_response(
    response_request: ExpertResponseRequest,
    db: AsyncSession = Depends(get_db)
):
    """Submit expert response to a question"""
    try:
        from groupchat.db.models import Contribution
        from datetime import datetime
        
        # Find the contribution record
        result = await db.execute(
            select(Contribution).where(
                and_(
                    Contribution.query_id == UUID(response_request.question_id),
                    Contribution.contact_id == UUID(response_request.expert_id)
                )
            )
        )
        contribution = result.scalar_one_or_none()
        
        if not contribution:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Question not found or not assigned to this expert"
            )
        
        # Update the contribution with the response
        contribution.response_text = response_request.response
        contribution.responded_at = datetime.utcnow()
        if contribution.requested_at:
            contribution.response_time_minutes = (
                datetime.utcnow() - contribution.requested_at
            ).total_seconds() / 60
        
        await db.commit()
        
        logger.info(f"Expert {response_request.expert_id} responded to question {response_request.question_id}")
        return {"success": True, "message": "Response submitted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting expert response: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit response"
        )