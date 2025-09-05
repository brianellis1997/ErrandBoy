"""Query service layer with business logic"""

import logging
import uuid
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from groupchat.config import settings
from groupchat.db.models import (
    CompiledAnswer,
    Contribution,
    Ledger,
    LedgerEntryType,
    Query,
    QueryStatus,
    TransactionType,
)
from groupchat.schemas.queries import AcceptAnswerRequest, QueryCreate, QueryUpdate

logger = logging.getLogger(__name__)


class QueryService:
    """Service for managing queries and their lifecycle"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_query(self, query_data: QueryCreate) -> Query:
        """Create a new query with validation and embedding generation"""

        # Validate budget against minimum requirements
        min_cost = settings.query_price_cents * query_data.min_experts * 100
        if query_data.max_spend_cents < min_cost:
            raise ValueError(
                f"Budget too low. Minimum required: ${min_cost/100:.2f} "
                f"for {query_data.min_experts} experts"
            )

        # Generate embedding (mock for now)
        embedding = await self._generate_embedding(query_data.question_text)

        # Calculate platform fee
        platform_fee = int(query_data.max_spend_cents * settings.platform_percentage)

        # Create query object
        query = Query(
            id=uuid.uuid4(),
            user_phone=query_data.user_phone,
            question_text=query_data.question_text,
            question_embedding=embedding,
            status=QueryStatus.PENDING,
            max_experts=query_data.max_experts,
            min_experts=query_data.min_experts,
            timeout_minutes=query_data.timeout_minutes,
            total_cost_cents=query_data.max_spend_cents,
            platform_fee_cents=platform_fee,
            context=query_data.context
        )

        self.db.add(query)
        await self.db.commit()
        await self.db.refresh(query)

        logger.info(f"Created query {query.id} for user {query.user_phone}")
        return query

    async def get_query(self, query_id: UUID) -> Query | None:
        """Get query by ID with all relationships"""
        stmt = (
            select(Query)
            .options(
                selectinload(Query.contributions),
                selectinload(Query.compiled_answer).selectinload(CompiledAnswer.citations)
            )
            .where(Query.id == query_id)
            .where(Query.deleted_at.is_(None))
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_queries(
        self,
        skip: int = 0,
        limit: int = 100,
        user_phone: str | None = None,
        status: QueryStatus | None = None
    ) -> tuple[list[Query], int]:
        """List queries with pagination and filters"""

        # Build base query
        stmt = select(Query).where(Query.deleted_at.is_(None))
        count_stmt = select(func.count(Query.id)).where(Query.deleted_at.is_(None))

        # Apply filters
        if user_phone:
            stmt = stmt.where(Query.user_phone == user_phone)
            count_stmt = count_stmt.where(Query.user_phone == user_phone)

        if status:
            stmt = stmt.where(Query.status == status)
            count_stmt = count_stmt.where(Query.status == status)

        # Apply pagination and ordering
        stmt = stmt.order_by(Query.created_at.desc()).offset(skip).limit(limit)

        # Execute queries
        result = await self.db.execute(stmt)
        queries = result.scalars().all()

        count_result = await self.db.execute(count_stmt)
        total = count_result.scalar() or 0

        return list(queries), total

    async def update_query(self, query_id: UUID, update_data: QueryUpdate) -> Query | None:
        """Update query with validation"""
        query = await self.get_query(query_id)
        if not query:
            return None

        # Validate status - only allow updates for pending queries
        if query.status != QueryStatus.PENDING:
            raise ValueError("Cannot update query that is no longer pending")

        # Apply updates
        update_dict = update_data.model_dump(exclude_unset=True)
        if update_dict:
            stmt = (
                update(Query)
                .where(Query.id == query_id)
                .values(**update_dict, updated_at=datetime.utcnow())
            )
            await self.db.execute(stmt)
            await self.db.commit()

            # Refresh query
            await self.db.refresh(query)

        return query

    async def update_status(
        self,
        query_id: UUID,
        new_status: QueryStatus,
        error_message: str | None = None
    ) -> bool:
        """Update query status with validation"""

        query = await self.get_query(query_id)
        if not query:
            return False

        # Validate status transition
        if not self._is_valid_status_transition(query.status, new_status):
            raise ValueError(
                f"Invalid status transition from {query.status.value} to {new_status.value}"
            )

        # Update status
        update_data = {
            "status": new_status,
            "updated_at": datetime.utcnow()
        }
        if error_message:
            update_data["error_message"] = error_message

        stmt = update(Query).where(Query.id == query_id).values(**update_data)
        await self.db.execute(stmt)
        await self.db.commit()

        logger.info(f"Updated query {query_id} status to {new_status.value}")
        return True

    async def get_query_contributions(self, query_id: UUID) -> list[Contribution]:
        """Get all contributions for a query"""
        stmt = (
            select(Contribution)
            .where(Contribution.query_id == query_id)
            .order_by(Contribution.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_query_answer(self, query_id: UUID) -> CompiledAnswer | None:
        """Get compiled answer for a query"""
        stmt = (
            select(CompiledAnswer)
            .options(selectinload(CompiledAnswer.citations))
            .where(CompiledAnswer.query_id == query_id)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def accept_answer(
        self,
        query_id: UUID,
        accept_data: AcceptAnswerRequest
    ) -> dict[str, Any]:
        """Accept answer and trigger payment distribution"""

        query = await self.get_query(query_id)
        if not query:
            raise ValueError("Query not found")

        if query.status != QueryStatus.COMPLETED:
            raise ValueError("Can only accept answers for completed queries")

        compiled_answer = await self.get_query_answer(query_id)
        if not compiled_answer:
            raise ValueError("No compiled answer found for query")

        # Update user feedback if provided
        if accept_data.user_rating or accept_data.user_feedback:
            update_data = {"updated_at": datetime.utcnow()}
            if accept_data.user_rating:
                update_data["user_rating"] = accept_data.user_rating
            if accept_data.user_feedback:
                update_data["user_feedback"] = accept_data.user_feedback

            stmt = (
                update(CompiledAnswer)
                .where(CompiledAnswer.id == compiled_answer.id)
                .values(**update_data)
            )
            await self.db.execute(stmt)

        # Create transaction ID for payment processing
        transaction_id = uuid.uuid4()

        # Calculate payouts (simplified - real implementation would be more complex)
        contributor_pool = int(query.total_cost_cents * settings.contributor_pool_percentage)
        platform_fee = int(query.total_cost_cents * settings.platform_percentage)

        # Create ledger entries (simplified)
        await self._create_ledger_entry(
            transaction_id=transaction_id,
            transaction_type=TransactionType.QUERY_PAYMENT,
            account_type="user",
            account_id=query.user_phone,
            entry_type=LedgerEntryType.DEBIT,
            amount_cents=query.total_cost_cents,
            query_id=query_id,
            description=f"Payment for query {query_id}"
        )

        await self.db.commit()

        logger.info(f"Accepted answer for query {query_id}, transaction {transaction_id}")

        return {
            "success": True,
            "transaction_id": transaction_id,
            "total_payout_cents": contributor_pool,
            "platform_fee_cents": platform_fee,
            "message": "Answer accepted and payment processing initiated"
        }

    async def get_query_status(self, query_id: UUID) -> dict[str, Any] | None:
        """Get detailed status information for a query"""
        query = await self.get_query(query_id)
        if not query:
            return None

        contributions = await self.get_query_contributions(query_id)

        # Calculate progress metrics
        contributors_matched = len(contributions)  # Simplified
        contributions_received = len([c for c in contributions if c.responded_at])

        # Estimate completion time
        estimated_completion = None
        if query.status in [QueryStatus.ROUTING, QueryStatus.COLLECTING]:
            estimated_completion = query.created_at + timedelta(minutes=query.timeout_minutes)

        return {
            "id": query.id,
            "status": query.status.value,
            "progress": {
                "contributors_matched": contributors_matched,
                "contributions_received": contributions_received,
                "min_experts": query.min_experts,
                "max_experts": query.max_experts,
                "completion_percentage": min(100, (contributions_received / query.min_experts) * 100)
            },
            "estimated_completion": estimated_completion,
            "contributors_matched": contributors_matched,
            "contributions_received": contributions_received,
            "last_updated": query.updated_at
        }

    async def _generate_embedding(self, text: str) -> list[float]:
        """Generate embedding for query text"""
        if settings.enable_real_embeddings:
            # TODO: Implement real OpenAI embeddings
            logger.info("Real embeddings not yet implemented, using mock")

        # Generate mock embedding (1536 dimensions for OpenAI compatibility)
        import random
        random.seed(hash(text))  # Deterministic for testing
        embedding = [random.uniform(-1, 1) for _ in range(1536)]

        logger.debug(f"Generated mock embedding of length {len(embedding)}")
        return embedding

    def _is_valid_status_transition(
        self,
        current: QueryStatus,
        new: QueryStatus
    ) -> bool:
        """Validate if status transition is allowed"""

        valid_transitions = {
            QueryStatus.PENDING: [QueryStatus.ROUTING, QueryStatus.FAILED, QueryStatus.CANCELLED],
            QueryStatus.ROUTING: [QueryStatus.COLLECTING, QueryStatus.FAILED, QueryStatus.CANCELLED],
            QueryStatus.COLLECTING: [QueryStatus.COMPILING, QueryStatus.FAILED, QueryStatus.CANCELLED],
            QueryStatus.COMPILING: [QueryStatus.COMPLETED, QueryStatus.FAILED],
            QueryStatus.COMPLETED: [],  # Terminal state
            QueryStatus.FAILED: [],     # Terminal state
            QueryStatus.CANCELLED: []   # Terminal state
        }

        return new in valid_transitions.get(current, [])

    async def _create_ledger_entry(
        self,
        transaction_id: UUID,
        transaction_type: TransactionType,
        account_type: str,
        account_id: str,
        entry_type: LedgerEntryType,
        amount_cents: int,
        query_id: UUID | None = None,
        contact_id: UUID | None = None,
        description: str = "",
        extra_metadata: dict[str, Any] | None = None
    ) -> None:
        """Create a ledger entry for double-entry bookkeeping"""

        entry = Ledger(
            id=uuid.uuid4(),
            transaction_id=transaction_id,
            transaction_type=transaction_type,
            account_type=account_type,
            account_id=account_id,
            entry_type=entry_type,
            amount_cents=amount_cents,
            query_id=query_id,
            contact_id=contact_id,
            description=description,
            extra_metadata=extra_metadata or {}
        )

        self.db.add(entry)
        logger.debug(f"Created ledger entry: {entry_type.value} ${amount_cents/100:.2f}")
