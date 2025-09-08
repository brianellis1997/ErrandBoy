"""Database models for GroupChat system"""

import enum
import uuid
from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

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
    deleted_at: Mapped[datetime | None] = mapped_column(
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
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Expertise and matching
    expertise_embedding: Mapped[list[float] | None] = mapped_column(
        Vector(1536),  # OpenAI embedding dimension
        nullable=True
    )
    expertise_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Trust and reputation
    trust_score: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    response_rate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    avg_response_time_minutes: Mapped[float | None] = mapped_column(Float, nullable=True)
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
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    # Relationships
    expertise_tags = relationship("ExpertiseTag", secondary="contact_expertise", back_populates="contacts")
    contributions = relationship("Contribution", back_populates="contact")
    api_credentials = relationship("APICredential", back_populates="contact")
    stripe_account = relationship("StripeConnectedAccount", back_populates="contact", uselist=False)
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
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

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
    question_embedding: Mapped[list[float] | None] = mapped_column(
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
    context: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

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
    relevance_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Timing
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    response_time_minutes: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Quality metrics
    was_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    quality_rating: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Financial
    payout_amount_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Metadata
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

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
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # Compilation metadata
    compilation_method: Mapped[str] = mapped_column(String(50), default="gpt-4", nullable=False)
    compilation_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    compilation_tokens_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Quality metrics
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    user_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    user_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Metadata
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

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
    query_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("queries.id", ondelete="SET NULL"),
        nullable=True
    )
    contact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contacts.id", ondelete="SET NULL"),
        nullable=True
    )

    # Description and metadata
    description: Mapped[str] = mapped_column(Text, nullable=False)
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    # Running balance (calculated)
    balance_after_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)

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
    distribution: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)

    # Processing status
    is_processed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Stripe references
    stripe_transfer_ids: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)

    # Metadata
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

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
    last_validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Metadata
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

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


class PaymentAccountStatus(enum.Enum):
    """Payment account status enumeration"""
    PENDING = "pending"
    CONNECTED = "connected" 
    EXPIRED = "expired"
    ERROR = "error"


class PaymentMethodType(enum.Enum):
    """Payment method types"""
    BANK_ACCOUNT = "bank_account"
    DEBIT_CARD = "debit_card"
    CREDIT_CARD = "credit_card"


class PaymentIntentStatus(enum.Enum):
    """Payment intent status"""
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class UserPaymentAccount(Base, TimestampMixin, SoftDeleteMixin):
    """User bank accounts and payment methods linked via Plaid"""
    __tablename__ = "user_payment_accounts"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    
    # User identification (using phone as in existing system)
    user_phone: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    
    # Plaid integration
    plaid_access_token: Mapped[str] = mapped_column(String(255), nullable=False)
    plaid_item_id: Mapped[str] = mapped_column(String(255), nullable=False)
    plaid_account_id: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Account details
    account_name: Mapped[str] = mapped_column(String(255), nullable=False)
    account_type: Mapped[str] = mapped_column(String(50), nullable=False)  # checking, savings, etc.
    account_subtype: Mapped[str | None] = mapped_column(String(50), nullable=True)
    account_mask: Mapped[str] = mapped_column(String(10), nullable=False)  # Last 4 digits
    
    # Institution information
    institution_name: Mapped[str] = mapped_column(String(255), nullable=False)
    institution_id: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Status and verification
    status: Mapped[PaymentAccountStatus] = mapped_column(
        SQLEnum(PaymentAccountStatus),
        default=PaymentAccountStatus.PENDING,
        nullable=False
    )
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Payment capabilities
    can_deposit: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    can_withdraw: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # Metadata and configuration
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    
    __table_args__ = (
        Index("idx_payment_account_user", "user_phone"),
        Index("idx_payment_account_plaid_item", "plaid_item_id"),
        Index("idx_payment_account_status", "status"),
        UniqueConstraint("plaid_account_id", name="uq_plaid_account"),
    )


class StripeConnectedAccount(Base, TimestampMixin):
    """Expert Stripe Connect accounts for receiving payouts"""
    __tablename__ = "stripe_connected_accounts"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    
    contact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contacts.id", ondelete="CASCADE"),
        nullable=False,
        unique=True
    )
    
    # Stripe Connect integration
    stripe_account_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    stripe_account_type: Mapped[str] = mapped_column(String(50), default="express", nullable=False)
    
    # Account status and capabilities
    charges_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    payouts_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    details_submitted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # Onboarding
    onboarding_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    onboarding_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    onboarding_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Requirements and restrictions
    requirements_currently_due: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    requirements_eventually_due: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    requirements_disabled_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    # Metadata
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    
    # Relationships
    contact = relationship("Contact", back_populates="stripe_account")
    
    __table_args__ = (
        Index("idx_stripe_account_contact", "contact_id"),
        Index("idx_stripe_account_stripe_id", "stripe_account_id"),
        Index("idx_stripe_account_enabled", "payouts_enabled"),
    )


class PaymentIntent(Base, TimestampMixin):
    """Track deposit and withdrawal intents"""
    __tablename__ = "payment_intents"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    
    # User and amount
    user_phone: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    
    # Intent type and direction
    intent_type: Mapped[str] = mapped_column(String(20), nullable=False)  # deposit, withdrawal
    description: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Status tracking
    status: Mapped[PaymentIntentStatus] = mapped_column(
        SQLEnum(PaymentIntentStatus),
        default=PaymentIntentStatus.PENDING,
        nullable=False
    )
    
    # External references
    payment_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user_payment_accounts.id", ondelete="CASCADE"),
        nullable=False
    )
    stripe_payment_intent_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    plaid_transfer_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ledger_transaction_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    
    # Processing details
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Metadata
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    
    # Relationships
    payment_account = relationship("UserPaymentAccount")
    
    __table_args__ = (
        Index("idx_payment_intent_user", "user_phone"),
        Index("idx_payment_intent_status", "status"),
        Index("idx_payment_intent_type", "intent_type"),
        Index("idx_payment_intent_account", "payment_account_id"),
    )


