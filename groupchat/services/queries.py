"""Query service layer with business logic"""

import logging
import uuid
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import func, select, update, cast
from sqlalchemy.dialects.postgresql import JSONB
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
from groupchat.schemas.queries import AcceptAnswerRequest, ContributionCreate, QueryCreate, QueryUpdate
from groupchat.schemas.matching import MatchingRequest

logger = logging.getLogger(__name__)


class QueryService:
    """Service for managing queries and their lifecycle"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_query(self, query_data: QueryCreate) -> Query:
        """Create a new query with validation and embedding generation"""

        # Validate budget against minimum requirements
        # query_price_cents is in cents (0.5 = 0.5 cents), min_experts is count
        min_cost_cents = settings.query_price_cents * query_data.min_experts
        if query_data.max_spend_cents < min_cost_cents:
            raise ValueError(
                f"Budget too low. Minimum required: ${min_cost_cents/100:.2f} "
                f"for {query_data.min_experts} experts"
            )

        # Generate embedding (disabled for MVP)
        # embedding = await self._generate_embedding(query_data.question_text)
        embedding = None

        # Calculate platform fee
        platform_fee = int(query_data.max_spend_cents * settings.platform_percentage)

        # Create query object
        query = Query(
            id=uuid.uuid4(),
            user_phone=query_data.user_phone,
            question_text=query_data.question_text,
            # question_embedding=embedding,  # Disabled for MVP
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

        # Trigger query processing workflow for real functionality (DON'T wait for it)
        try:
            await self._process_query_async(query)
        except Exception as e:
            logger.error(f"Error starting query processing for {query.id}: {e}", exc_info=True)

        # Refresh again to get latest state after processing
        await self.db.refresh(query)

        return query

    async def create_query_dict(self, query_data: QueryCreate) -> dict:
        """Create query and return as dict to avoid lazy loading issues"""
        # Build dict RIGHT after refresh while session is active
        query = await self._create_query_internal(query_data)

        # Access all fields IMMEDIATELY after refresh
        query_dict = {
            "id": query.id,
            "user_phone": query.user_phone,
            "question_text": query.question_text,
            "status": query.status.value,
            "max_experts": query.max_experts,
            "min_experts": query.min_experts,
            "timeout_minutes": query.timeout_minutes,
            "context": query.context if query.context else {},
            "total_cost_cents": query.total_cost_cents,
            "platform_fee_cents": query.platform_fee_cents,
            "error_message": query.error_message,
            "created_at": query.created_at,
            "updated_at": query.updated_at,
            "deleted_at": query.deleted_at
        }

        # NOW do async processing
        try:
            await self._process_query_async(query)
        except Exception as e:
            logger.error(f"Error starting query processing for {query.id}: {e}", exc_info=True)
            query_dict["status"] = QueryStatus.FAILED.value
            query_dict["error_message"] = f"Processing failed: {str(e)}"

        return query_dict

    async def _create_query_internal(self, query_data: QueryCreate) -> Query:
        """Internal method to create query without processing"""
        # Validate budget
        min_cost_cents = settings.query_price_cents * query_data.min_experts
        if query_data.max_spend_cents < min_cost_cents:
            raise ValueError(
                f"Budget too low. Minimum required: ${min_cost_cents/100:.2f} "
                f"for {query_data.min_experts} experts"
            )

        embedding = None
        platform_fee = int(query_data.max_spend_cents * settings.platform_percentage)

        query = Query(
            id=uuid.uuid4(),
            user_phone=query_data.user_phone,
            question_text=query_data.question_text,
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
    
    async def trigger_synthesis(self, query_id: UUID) -> CompiledAnswer:
        """Trigger answer synthesis for a query"""
        from groupchat.services.synthesis import SynthesisService
        
        synthesis_service = SynthesisService(self.db)
        return await synthesis_service.synthesize_answer(query_id)

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

        result = {
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

        # Include final answer if query is completed
        if query.status == QueryStatus.COMPLETED:
            compiled_answer = await self.get_query_answer(query_id)
            if compiled_answer:
                result["final_answer"] = compiled_answer.final_answer
                result["answer_summary"] = compiled_answer.summary
                result["confidence_score"] = compiled_answer.confidence_score
            
        return result

    async def _generate_embedding(self, text: str) -> list[float]:
        """Generate embedding for query text"""
        from groupchat.services.embeddings import EmbeddingService
        
        embedding_service = EmbeddingService()
        embedding = await embedding_service.generate_embedding(text)
        logger.debug(f"Generated embedding of length {len(embedding)}")
        return embedding

    async def _process_query_async(self, query: Query) -> None:
        """Start asynchronous query processing (matching + outreach)"""
        try:
            # Update status to ROUTING
            query.status = QueryStatus.ROUTING
            await self.db.commit()
            
            # Basic expert matching for MVP (without embeddings)
            from groupchat.services.matching import ExpertMatchingService
            from groupchat.schemas.matching import MatchingRequest
            
            matching_service = ExpertMatchingService(self.db)
            request = MatchingRequest(
                query_id=query.id,  # Add required query_id
                limit=query.max_experts,
                location_boost=False,  # Disable for MVP
                exclude_recent=False,  # Disable for MVP
                wave_size=3
            )
            
            # Match experts
            matching_result = await matching_service.match_experts(query, request)
            
            if matching_result.matches:
                # Update status to COLLECTING
                query.status = QueryStatus.COLLECTING
                await self.db.commit()
                
                logger.info(f"Query {query.id} matched to {len(matching_result.matches)} experts")
                
                # Create contribution requests for matched experts (no auto-generation)
                await self._create_contribution_requests(query, matching_result.matches[:5])
            else:
                logger.warning(f"No experts matched for query {query.id}")
                # No experts found - mark as failed with helpful message
                query.status = QueryStatus.FAILED
                query.error_message = "No experts found who can answer this question. Invite more experts to join the network!"
                await self.db.commit()
                
        except Exception as e:
            logger.error(f"Error processing query {query.id}: {e}")
            query.status = QueryStatus.FAILED
            query.error_message = str(e)
            await self.db.commit()
    
    async def _create_contribution_requests(self, query: Query, expert_matches: list) -> None:
        """Create contribution requests for matched experts (they need to respond manually)"""
        from groupchat.db.models import Contribution
        import uuid
        from datetime import datetime
        
        requests_created = 0
        
        for expert_match in expert_matches:
            try:
                contact_id = expert_match.contact.id if hasattr(expert_match, 'contact') else None
                
                # Create contribution request (empty response, waiting for expert)
                contribution = Contribution(
                    id=uuid.uuid4(),
                    query_id=query.id,
                    contact_id=contact_id,
                    response_text="",  # Empty - waiting for expert to fill
                    confidence_score=0.0,  # Will be set when expert responds
                    requested_at=datetime.utcnow(),
                    responded_at=None,  # Not responded yet
                    response_time_minutes=None,
                    was_used=False,
                    relevance_score=expert_match.scores.final_score if hasattr(expert_match, 'scores') else 0.8,
                    extra_metadata={
                        "status": "pending_response",
                        "match_score": expert_match.scores.final_score if hasattr(expert_match, 'scores') else 0.8,
                        "invited_at": datetime.utcnow().isoformat()
                    }
                )
                self.db.add(contribution)
                requests_created += 1
                
            except Exception as e:
                logger.error(f"Error creating contribution request: {e}")
                continue
        
        await self.db.commit()
        logger.info(f"Created {requests_created} contribution requests for query {query.id}")
        
        # Query stays in COLLECTING status until experts respond
    
    async def check_and_synthesize_if_ready(self, query_id: UUID) -> bool:
        """Check if query has enough responses and synthesize if ready"""
        try:
            query = await self.get_query(query_id)
            if not query or query.status != QueryStatus.COLLECTING:
                return False
            
            # Get actual responses (not empty contribution requests)
            contributions = await self.get_query_contributions(query_id)
            actual_responses = [c for c in contributions if c.responded_at and c.response_text.strip()]
            
            # Synthesize if we have minimum responses
            if len(actual_responses) >= query.min_experts:
                from groupchat.services.synthesis import SynthesisService
                
                query.status = QueryStatus.COMPILING
                await self.db.commit()
                
                synthesis_service = SynthesisService(self.db)
                compiled_answer = await synthesis_service.synthesize_answer(query_id)
                
                if compiled_answer:
                    query.status = QueryStatus.COMPLETED
                    await self.db.commit()
                    logger.info(f"Query {query_id} synthesized with {len(actual_responses)} responses")
                    return True
                    
        except Exception as e:
            logger.error(f"Error in synthesis check for query {query_id}: {e}")
            
        return False

    async def update_contribution(self, contribution_id: UUID, contribution_data) -> Contribution | None:
        """Update an existing contribution with expert's response"""
        from sqlalchemy import select, update
        from datetime import datetime
        
        # Get the existing contribution
        stmt = select(Contribution).where(Contribution.id == contribution_id)
        result = await self.db.execute(stmt)
        contribution = result.scalar_one_or_none()
        
        if not contribution:
            return None
            
        # Update the contribution with expert's response
        update_stmt = (
            update(Contribution)
            .where(Contribution.id == contribution_id)
            .values(
                response_text=contribution_data.response_text,
                confidence_score=contribution_data.confidence_score,
                responded_at=datetime.utcnow(),
                response_time_minutes=(datetime.utcnow() - contribution.requested_at).total_seconds() / 60.0 if contribution.requested_at else 0.0,
                extra_metadata={
                    **contribution.extra_metadata,
                    "status": "responded",
                    "responded_at": datetime.utcnow().isoformat(),
                    "source_links": contribution_data.source_links
                },
                updated_at=datetime.utcnow()
            )
        )
        
        await self.db.execute(update_stmt)
        await self.db.commit()
        
        # Refresh and return the updated contribution
        await self.db.refresh(contribution)
        return contribution

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

    async def route_query_to_experts(
        self,
        query_id: UUID,
        max_experts: int | None = None,
        location_boost: bool = True
    ) -> dict[str, Any]:
        """
        Route a query to matched experts and update status to ROUTING
        Integration point with the matching algorithm
        """
        query = await self.get_query(query_id)
        if not query:
            raise ValueError("Query not found")
        
        if query.status != QueryStatus.PENDING:
            raise ValueError("Can only route pending queries")
        
        # Update status to ROUTING
        await self.update_status(query_id, QueryStatus.ROUTING)
        
        try:
            # Import here to avoid circular dependency
            from groupchat.services.matching import ExpertMatchingService
            
            matching_service = ExpertMatchingService(self.db)
            
            # Create matching request
            request = MatchingRequest(
                query_id=query_id,
                limit=max_experts or query.max_experts,
                location_boost=location_boost,
                exclude_recent=False,  # Temporarily disabled for testing
                wave_size=3
            )
            
            # Get expert matches
            matching_result = await matching_service.match_experts(query, request)
            
            # Store matching results in query context for later use
            await self._store_matching_results(query_id, matching_result)
            
            # Update status to COLLECTING (ready for outreach)
            await self.update_status(query_id, QueryStatus.COLLECTING)
            
            logger.info(
                f"Routed query {query_id} to {len(matching_result.matches)} experts "
                f"in {matching_result.search_time_ms:.2f}ms"
            )
            
            return {
                "success": True,
                "query_id": query_id,
                "experts_matched": len(matching_result.matches),
                "matching_time_ms": matching_result.search_time_ms,
                "wave_groups": max(match.wave_group for match in matching_result.matches) if matching_result.matches else 0,
                "top_matches": [
                    {
                        "expert_id": match.contact.id,
                        "name": match.contact.name,
                        "score": match.scores.final_score,
                        "reasons": match.match_reasons[:3]  # Top 3 reasons
                    }
                    for match in matching_result.matches[:5]  # Top 5 for summary
                ]
            }
            
        except Exception as e:
            # Rollback status on error
            await self.update_status(query_id, QueryStatus.FAILED, str(e))
            logger.error(f"Failed to route query {query_id}: {e}")
            raise
    
    async def get_expert_matches(self, query_id: UUID) -> dict[str, Any] | None:
        """Get stored expert matching results for a query"""
        query = await self.get_query(query_id)
        if not query:
            return None
        
        return query.context.get("expert_matches")
    
    async def _store_matching_results(
        self,
        query_id: UUID,
        matching_result
    ) -> None:
        """Store matching results in query context"""
        from sqlalchemy import update as sql_update
        
        # Convert matching result to storable format
        expert_matches = {
            "total_candidates": matching_result.total_candidates,
            "search_time_ms": matching_result.search_time_ms,
            "matching_strategy": matching_result.matching_strategy,
            "matches": [
                {
                    "expert_id": str(match.contact.id),
                    "expert_name": match.contact.name,
                    "scores": {
                        "final_score": match.scores.final_score,
                        "embedding_similarity": match.scores.embedding_similarity,
                        "tag_overlap": match.scores.tag_overlap,
                        "trust_score": match.scores.trust_score,
                        "availability_boost": match.scores.availability_boost,
                        "responsiveness_rate": match.scores.responsiveness_rate,
                        "geographic_boost": match.scores.geographic_boost
                    },
                    "match_reasons": match.match_reasons,
                    "distance_km": match.distance_km,
                    "wave_group": match.wave_group,
                    "availability_status": match.availability_status
                }
                for match in matching_result.matches
            ]
        }
        
        # Update query context with matching results
        stmt = (
            sql_update(Query)
            .where(Query.id == query_id)
            .values(
                context=func.jsonb_set(
                    Query.context,
                    ['expert_matches'],
                    cast(expert_matches, JSONB)
                ),
                updated_at=datetime.utcnow()
            )
        )
        
        await self.db.execute(stmt)
        await self.db.commit()

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

    async def send_outreach_to_experts(
        self,
        query_id: UUID,
        user_name: str = "Someone"
    ) -> dict[str, Any]:
        """Send SMS outreach to matched experts for a query"""
        query = await self.get_query(query_id)
        if not query:
            raise ValueError("Query not found")
        
        if query.status != QueryStatus.COLLECTING:
            raise ValueError("Query must be in COLLECTING status for outreach")
        
        # Get expert matches from stored context
        expert_matches = await self.get_expert_matches(query_id)
        if not expert_matches or not expert_matches.get("matches"):
            raise ValueError("No expert matches found for query")
        
        # Import SMS service
        # Removed SMS service - using dashboard notifications instead
        from groupchat.services.contacts import ContactService
        
        # Get contact details for matched experts
        contact_service = ContactService(self.db)
        expert_contacts = []
        
        for match in expert_matches["matches"]:
            expert_id = UUID(match["expert_id"])
            contact = await contact_service.get_contact_by_id(expert_id)
            if contact:
                expert_contacts.append(contact)
        
        # Create dashboard notifications for experts (instead of SMS)
        # Mock SMS results for demo purposes
        results = {
            "sent": [{"contact_id": str(contact.id), "phone": contact.phone_number} for contact in expert_contacts],
            "failed": [],
            "skipped": []
        }
        
        # Create notification entries for each expert (for dashboard display)
        for contact in expert_contacts:
            await self._create_expert_notification(
                query_id=query_id,
                expert_id=contact.id,
                question_text=query.question_text[:100] + "..." if len(query.question_text) > 100 else query.question_text
            )
        
        # Update query context with outreach results
        outreach_data = {
            "sent_at": datetime.utcnow().isoformat(),
            "sent_to": len(results["sent"]),
            "failed": len(results["failed"]),
            "skipped": len(results["skipped"]),
            "details": results,
            "notification_method": "dashboard"
        }
        
        await self._update_query_context(query_id, "sms_outreach", outreach_data)
        
        logger.info(f"SMS outreach completed for query {query_id}: "
                   f"{len(results['sent'])} sent, {len(results['failed'])} failed, "
                   f"{len(results['skipped'])} skipped")
        
        return {
            "success": True,
            "query_id": query_id,
            "outreach_results": results,
            "total_experts": len(expert_contacts),
            "messages_sent": len(results["sent"])
        }

    async def _update_query_context(
        self,
        query_id: UUID,
        key: str,
        data: Any
    ) -> None:
        """Update a specific key in query context"""
        from sqlalchemy import update as sql_update
        
        stmt = (
            sql_update(Query)
            .where(Query.id == query_id)
            .values(
                context=func.jsonb_set(
                    Query.context,
                    [key],
                    cast(data, JSONB)
                ),
                updated_at=datetime.utcnow()
            )
        )
        
        await self.db.execute(stmt)
        await self.db.commit()


    async def create_contribution(self, query_id: UUID, contribution_data: ContributionCreate) -> Contribution | None:
        """Create a new contribution for a query (expert response)"""
        
        # First, verify the query exists and is accepting contributions
        query = await self.get_query(query_id)
        if not query:
            return None
            
        if query.status not in [QueryStatus.COLLECTING, QueryStatus.ROUTING]:
            raise ValueError(f"Query {query_id} is not accepting contributions (status: {query.status})")
        
        # Create the contribution record
        contribution = Contribution(
            id=uuid.uuid4(),
            query_id=query_id,
            contact_id=None,  # For demo purposes, we don't link to specific contacts
            response_text=contribution_data.response_text,
            confidence_score=contribution_data.confidence_score,
            requested_at=datetime.utcnow(),  # Mark as requested now
            responded_at=datetime.utcnow(),  # And responded immediately
            response_time_minutes=0.0,  # Instant response for demo
            was_used=False,  # Will be marked true during synthesis
            quality_rating=None,
            payout_amount_cents=0,  # Will be calculated during payment processing
            extra_metadata={
                "source_links": contribution_data.source_links,
                "expert_name": contribution_data.expert_name,
                "demo_contribution": True,
                "submitted_via": "expert_interface"
            }
        )
        
        try:
            self.db.add(contribution)
            await self.db.commit()
            await self.db.refresh(contribution)
            
            # Update query status to collecting if it wasn't already
            if query.status == QueryStatus.ROUTING:
                await self.update_status(query_id, QueryStatus.COLLECTING, "Expert contributions being collected")
            
            logger.info(f"Created contribution {contribution.id} for query {query_id}")
            return contribution
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error creating contribution for query {query_id}: {e}", exc_info=True)
            raise

    async def _create_expert_notification(self, query_id: UUID, expert_id: UUID, question_text: str) -> None:
        """Create a notification for an expert about a new question (dashboard display)"""
        try:
            # For now, we'll just log this. In a real implementation, you'd store this in a notifications table
            logger.info(f"📱 Notification created for expert {expert_id}: New question for query {query_id}")
            logger.info(f"Question preview: {question_text}")
            
            # In a full implementation, you'd create a notification record like:
            # notification = Notification(
            #     id=uuid.uuid4(),
            #     expert_id=expert_id,
            #     query_id=query_id,
            #     type="new_question",
            #     title="New Question Available",
            #     message=f"You have a new question to answer: {question_text}",
            #     created_at=datetime.utcnow(),
            #     read_at=None
            # )
            # self.db.add(notification)
            # await self.db.commit()
            
        except Exception as e:
            logger.error(f"Error creating notification for expert {expert_id}: {e}")
            # Don't raise here - notification failure shouldn't break the query flow
