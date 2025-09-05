"""Database models for GroupChat system"""

import enum
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from decimal import Decimal

from sqlalchemy import (
    Column, String, Text, Float, Boolean, Integer, 
    DateTime, ForeignKey, Index, DECIMAL, JSON,
    Enum as SQLEnum, UniqueConstraint, CheckConstraint
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector

from groupchat.db.database import Base


class TimestampMixin:
    """Mixin for adding timestamp columns to models"""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )


class SoftDeleteMixin:
    """Mixin for soft delete functionality"""
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None
    )
    
    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None


class ContactStatus(enum.Enum):
    """Contact status enumeration"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"
    SUSPENDED = "suspended"


class QueryStatus(enum.Enum):
    """Query processing status"""
    PENDING = "pending"
    ROUTING = "routing"
    COLLECTING = "collecting"
    COMPILING = "compiling"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class LedgerEntryType(enum.Enum):
    """Ledger entry types for double-entry bookkeeping"""
    DEBIT = "debit"
    CREDIT = "credit"


class TransactionType(enum.Enum):
    """Types of financial transactions"""
    QUERY_PAYMENT = "query_payment"
    CONTRIBUTION_PAYOUT = "contribution_payout"
    PLATFORM_FEE = "platform_fee"
    REFERRAL_BONUS = "referral_bonus"
    REFUND = "refund"
    ADJUSTMENT = "adjustment"


class Contact(Base, TimestampMixin, SoftDeleteMixin):
    """Network members with expertise and trust metrics"""
    __tablename__ = "contacts"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    phone_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    bio: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Expertise and matching
    expertise_embedding: Mapped[Optional[List[float]]] = mapped_column(
        Vector(1536),  # OpenAI embedding dimension
        nullable=True
    )
    expertise_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Trust and reputation
    trust_score: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    response_rate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    avg_response_time_minutes: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    total_contributions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_earnings_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    # Availability
    is_available: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    max_queries_per_day: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    preferred_contact_method: Mapped[str] = mapped_column(String(20), default="sms", nullable=False)
    
    # Status and metadata
    status: Mapped[ContactStatus] = mapped_column(
        SQLEnum(ContactStatus),
        default=ContactStatus.PENDING,
        nullable=False
    )
    extra_metadata: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    
    # Relationships
    expertise_tags = relationship("ExpertiseTag", secondary="contact_expertise", back_populates="contacts")
    contributions = relationship("Contribution", back_populates="contact")
    api_credentials = relationship("APICredential", back_populates="contact")
    referrals = relationship("Contact", 
                           secondary="referrals",
                           primaryjoin="Contact.id==referrals.c.referrer_id",
                           secondaryjoin="Contact.id==referrals.c.referred_id")
    
    # Indexes
    __table_args__ = (
        Index("idx_contact_phone", "phone_number"),
        Index("idx_contact_email", "email"),
        Index("idx_contact_status", "status"),
        Index("idx_contact_trust_score", "trust_score"),
        Index("idx_contact_availability", "is_available", "status"),
    )


class ExpertiseTag(Base, TimestampMixin):
    """Skill and knowledge categorization tags"""
    __tablename__ = "expertise_tags"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Relationships
    contacts = relationship("Contact", secondary="contact_expertise", back_populates="expertise_tags")
    
    __table_args__ = (
        Index("idx_tag_name", "name"),
        Index("idx_tag_category", "category"),
    )


class ContactExpertise(Base):
    """Association table for contact-expertise many-to-many relationship"""
    __tablename__ = "contact_expertise"
    
    contact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contacts.id", ondelete="CASCADE"),
        primary_key=True
    )
    tag_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("expertise_tags.id", ondelete="CASCADE"),
        primary_key=True
    )
    confidence_score: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    
    __table_args__ = (
        Index("idx_contact_expertise_contact", "contact_id"),
        Index("idx_contact_expertise_tag", "tag_id"),
    )


class Query(Base, TimestampMixin, SoftDeleteMixin):
    """User questions and requests"""
    __tablename__ = "queries"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    user_phone: Mapped[str] = mapped_column(String(20), nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    question_embedding: Mapped[Optional[List[float]]] = mapped_column(
        Vector(1536),
        nullable=True
    )
    
    # Processing status
    status: Mapped[QueryStatus] = mapped_column(
        SQLEnum(QueryStatus),
        default=QueryStatus.PENDING,
        nullable=False
    )
    
    # Routing configuration
    max_experts: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    min_experts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    timeout_minutes: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    
    # Financial
    total_cost_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    platform_fee_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    # Metadata
    context: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Relationships
    contributions = relationship("Contribution", back_populates="query")
    compiled_answer = relationship("CompiledAnswer", back_populates="query", uselist=False)
    
    __table_args__ = (
        Index("idx_query_user", "user_phone"),
        Index("idx_query_status", "status"),
        Index("idx_query_created", "created_at"),
    )


class Contribution(Base, TimestampMixin):
    """Raw responses from experts"""
    __tablename__ = "contributions"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    query_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("queries.id", ondelete="CASCADE"),
        nullable=False
    )
    contact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contacts.id", ondelete="SET NULL"),
        nullable=True
    )
    
    # Response content
    response_text: Mapped[str] = mapped_column(Text, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    relevance_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # Timing
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    responded_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    response_time_minutes: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # Quality metrics
    was_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    quality_rating: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # Financial
    payout_amount_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    # Metadata
    extra_metadata: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    
    # Relationships
    query = relationship("Query", back_populates="contributions")
    contact = relationship("Contact", back_populates="contributions")
    citations = relationship("Citation", back_populates="contribution")
    
    __table_args__ = (
        Index("idx_contribution_query", "query_id"),
        Index("idx_contribution_contact", "contact_id"),
        Index("idx_contribution_timing", "requested_at", "responded_at"),
        UniqueConstraint("query_id", "contact_id", name="uq_query_contact"),
    )


class CompiledAnswer(Base, TimestampMixin):
    """Synthesized answers with citations"""
    __tablename__ = "compiled_answers"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    query_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("queries.id", ondelete="CASCADE"),
        unique=True,
        nullable=False
    )
    
    # Answer content
    final_answer: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    
    # Compilation metadata
    compilation_method: Mapped[str] = mapped_column(String(50), default="gpt-4", nullable=False)
    compilation_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    compilation_tokens_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    # Quality metrics
    quality_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    user_rating: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    user_feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Metadata
    extra_metadata: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    
    # Relationships
    query = relationship("Query", back_populates="compiled_answer")
    citations = relationship("Citation", back_populates="compiled_answer")
    
    __table_args__ = (
        Index("idx_compiled_query", "query_id"),
        CheckConstraint("user_rating >= 1 AND user_rating <= 5", name="check_user_rating"),
    )


class Citation(Base, TimestampMixin):
    """Mapping of claims to contributors"""
    __tablename__ = "citations"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    compiled_answer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("compiled_answers.id", ondelete="CASCADE"),
        nullable=False
    )
    contribution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contributions.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # Citation details
    claim_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    position_in_answer: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    
    # Relationships
    compiled_answer = relationship("CompiledAnswer", back_populates="citations")
    contribution = relationship("Contribution", back_populates="citations")
    
    __table_args__ = (
        Index("idx_citation_answer", "compiled_answer_id"),
        Index("idx_citation_contribution", "contribution_id"),
        Index("idx_citation_position", "position_in_answer"),
    )


class Ledger(Base, TimestampMixin):
    """Double-entry bookkeeping for micropayments"""
    __tablename__ = "ledger"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    
    # Transaction reference
    transaction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True
    )
    transaction_type: Mapped[TransactionType] = mapped_column(
        SQLEnum(TransactionType),
        nullable=False
    )
    
    # Account information
    account_type: Mapped[str] = mapped_column(String(50), nullable=False)
    account_id: Mapped[str] = mapped_column(String(100), nullable=False)
    
    # Entry details
    entry_type: Mapped[LedgerEntryType] = mapped_column(
        SQLEnum(LedgerEntryType),
        nullable=False
    )
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    
    # References
    query_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("queries.id", ondelete="SET NULL"),
        nullable=True
    )
    contact_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contacts.id", ondelete="SET NULL"),
        nullable=True
    )
    
    # Description and metadata
    description: Mapped[str] = mapped_column(Text, nullable=False)
    extra_metadata: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    
    # Running balance (calculated)
    balance_after_cents: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    __table_args__ = (
        Index("idx_ledger_transaction", "transaction_id"),
        Index("idx_ledger_account", "account_type", "account_id"),
        Index("idx_ledger_query", "query_id"),
        Index("idx_ledger_contact", "contact_id"),
        Index("idx_ledger_created", "created_at"),
        Index("idx_ledger_type", "transaction_type"),
    )


class PayoutSplit(Base, TimestampMixin):
    """Payment distribution records"""
    __tablename__ = "payout_splits"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    query_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("queries.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # Payout calculation
    total_amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    contributor_pool_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    platform_fee_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    referral_bonus_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    # Distribution details (JSONB array of recipient splits)
    distribution: Mapped[List[Dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    
    # Processing status
    is_processed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Stripe references
    stripe_transfer_ids: Mapped[List[str]] = mapped_column(JSONB, default=list, nullable=False)
    
    # Metadata
    extra_metadata: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    
    __table_args__ = (
        Index("idx_payout_query", "query_id"),
        Index("idx_payout_processed", "is_processed"),
        UniqueConstraint("query_id", name="uq_payout_query"),
    )


class APICredential(Base, TimestampMixin):
    """Encrypted third-party API keys"""
    __tablename__ = "api_credentials"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    contact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contacts.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # Service information
    service_name: Mapped[str] = mapped_column(String(100), nullable=False)
    credential_type: Mapped[str] = mapped_column(String(50), nullable=False)  # api_key, oauth_token, etc.
    
    # Encrypted storage
    encrypted_value: Mapped[bytes] = mapped_column(Text, nullable=False)  # Base64 encoded encrypted value
    encryption_method: Mapped[str] = mapped_column(String(50), default="fernet", nullable=False)
    
    # Validation
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_validated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Metadata
    extra_metadata: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    
    # Relationships
    contact = relationship("Contact", back_populates="api_credentials")
    
    __table_args__ = (
        Index("idx_credential_contact", "contact_id"),
        Index("idx_credential_service", "service_name"),
        UniqueConstraint("contact_id", "service_name", name="uq_contact_service"),
    )


class Referral(Base):
    """Referral tracking table"""
    __tablename__ = "referrals"
    
    referrer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contacts.id", ondelete="CASCADE"),
        primary_key=True
    )
    referred_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contacts.id", ondelete="CASCADE"),
        primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    
    __table_args__ = (
        Index("idx_referral_referrer", "referrer_id"),
        Index("idx_referral_referred", "referred_id"),
    )