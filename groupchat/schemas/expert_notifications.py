"""Schemas for expert notification and response management"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, validator

from groupchat.db.models import NotificationSchedule, NotificationUrgency


class ExpertNotificationPreferencesBase(BaseModel):
    """Base schema for expert notification preferences"""
    sms_enabled: bool = True
    email_enabled: bool = True
    push_enabled: bool = True
    notification_schedule: NotificationSchedule = NotificationSchedule.IMMEDIATE
    urgency_filter: NotificationUrgency = NotificationUrgency.LOW
    business_hours: Dict[str, Any] = Field(
        default_factory=lambda: {"start": "09:00", "end": "17:00", "timezone": "UTC"}
    )
    quiet_hours_enabled: bool = True
    quiet_hours_start: str = "22:00"
    quiet_hours_end: str = "08:00"
    max_notifications_per_hour: int = Field(default=5, ge=1, le=50)
    max_notifications_per_day: int = Field(default=20, ge=1, le=100)
    expertise_matching_threshold: float = Field(default=0.3, ge=0.0, le=1.0)
    auto_decline_low_match: bool = False

    @validator("quiet_hours_start", "quiet_hours_end")
    def validate_time_format(cls, v):
        """Validate time format HH:MM"""
        try:
            datetime.strptime(v, "%H:%M")
            return v
        except ValueError:
            raise ValueError("Time must be in HH:MM format")


class ExpertNotificationPreferencesCreate(ExpertNotificationPreferencesBase):
    """Schema for creating expert notification preferences"""
    contact_id: UUID


class ExpertNotificationPreferencesUpdate(BaseModel):
    """Schema for updating expert notification preferences"""
    sms_enabled: Optional[bool] = None
    email_enabled: Optional[bool] = None
    push_enabled: Optional[bool] = None
    notification_schedule: Optional[NotificationSchedule] = None
    urgency_filter: Optional[NotificationUrgency] = None
    business_hours: Optional[Dict[str, Any]] = None
    quiet_hours_enabled: Optional[bool] = None
    quiet_hours_start: Optional[str] = None
    quiet_hours_end: Optional[str] = None
    max_notifications_per_hour: Optional[int] = Field(None, ge=1, le=50)
    max_notifications_per_day: Optional[int] = Field(None, ge=1, le=100)
    expertise_matching_threshold: Optional[float] = Field(None, ge=0.0, le=1.0)
    auto_decline_low_match: Optional[bool] = None

    @validator("quiet_hours_start", "quiet_hours_end")
    def validate_time_format(cls, v):
        """Validate time format HH:MM"""
        if v is not None:
            try:
                datetime.strptime(v, "%H:%M")
                return v
            except ValueError:
                raise ValueError("Time must be in HH:MM format")


class ExpertNotificationPreferencesResponse(ExpertNotificationPreferencesBase):
    """Schema for expert notification preferences response"""
    contact_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ResponseDraftBase(BaseModel):
    """Base schema for response drafts"""
    draft_content: str
    confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    content_format: str = "plaintext"
    attachments: List[Dict[str, Any]] = Field(default_factory=list)


class ResponseDraftCreate(ResponseDraftBase):
    """Schema for creating response drafts"""
    query_id: UUID
    contact_id: UUID


class ResponseDraftUpdate(BaseModel):
    """Schema for updating response drafts"""
    draft_content: Optional[str] = None
    confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    content_format: Optional[str] = None
    attachments: Optional[List[Dict[str, Any]]] = None
    is_final: Optional[bool] = None


class ResponseDraftResponse(ResponseDraftBase):
    """Schema for response draft response"""
    id: UUID
    query_id: UUID
    contact_id: UUID
    contribution_id: Optional[UUID] = None
    auto_save_count: int
    is_final: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ResponseQualityReviewBase(BaseModel):
    """Base schema for response quality reviews"""
    quality_score: float = Field(..., ge=0.0, le=5.0)
    accuracy_score: Optional[float] = Field(None, ge=0.0, le=5.0)
    helpfulness_score: Optional[float] = Field(None, ge=0.0, le=5.0)
    clarity_score: Optional[float] = Field(None, ge=0.0, le=5.0)
    review_notes: Optional[str] = None
    recommended_improvements: Optional[str] = None
    review_weight: float = Field(default=1.0, ge=0.0, le=5.0)


class ResponseQualityReviewCreate(ResponseQualityReviewBase):
    """Schema for creating response quality reviews"""
    contribution_id: UUID
    reviewer_id: Optional[UUID] = None
    is_automated_review: bool = False


class ResponseQualityReviewResponse(ResponseQualityReviewBase):
    """Schema for response quality review response"""
    id: UUID
    contribution_id: UUID
    reviewer_id: Optional[UUID]
    is_automated_review: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ExpertAvailabilityScheduleBase(BaseModel):
    """Base schema for expert availability schedules"""
    weekly_schedule: Dict[str, Any] = Field(
        default_factory=lambda: {
            "monday": {"available": True, "start": "09:00", "end": "17:00"},
            "tuesday": {"available": True, "start": "09:00", "end": "17:00"},
            "wednesday": {"available": True, "start": "09:00", "end": "17:00"},
            "thursday": {"available": True, "start": "09:00", "end": "17:00"},
            "friday": {"available": True, "start": "09:00", "end": "17:00"},
            "saturday": {"available": False, "start": "09:00", "end": "17:00"},
            "sunday": {"available": False, "start": "09:00", "end": "17:00"}
        }
    )
    temporary_unavailable_start: Optional[datetime] = None
    temporary_unavailable_end: Optional[datetime] = None
    unavailable_reason: Optional[str] = None
    vacation_mode_enabled: bool = False
    vacation_start: Optional[datetime] = None
    vacation_end: Optional[datetime] = None
    vacation_auto_response: Optional[str] = None


class ExpertAvailabilityScheduleCreate(ExpertAvailabilityScheduleBase):
    """Schema for creating expert availability schedules"""
    contact_id: UUID


class ExpertAvailabilityScheduleUpdate(BaseModel):
    """Schema for updating expert availability schedules"""
    weekly_schedule: Optional[Dict[str, Any]] = None
    temporary_unavailable_start: Optional[datetime] = None
    temporary_unavailable_end: Optional[datetime] = None
    unavailable_reason: Optional[str] = None
    vacation_mode_enabled: Optional[bool] = None
    vacation_start: Optional[datetime] = None
    vacation_end: Optional[datetime] = None
    vacation_auto_response: Optional[str] = None


class ExpertAvailabilityScheduleResponse(ExpertAvailabilityScheduleBase):
    """Schema for expert availability schedule response"""
    id: UUID
    contact_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ExpertQueryNotification(BaseModel):
    """Schema for expert query notifications"""
    query_id: UUID
    query_text: str
    urgency: NotificationUrgency
    user_phone: str
    estimated_payout_cents: int
    expertise_match_score: float
    timeout_minutes: int
    notification_channels: List[str]
    created_at: datetime


class ExpertQueueItem(BaseModel):
    """Schema for expert queue items"""
    query_id: UUID
    question_text: str
    user_phone: str
    urgency: NotificationUrgency
    estimated_payout_cents: int
    expertise_match_score: float
    time_remaining_minutes: int
    status: str
    received_at: datetime
    response_deadline: datetime


class ExpertQueueResponse(BaseModel):
    """Schema for expert queue response"""
    items: List[ExpertQueueItem]
    total_items: int
    pending_items: int
    in_progress_items: int
    completed_today: int
    earnings_today_cents: int


class NotificationDeliveryStatus(BaseModel):
    """Schema for notification delivery status"""
    notification_id: UUID
    contact_id: UUID
    query_id: UUID
    channels_attempted: List[str]
    channels_delivered: List[str]
    channels_failed: List[str]
    delivery_attempts: int
    last_attempt_at: datetime
    next_retry_at: Optional[datetime]
    final_status: str  # delivered, failed, rate_limited, opted_out