class NotificationUrgency(enum.Enum):
    """Notification urgency levels"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class NotificationSchedule(enum.Enum):
    """Notification delivery schedules"""
    IMMEDIATE = "immediate"
    BATCHED_HOURLY = "batched_hourly"
    BATCHED_DAILY = "batched_daily"
    BUSINESS_HOURS = "business_hours"


class ExpertNotificationPreferences(Base, TimestampMixin):
    """Expert notification preferences and settings"""
    __tablename__ = "expert_notification_preferences"
    
    contact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contacts.id", ondelete="CASCADE"),
        primary_key=True
    )
    
    # Notification channels
    sms_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    email_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    push_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # Scheduling preferences
    notification_schedule: Mapped[NotificationSchedule] = mapped_column(
        SQLEnum(NotificationSchedule),
        default=NotificationSchedule.IMMEDIATE,
        nullable=False
    )
    
    # Filtering preferences
    urgency_filter: Mapped[NotificationUrgency] = mapped_column(
        SQLEnum(NotificationUrgency),
        default=NotificationUrgency.LOW,
        nullable=False
    )
    
    # Business hours configuration (JSON format: {"start": "09:00", "end": "17:00", "timezone": "UTC"})
    business_hours: Mapped[dict[str, Any]] = mapped_column(
        JSONB, 
        default=lambda: {"start": "09:00", "end": "17:00", "timezone": "UTC"},
        nullable=False
    )
    
    # Quiet hours configuration
    quiet_hours_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    quiet_hours_start: Mapped[str] = mapped_column(String(5), default="22:00", nullable=False)
    quiet_hours_end: Mapped[str] = mapped_column(String(5), default="08:00", nullable=False)
    
    # Rate limiting
    max_notifications_per_hour: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    max_notifications_per_day: Mapped[int] = mapped_column(Integer, default=20, nullable=False)
    
    # Topic/expertise filtering
    expertise_matching_threshold: Mapped[float] = mapped_column(Float, default=0.3, nullable=False)
    auto_decline_low_match: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # Relationships
    contact = relationship("Contact")
    
    __table_args__ = (
        Index("idx_notification_prefs_contact", "contact_id"),
        CheckConstraint("max_notifications_per_hour > 0", name="check_hourly_limit"),
        CheckConstraint("max_notifications_per_day > 0", name="check_daily_limit"),
    )


class ResponseDraft(Base, TimestampMixin):
    """Draft responses for experts to save work in progress"""
    __tablename__ = "response_drafts"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    
    # Links to contribution (may not exist yet)
    contribution_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contributions.id", ondelete="CASCADE"),
        nullable=True
    )
    
    # Alternative linking via query and contact
    query_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("queries.id", ondelete="CASCADE"),
        nullable=False
    )
    contact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contacts.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # Draft content
    draft_content: Mapped[str] = mapped_column(Text, nullable=False)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    
    # Metadata for rich editor support
    content_format: Mapped[str] = mapped_column(String(20), default="plaintext", nullable=False)  # plaintext, html, markdown
    attachments: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list, nullable=False)
    
    # Auto-save tracking
    auto_save_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_final: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # Relationships
    contribution = relationship("Contribution")
    query = relationship("Query")
    contact = relationship("Contact")
    
    __table_args__ = (
        Index("idx_draft_query", "query_id"),
        Index("idx_draft_contact", "contact_id"),
        Index("idx_draft_contribution", "contribution_id"),
        UniqueConstraint("query_id", "contact_id", name="uq_draft_query_contact"),
    )


class ResponseQualityReview(Base, TimestampMixin):
    """Peer reviews and quality assessments for expert responses"""
    __tablename__ = "response_quality_reviews"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    
    contribution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contributions.id", ondelete="CASCADE"),
        nullable=False
    )
    reviewer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contacts.id", ondelete="SET NULL"),
        nullable=True
    )
    
    # Quality assessment
    quality_score: Mapped[float] = mapped_column(
        Float, 
        CheckConstraint("quality_score >= 0 AND quality_score <= 5"),
        nullable=False
    )
    accuracy_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    helpfulness_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    clarity_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    
    # Review details
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommended_improvements: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Review context
    is_automated_review: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    review_weight: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    
    # Relationships
    contribution = relationship("Contribution")
    reviewer = relationship("Contact", foreign_keys=[reviewer_id])
    
    __table_args__ = (
        Index("idx_quality_review_contribution", "contribution_id"),
        Index("idx_quality_review_reviewer", "reviewer_id"),
        Index("idx_quality_review_score", "quality_score"),
        UniqueConstraint("contribution_id", "reviewer_id", name="uq_review_contribution_reviewer"),
    )


class ExpertAvailabilitySchedule(Base, TimestampMixin):
    """Expert availability schedules and temporary unavailability"""
    __tablename__ = "expert_availability_schedules"
    
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
    
    # Schedule configuration (JSON format with weekly schedule)
    weekly_schedule: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    
    # Temporary overrides
    temporary_unavailable_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    temporary_unavailable_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    unavailable_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    # Vacation/long-term unavailability
    vacation_mode_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    vacation_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    vacation_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    vacation_auto_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Relationships
    contact = relationship("Contact")
    
    __table_args__ = (
        Index("idx_availability_contact", "contact_id"),
        Index("idx_availability_vacation", "vacation_mode_enabled"),
        UniqueConstraint("contact_id", name="uq_availability_contact"),
    )
