"""API endpoints for expert matching system"""

import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from groupchat.db.database import get_db
from groupchat.schemas.matching import MatchingRequest, MatchingResponse, MatchingStats
from groupchat.services.matching import ExpertMatchingService
from groupchat.services.queries import QueryService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/matching", tags=["matching"])


@router.post("/experts/{query_id}")
async def match_experts_to_query(
    query_id: UUID,
    request: MatchingRequest | None = None,
    db: AsyncSession = Depends(get_db)
) -> MatchingResponse:
    """
    Find and rank experts for a specific query
    """
    try:
        # Get the query
        query_service = QueryService(db)
        query = await query_service.get_query(query_id)
        
        if not query:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Query not found"
            )
        
        # Set query_id if not provided in request
        if request is None:
            request = MatchingRequest(query_id=query_id)
        else:
            request.query_id = query_id
        
        # Perform matching
        matching_service = ExpertMatchingService(db)
        result = await matching_service.match_experts(query, request)
        
        return result
        
    except Exception as e:
        logger.error(f"Error matching experts for query {query_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during expert matching"
        )


@router.get("/stats/{query_id}")
async def get_matching_stats(
    query_id: UUID,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """
    Get statistics about the matching process for a query
    """
    try:
        query_service = QueryService(db)
        query = await query_service.get_query(query_id)
        
        if not query:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Query not found"
            )
        
        matching_service = ExpertMatchingService(db)
        
        # Get basic candidate counts
        candidates = await matching_service._get_candidate_experts()
        available = await matching_service._filter_available_experts(candidates)
        
        return {
            "query_id": query_id,
            "total_experts_in_system": len(candidates),
            "available_experts": len(available),
            "query_has_embedding": query.question_embedding is not None,
            "is_local_query": matching_service._is_local_query(query.question_text) if hasattr(matching_service, '_is_local_query') else False,
            "matching_weights": {
                "embedding_weight": matching_service.settings.embedding_weight if hasattr(matching_service, 'settings') else 0.45,
                "tag_overlap_weight": 0.20,
                "trust_score_weight": 0.15,
                "availability_weight": 0.10,
                "responsiveness_weight": 0.10
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting matching stats for query {query_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error getting matching statistics"
        )


@router.get("/test/similarity")
async def test_vector_similarity(
    text1: str,
    text2: str,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """
    Test endpoint for vector similarity calculations
    """
    try:
        matching_service = ExpertMatchingService(db)
        
        # This would need embedding generation
        # For now, return a mock response
        return {
            "text1": text1,
            "text2": text2,
            "similarity": 0.85,  # Mock similarity
            "method": "mock_calculation",
            "note": "Real embeddings not yet implemented"
        }
        
    except Exception as e:
        logger.error(f"Error testing similarity: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during similarity testing"
        )