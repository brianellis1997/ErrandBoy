"""Schemas for expert matching system"""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from groupchat.schemas.contacts import ContactResponse


class MatchingRequest(BaseModel):
    """Request for expert matching"""
    query_id: UUID
    limit: int = Field(default=10, ge=1, le=50)
    location_boost: bool = Field(default=False)
    exclude_recent: bool = Field(default=True)
    wave_size: int = Field(default=3, ge=1, le=10)


class ExpertMatchScores(BaseModel):
    """Detailed scoring breakdown for an expert match"""
    embedding_similarity: float = Field(ge=0.0, le=1.0)
    tag_overlap: float = Field(ge=0.0, le=1.0)
    trust_score: float = Field(ge=0.0, le=1.0)
    availability_boost: float = Field(ge=0.0, le=1.0)
    responsiveness_rate: float = Field(ge=0.0, le=1.0)
    geographic_boost: float = Field(default=0.0, ge=0.0, le=1.0)
    final_score: float = Field(ge=0.0, le=1.0)


class ExpertMatch(BaseModel):
    """Expert match result with scoring details"""
    contact: ContactResponse
    scores: ExpertMatchScores
    match_reasons: list[str] = Field(default_factory=list)
    distance_km: float | None = Field(default=None)
    timezone_offset: int | None = Field(default=None)
    availability_status: str
    recent_query_count: int = Field(default=0)
    wave_group: int = Field(default=1)


class MatchingResponse(BaseModel):
    """Response containing matched experts"""
    query_id: UUID
    matches: list[ExpertMatch]
    total_candidates: int
    search_time_ms: float
    matching_strategy: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class MatchingStats(BaseModel):
    """Statistics about the matching process"""
    total_experts: int
    available_experts: int
    candidates_after_filters: int
    final_matches: int
    avg_score: float
    processing_time_ms: float
    geographic_matches: int = Field(default=0)
    timezone_compatible: int = Field(default=0)