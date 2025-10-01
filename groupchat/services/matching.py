"""Smart expert-to-query matching algorithm"""

import logging
import time
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import and_, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from groupchat.config import settings
from groupchat.db.models import Contact, ContactExpertise, ContactStatus, ExpertiseTag, Query, Contribution
from groupchat.schemas.contacts import ContactResponse
from groupchat.services.contacts import ContactService
from groupchat.schemas.matching import (
    ExpertMatch,
    ExpertMatchScores,
    MatchingRequest,
    MatchingResponse,
    MatchingStats,
)
from groupchat.utils.geographic import (
    calculate_geographic_boost,
    extract_coordinates,
    get_timezone_offset,
    is_business_hours,
    is_local_query,
)

logger = logging.getLogger(__name__)


class ExpertMatchingService:
    """Service for matching experts to queries using multi-factor scoring"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def match_experts(
        self,
        query: Query,
        request: MatchingRequest | None = None
    ) -> MatchingResponse:
        """
        Main entry point for expert matching
        Implements the algorithm from Issue #5
        """
        start_time = time.time()
        
        try:
            if request is None:
                request = MatchingRequest(query_id=query.id)
            
            logger.info(f"Starting expert matching for query {query.id}")
            
            # Step 1: Get all available experts
            candidates = await self._get_candidate_experts()
            logger.debug(f"Found {len(candidates)} candidate experts")
            
            # Step 2: Filter by basic availability and exclude query author
            available_experts = await self._filter_available_experts(candidates)
            available_experts = await self._exclude_query_author(available_experts, query)
            logger.debug(f"Found {len(available_experts)} available experts (excluding query author)")
            
            # Step 3: Exclude recently contacted experts if requested
            if request.exclude_recent:
                available_experts = await self._exclude_recent_contacts(
                    available_experts, query.id
                )
                logger.debug(f"After excluding recent contacts: {len(available_experts)} experts")
            
            # Step 4: Perform vector similarity search
            similarity_matches = await self._vector_similarity_search(
                query, available_experts
            )
            logger.debug(f"Vector similarity search returned {len(similarity_matches)} matches")
            
            # Step 5: Calculate multi-factor scores
            scored_matches = await self._calculate_match_scores(
                query, similarity_matches, request
            )
            logger.debug(f"Multi-factor scoring returned {len(scored_matches)} scored matches")
            
            # Step 6: Apply diversity filtering and wave grouping
            final_matches = await self._apply_diversity_and_waves(
                scored_matches, request
            )
            logger.debug(f"After diversity filtering: {len(final_matches)} final matches")
            
            # Step 7: Limit results
            final_matches = final_matches[:request.limit]
            
            end_time = time.time()
            processing_time_ms = (end_time - start_time) * 1000
            
            logger.info(
                f"Expert matching completed in {processing_time_ms:.2f}ms, "
                f"found {len(final_matches)} matches"
            )
            
            return MatchingResponse(
                query_id=query.id,
                matches=final_matches,
                total_candidates=len(candidates),
                search_time_ms=processing_time_ms,
                matching_strategy="multi_factor_scoring_v1",
                metadata={
                    "available_experts": len(available_experts),
                    "similarity_matches": len(similarity_matches),
                    "location_boost_enabled": request.location_boost,
                    "wave_size": request.wave_size
                }
            )
            
        except Exception as e:
            logger.error(f"Expert matching failed at step with error: {e}", exc_info=True)
            # Re-raise with more context
            raise RuntimeError(f"Expert matching failed: {str(e)}") from e

    async def _get_candidate_experts(self) -> list[Contact]:
        """Get all potentially matchable experts"""
        try:
            stmt = (
                select(Contact)
                .options(
                    selectinload(Contact.expertise_tags),
                    selectinload(Contact.contributions)
                )
                .where(Contact.deleted_at.is_(None))
                .where(Contact.status == ContactStatus.ACTIVE)
            )
            
            result = await self.db.execute(stmt)
            candidates = list(result.scalars().all())
            logger.info(f"Found {len(candidates)} candidate experts")
            return candidates
        except Exception as e:
            logger.error(f"Error getting candidate experts: {e}")
            return []

    async def _filter_available_experts(self, candidates: list[Contact]) -> list[Contact]:
        """Filter experts by availability status"""
        return [
            expert for expert in candidates
            if expert.is_available
        ]

    async def _exclude_query_author(self, experts: list[Contact], query: Query) -> list[Contact]:
        """Exclude the person who asked the question from being matched"""
        return [
            expert for expert in experts
            if expert.phone_number != query.user_phone
        ]

    async def _exclude_recent_contacts(
        self,
        experts: list[Contact],
        query_id: UUID
    ) -> list[Contact]:
        """Exclude experts contacted recently (last 24 hours)"""
        cutoff_time = datetime.utcnow() - timedelta(hours=24)
        
        # Get recently contacted expert IDs
        recent_stmt = (
            select(Contact.id)
            .join(Contribution, Contact.id == Contribution.contact_id)
            .where(
                and_(
                    Contribution.requested_at >= cutoff_time,
                    Contribution.query_id != query_id
                )
            )
        )
        
        result = await self.db.execute(recent_stmt)
        recent_expert_ids = {row[0] for row in result.fetchall()}
        
        return [
            expert for expert in experts
            if expert.id not in recent_expert_ids
        ]

    async def _vector_similarity_search(
        self,
        query: Query,
        experts: list[Contact]
    ) -> list[tuple[Contact, float]]:
        """Perform keyword-based matching for MVP (no vector embeddings)"""
        logger.info(f"Performing keyword-based matching for query {query.id} with {len(experts)} experts")
        
        if not experts:
            return []
        
        # For MVP: Use keyword matching instead of vector similarity
        query_text = query.question_text.lower()
        query_keywords = set(query_text.split())
        
        # Remove common words
        stop_words = {'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 'from', 
                     'has', 'he', 'in', 'is', 'it', 'its', 'of', 'on', 'that', 'the', 
                     'to', 'was', 'were', 'will', 'with', 'how', 'what', 'when', 'where', 
                     'why', 'who', 'i', 'you', 'me', 'my', 'your', 'can', 'should', 'would'}
        query_keywords = query_keywords - stop_words
        
        matches = []
        
        for expert in experts:
            # Calculate keyword-based similarity
            similarity_score = 0.0
            
            # Check bio for keyword matches
            if expert.bio:
                bio_words = set(expert.bio.lower().split())
                bio_matches = len(query_keywords.intersection(bio_words))
                similarity_score += bio_matches * 0.3
            
            # Check expertise summary for keyword matches
            if expert.expertise_summary:
                expertise_words = set(expert.expertise_summary.lower().split())
                expertise_matches = len(query_keywords.intersection(expertise_words))
                similarity_score += expertise_matches * 0.4
            
            # Check expertise tags for keyword matches
            expert_tag_words = set()
            for tag in expert.expertise_tags:
                expert_tag_words.update(tag.name.lower().split())
                if tag.description:
                    expert_tag_words.update(tag.description.lower().split())
            
            tag_matches = len(query_keywords.intersection(expert_tag_words))
            similarity_score += tag_matches * 0.5
            
            # Normalize similarity score (rough approximation)
            max_possible_matches = len(query_keywords)
            if max_possible_matches > 0:
                similarity_score = min(1.0, similarity_score / max_possible_matches)
            
            # Add some randomness to avoid identical scores
            import random
            similarity_score += random.uniform(-0.1, 0.1)
            similarity_score = max(0.0, min(1.0, similarity_score))
            
            # Boost experts with higher trust scores
            if expert.trust_score > 0.7:
                similarity_score += 0.1
            
            # Always include some experts even with low keyword overlap for functionality
            if similarity_score < 0.2:
                similarity_score = random.uniform(0.15, 0.35)
            
            matches.append((expert, similarity_score))
            
            logger.debug(f"Expert {expert.name}: keyword similarity = {similarity_score:.3f}")
        
        # Sort by similarity score and return top matches
        matches = sorted(matches, key=lambda x: x[1], reverse=True)
        
        # Ensure we have at least 3 matches for functionality
        if len(matches) < 3 and len(experts) >= 3:
            # Add more experts with reasonable scores
            unmatched_experts = [e for e in experts if not any(e.id == m[0].id for m in matches)]
            for expert in unmatched_experts[:3-len(matches)]:
                matches.append((expert, random.uniform(0.25, 0.45)))
        
        logger.info(f"Keyword matching found {len(matches)} expert matches")
        return matches

    async def _calculate_match_scores(
        self,
        query: Query,
        similarity_matches: list[tuple[Contact, float]],
        request: MatchingRequest
    ) -> list[ExpertMatch]:
        """Calculate multi-factor scores for each expert"""
        query_tags = await self._extract_query_tags(query)
        query_coords = extract_coordinates(query.context.get("location"))
        is_local = is_local_query(query.question_text)
        
        matches = []
        
        for expert, embedding_similarity in similarity_matches:
            # Calculate individual score components
            tag_overlap = await self._calculate_tag_overlap(expert, query_tags)
            trust_score = expert.trust_score
            availability_boost = self._calculate_availability_boost(expert)
            responsiveness_rate = expert.response_rate
            
            # Geographic boost for local queries
            geographic_boost = 0.0
            distance_km = None
            if is_local and request.location_boost:
                expert_coords = extract_coordinates(expert.extra_metadata.get("location"))
                geographic_boost = calculate_geographic_boost(query_coords, expert_coords)
                if expert_coords and query_coords:
                    from groupchat.utils.geographic import haversine_distance
                    distance_km = haversine_distance(*query_coords, *expert_coords)
            
            # Calculate final weighted score
            final_score = (
                settings.embedding_weight * embedding_similarity +
                settings.tag_overlap_weight * tag_overlap +
                settings.trust_score_weight * trust_score +
                settings.availability_weight * availability_boost +
                settings.responsiveness_weight * responsiveness_rate +
                geographic_boost  # Additional boost, not replacing any weight
            )
            
            # Normalize to [0, 1] range
            final_score = min(1.0, max(0.0, final_score))
            
            scores = ExpertMatchScores(
                embedding_similarity=embedding_similarity,
                tag_overlap=tag_overlap,
                trust_score=trust_score,
                availability_boost=availability_boost,
                responsiveness_rate=responsiveness_rate,
                geographic_boost=geographic_boost,
                final_score=final_score
            )
            
            # Generate match reasons
            match_reasons = self._generate_match_reasons(scores, is_local, distance_km)
            
            # Get timezone information
            timezone_offset = get_timezone_offset(
                expert.extra_metadata.get("location")
            )
            
            # Convert Contact model to ContactResponse schema
            contact_response = self._convert_contact_to_response(expert)
            
            match = ExpertMatch(
                contact=contact_response,
                scores=scores,
                match_reasons=match_reasons,
                distance_km=distance_km,
                timezone_offset=timezone_offset,
                availability_status="available" if expert.is_available else "unavailable",
                recent_query_count=await self._get_recent_query_count(expert.id)
            )
            
            matches.append(match)
        
        return sorted(matches, key=lambda x: x.scores.final_score, reverse=True)

    async def _extract_query_tags(self, query: Query) -> set[str]:
        """Extract relevant tags from query context or text analysis"""
        tags = set()
        
        # Get explicit tags from context
        if "tags" in query.context:
            tags.update(query.context["tags"])
        
        # Simple keyword extraction (can be enhanced with NLP)
        query_lower = query.question_text.lower()
        
        # Get all available expertise tags for matching
        stmt = select(ExpertiseTag.name)
        result = await self.db.execute(stmt)
        all_tags = {tag[0].lower() for tag in result.fetchall()}
        
        # Find tags mentioned in query text
        for tag in all_tags:
            if tag in query_lower:
                tags.add(tag)
        
        return tags

    async def _calculate_tag_overlap(self, expert: Contact, query_tags: set[str]) -> float:
        """Calculate overlap between expert expertise and query tags"""
        if not query_tags:
            return 0.5  # Neutral score if no tags available
        
        expert_tags = {tag.name.lower() for tag in expert.expertise_tags}
        
        if not expert_tags:
            return 0.0
        
        overlap = len(query_tags.intersection(expert_tags))
        union = len(query_tags.union(expert_tags))
        
        # Jaccard similarity
        return overlap / union if union > 0 else 0.0

    def _calculate_availability_boost(self, expert: Contact) -> float:
        """Calculate availability boost based on current status and capacity"""
        if not expert.is_available:
            return 0.0
        
        # Check if expert is under their daily query limit
        # This would need to be implemented with actual query counting
        # For now, just return a boost for available experts
        return 1.0 if expert.is_available else 0.0

    def _generate_match_reasons(
        self,
        scores: ExpertMatchScores,
        is_local: bool,
        distance_km: float | None
    ) -> list[str]:
        """Generate human-readable reasons for the match"""
        reasons = []
        
        if scores.embedding_similarity > 0.7:
            reasons.append("High semantic similarity to query")
        elif scores.embedding_similarity > 0.5:
            reasons.append("Good semantic match")
        
        if scores.tag_overlap > 0.3:
            reasons.append("Matching expertise areas")
        
        if scores.trust_score > 0.8:
            reasons.append("Highly trusted expert")
        elif scores.trust_score > 0.6:
            reasons.append("Reliable contributor")
        
        if scores.responsiveness_rate > 0.8:
            reasons.append("Fast responder")
        
        if scores.geographic_boost > 0.1 and distance_km:
            if distance_km < 10:
                reasons.append("Very close by")
            elif distance_km < 50:
                reasons.append("Local area expert")
            else:
                reasons.append("Regional expert")
        
        if not reasons:
            reasons.append("General match")
        
        return reasons

    async def _get_recent_query_count(self, expert_id: UUID) -> int:
        """Get count of recent queries for this expert"""
        cutoff_time = datetime.utcnow() - timedelta(days=7)
        
        stmt = (
            select(func.count())
            .select_from(Contact)
            .join(Contribution, Contact.id == Contribution.contact_id)
            .where(Contact.id == expert_id)
            .where(Contribution.requested_at >= cutoff_time)
        )
        
        result = await self.db.execute(stmt)
        return result.scalar() or 0

    async def _apply_diversity_and_waves(
        self,
        matches: list[ExpertMatch],
        request: MatchingRequest
    ) -> list[ExpertMatch]:
        """Apply diversity filtering and wave-based grouping"""
        if not matches:
            return matches
        
        # Simple diversity: ensure we don't have too many experts with identical top expertise
        diverse_matches = self._apply_diversity_filter(matches)
        
        # Apply wave grouping
        wave_grouped = self._apply_wave_grouping(diverse_matches, request.wave_size)
        
        return wave_grouped

    def _apply_diversity_filter(self, matches: list[ExpertMatch]) -> list[ExpertMatch]:
        """Ensure diversity in expertise areas"""
        if len(matches) <= 5:
            return matches  # Skip diversity for small result sets
        
        diverse_matches: list[ExpertMatch] = []
        seen_expertise_combos = set()
        
        for match in matches:
            # Create a signature from top expertise tags
            expertise_signature = tuple(sorted([
                tag.name for tag in (match.contact.expertise_tags or [])[:3]
            ]))
            
            # Allow some duplication but not complete overlap
            if len(diverse_matches) < 3 or expertise_signature not in seen_expertise_combos:
                diverse_matches.append(match)
                seen_expertise_combos.add(expertise_signature)
            elif len([m for m in diverse_matches 
                     if [tag.name for tag in m.contact.expertise_tags] == 
                        [tag.name for tag in match.contact.expertise_tags]]) < 2:
                # Allow up to 2 experts with same expertise
                diverse_matches.append(match)
        
        return diverse_matches

    def _apply_wave_grouping(
        self,
        matches: list[ExpertMatch],
        wave_size: int
    ) -> list[ExpertMatch]:
        """Group matches into waves for progressive outreach"""
        for i, match in enumerate(matches):
            match.wave_group = (i // wave_size) + 1
        
        return matches

    def _convert_contact_to_response(self, expert: Contact) -> ContactResponse:
        """Convert Contact model to ContactResponse schema"""
        from groupchat.schemas.contacts import ContactExpertiseResponse, ExpertiseTagResponse
        
        expertise_tags = []
        for tag in (expert.expertise_tags or []):
            tag_response = ExpertiseTagResponse(
                id=tag.id,
                name=tag.name,
                category=tag.category,
                description=tag.description,
                created_at=tag.created_at,
                updated_at=tag.updated_at
            )
            expertise_tags.append(ContactExpertiseResponse(
                tag=tag_response,
                confidence_score=1.0  # Default confidence
            ))
        
        return ContactResponse(
            id=expert.id,
            phone_number=expert.phone_number,
            email=expert.email,
            name=expert.name,
            bio=expert.bio,
            expertise_summary=expert.expertise_summary,
            trust_score=expert.trust_score,
            response_rate=expert.response_rate,
            avg_response_time_minutes=expert.avg_response_time_minutes,
            total_contributions=expert.total_contributions,
            total_earnings_cents=expert.total_earnings_cents,
            is_available=expert.is_available,
            max_queries_per_day=expert.max_queries_per_day,
            preferred_contact_method=expert.preferred_contact_method,
            status=expert.status.value,
            expertise_tags=expertise_tags,
            created_at=expert.created_at,
            updated_at=expert.updated_at,
            deleted_at=expert.deleted_at
        )