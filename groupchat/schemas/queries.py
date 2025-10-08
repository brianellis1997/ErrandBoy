"""Pydantic schemas for query management API"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class QueryBase(BaseModel):
    question_text: str = Field(..., min_length=10, max_length=5000)
    max_experts: int = Field(default=5, ge=1, le=10)
    min_experts: int = Field(default=3, ge=1, le=5)
    timeout_minutes: int = Field(default=30, ge=5, le=120)
    context: dict[str, Any] = Field(default_factory=dict)

    @field_validator("min_experts", "max_experts")
    @classmethod
    def validate_expert_counts(cls, v: int, info: Any) -> int:
        if info.field_name == "min_experts" and "max_experts" in info.data:
            if v > info.data["max_experts"]:
                raise ValueError("min_experts cannot be greater than max_experts")
        return v


class QueryCreate(QueryBase):
    user_phone: str = Field(..., pattern=r"^\+?1?[0-9]{10,15}$")
    max_spend_cents: int = Field(..., ge=50, le=100000)  # $0.50 to $1000.00

    @field_validator("user_phone")
    @classmethod
    def validate_phone_number(cls, v: str) -> str:
        cleaned = "".join(filter(str.isdigit, v))
        if len(cleaned) < 10 or len(cleaned) > 15:
            raise ValueError("Phone number must be 10-15 digits")
        return v


class QueryUpdate(BaseModel):
    max_experts: int | None = Field(None, ge=3, le=10)
    min_experts: int | None = Field(None, ge=1, le=5)
    timeout_minutes: int | None = Field(None, ge=5, le=120)
    context: dict[str, Any] | None = None


class QueryResponse(QueryBase):
    id: UUID
    user_phone: str
    status: str
    total_cost_cents: int
    platform_fee_cents: int
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None

    model_config = {"from_attributes": True}


class QueryListResponse(BaseModel):
    queries: list[QueryResponse]
    total: int
    skip: int
    limit: int


class ContributionCreate(BaseModel):
    response_text: str = Field(..., min_length=50, max_length=1000)
    confidence_score: float = Field(..., ge=0.1, le=1.0)
    source_links: str | None = Field(None, max_length=500)
    expert_name: str | None = Field(None, max_length=100)

    @field_validator("confidence_score")
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        """Convert 1-10 scale to 0.1-1.0 if needed"""
        if v > 1.0:
            v = v / 10.0
        return max(0.1, min(1.0, v))


class ContributionResponse(BaseModel):
    id: UUID
    contact_id: UUID | None
    response_text: str
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    relevance_score: float | None = Field(None, ge=0.0, le=1.0)
    requested_at: datetime
    responded_at: datetime | None
    response_time_minutes: float | None
    was_used: bool
    quality_rating: float | None = Field(None, ge=0.0, le=5.0)
    payout_amount_cents: int
    extra_metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ContributionListResponse(BaseModel):
    contributions: list[ContributionResponse]
    total: int


class CitationResponse(BaseModel):
    id: UUID
    contribution_id: UUID
    claim_text: str
    source_excerpt: str
    position_in_answer: int
    confidence: float = Field(..., ge=0.0, le=1.0)
    created_at: datetime

    model_config = {"from_attributes": True}


class CompiledAnswerResponse(BaseModel):
    id: UUID
    query_id: UUID
    final_answer: str
    summary: str | None
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    compilation_method: str
    compilation_tokens_used: int
    quality_score: float | None = Field(None, ge=0.0, le=1.0)
    user_rating: int | None = Field(None, ge=1, le=5)
    user_feedback: str | None
    citations: list[CitationResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class QueryDetailResponse(QueryResponse):
    contributions: list[ContributionResponse] = Field(default_factory=list)
    compiled_answer: CompiledAnswerResponse | None = None


class AcceptAnswerRequest(BaseModel):
    user_rating: int | None = Field(None, ge=1, le=5)
    user_feedback: str | None = Field(None, max_length=1000)


class AcceptAnswerResponse(BaseModel):
    success: bool
    transaction_id: UUID
    total_payout_cents: int
    platform_fee_cents: int
    message: str


class QueryStatusResponse(BaseModel):
    id: UUID
    status: str
    progress: dict[str, Any]
    estimated_completion: datetime | None
    contributors_matched: int
    contributions_received: int
    last_updated: datetime


class ErrorResponse(BaseModel):
    detail: str
    error_code: str | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
