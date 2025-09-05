"""Pydantic schemas for contact management API"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


class ExpertiseTagBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    category: str | None = Field(None, max_length=100)
    description: str | None = None


class ExpertiseTagCreate(ExpertiseTagBase):
    pass


class ExpertiseTagResponse(ExpertiseTagBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ContactExpertiseResponse(BaseModel):
    tag: ExpertiseTagResponse
    confidence_score: float = Field(..., ge=0.0, le=1.0)

    model_config = {"from_attributes": True}


class ContactBase(BaseModel):
    phone_number: str = Field(..., pattern=r"^\+?1?[0-9]{10,15}$")
    email: EmailStr | None = None
    name: str = Field(..., min_length=1, max_length=255)
    bio: str | None = None
    is_available: bool = True
    max_queries_per_day: int = Field(default=10, ge=1, le=100)
    preferred_contact_method: str = Field(
        default="sms", pattern=r"^(sms|email|whatsapp)$"
    )
    extra_metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("phone_number")
    @classmethod
    def validate_phone_number(cls, v: str) -> str:
        cleaned = "".join(filter(str.isdigit, v))
        if len(cleaned) < 10 or len(cleaned) > 15:
            raise ValueError("Phone number must be 10-15 digits")
        return v


class ContactCreate(ContactBase):
    expertise_tags: list[str] = Field(default_factory=list)


class ContactUpdate(BaseModel):
    email: EmailStr | None = None
    name: str | None = Field(None, min_length=1, max_length=255)
    bio: str | None = None
    is_available: bool | None = None
    max_queries_per_day: int | None = Field(None, ge=1, le=100)
    preferred_contact_method: str | None = Field(
        None, pattern=r"^(sms|email|whatsapp)$"
    )
    extra_metadata: dict[str, Any] | None = None


class ContactResponse(ContactBase):
    id: UUID
    expertise_summary: str | None
    trust_score: float = Field(..., ge=0.0, le=1.0)
    response_rate: float = Field(..., ge=0.0, le=1.0)
    avg_response_time_minutes: float | None
    total_contributions: int
    total_earnings_cents: int
    status: str
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None
    expertise_tags: list[ContactExpertiseResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class ContactListResponse(BaseModel):
    contacts: list[ContactResponse]
    total: int
    skip: int
    limit: int


class ContactSearchRequest(BaseModel):
    query: str | None = None
    expertise_tags: list[str] = Field(default_factory=list)
    min_trust_score: float | None = Field(None, ge=0.0, le=1.0)
    available_only: bool = True
    max_response_time_minutes: int | None = Field(None, ge=1)
    limit: int = Field(default=20, ge=1, le=100)
    skip: int = Field(default=0, ge=0)


class AddExpertiseRequest(BaseModel):
    expertise_tags: list[str] = Field(..., min_length=1, max_length=20)
    confidence_scores: list[float] | None = None

    @field_validator("confidence_scores")
    @classmethod
    def validate_confidence_scores(
        cls, v: list[float] | None, info: Any
    ) -> list[float] | None:
        if v is not None:
            expertise_tags = info.data.get("expertise_tags", [])
            if len(v) != len(expertise_tags):
                raise ValueError(
                    "confidence_scores length must match expertise_tags length"
                )
            if not all(0.0 <= score <= 1.0 for score in v):
                raise ValueError("All confidence scores must be between 0.0 and 1.0")
        return v


class ErrorResponse(BaseModel):
    detail: str
    error_code: str | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
