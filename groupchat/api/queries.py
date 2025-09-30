"""Query management API endpoints"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi import Query as QueryParam
from sqlalchemy.ext.asyncio import AsyncSession

from groupchat.db.database import get_db
from groupchat.db.models import QueryStatus
from groupchat.schemas.queries import (
    AcceptAnswerRequest,
    AcceptAnswerResponse,
    CompiledAnswerResponse,
    ContributionCreate,
    ContributionListResponse,
    ContributionResponse,
    QueryCreate,
    QueryDetailResponse,
    QueryListResponse,
    QueryResponse,
    QueryStatusResponse,
    QueryUpdate,
)
from groupchat.services.queries import QueryService
from groupchat.services.synthesis import SynthesisService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/", response_model=QueryResponse, status_code=status.HTTP_201_CREATED)
async def create_query(
    query_data: QueryCreate,
    db: AsyncSession = Depends(get_db),
) -> QueryResponse:
    """Submit a new query"""
    try:
        service = QueryService(db)
        query = await service.create_query(query_data)
        
        # Convert to dict within the async context to avoid lazy loading issues
        query_dict = {
            "id": query.id,
            "user_phone": query.user_phone,
            "question_text": query.question_text,
            "status": query.status.value if query.status else "pending",
            "total_cost_cents": query.total_cost_cents,
            "platform_fee_cents": query.platform_fee_cents,
            "error_message": query.error_message,
            "max_experts": query.max_experts,
            "min_experts": query.min_experts,
            "timeout_minutes": query.timeout_minutes,
            "context": query.context or {},
            "created_at": query.created_at,
            "updated_at": query.updated_at,
            "deleted_at": query.deleted_at
        }
        
        return QueryResponse(**query_dict)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error creating query: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("/", response_model=QueryListResponse)
async def list_queries(
    skip: int = QueryParam(0, ge=0),
    limit: int = QueryParam(100, ge=1, le=1000),
    user_phone: str | None = QueryParam(None),
    status_filter: str | None = QueryParam(None, alias="status"),
    db: AsyncSession = Depends(get_db),
) -> QueryListResponse:
    """List all queries with pagination and filters"""
    try:
        service = QueryService(db)

        # Parse status filter
        status_enum = None
        if status_filter:
            try:
                status_enum = QueryStatus(status_filter.lower())
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid status filter: {status_filter}"
                )

        queries, total = await service.list_queries(
            skip=skip,
            limit=limit,
            user_phone=user_phone,
            status=status_enum
        )

        return QueryListResponse(
            queries=[QueryResponse.model_validate(q) for q in queries],
            total=total,
            skip=skip,
            limit=limit
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing queries: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("/{query_id}", response_model=QueryDetailResponse)
async def get_query(
    query_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> QueryDetailResponse:
    """Get a specific query by ID with full details"""
    try:
        service = QueryService(db)
        query = await service.get_query(query_id)

        if not query:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Query not found"
            )

        return QueryDetailResponse.model_validate(query)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting query {query_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.put("/{query_id}", response_model=QueryResponse)
async def update_query(
    query_id: UUID,
    update_data: QueryUpdate,
    db: AsyncSession = Depends(get_db),
) -> QueryResponse:
    """Update a query (only allowed for pending queries)"""
    try:
        service = QueryService(db)
        query = await service.update_query(query_id, update_data)

        if not query:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Query not found"
            )

        return QueryResponse.model_validate(query)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating query {query_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("/{query_id}/status", response_model=QueryStatusResponse)
async def get_query_status(
    query_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> QueryStatusResponse:
    """Get detailed status information for a query"""
    try:
        service = QueryService(db)
        status_info = await service.get_query_status(query_id)

        if not status_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Query not found"
            )

        return QueryStatusResponse(**status_info)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting query status {query_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.post("/{query_id}/route")
async def route_query_to_experts(
    query_id: UUID,
    max_experts: int = QueryParam(default=None, ge=1, le=20),
    location_boost: bool = QueryParam(default=True),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Route a query to matched experts"""
    try:
        service = QueryService(db)
        result = await service.route_query_to_experts(
            query_id=query_id,
            max_experts=max_experts,
            location_boost=location_boost
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error routing query {query_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during query routing"
        )


@router.get("/{query_id}/matches")
async def get_expert_matches(
    query_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get expert matching results for a query"""
    try:
        service = QueryService(db)
        matches = await service.get_expert_matches(query_id)
        
        if matches is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Query not found or no matching results available"
            )
        
        return {
            "query_id": query_id,
            "expert_matches": matches
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting expert matches for query {query_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("/{query_id}/contributions", response_model=ContributionListResponse)
async def get_query_contributions(
    query_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> ContributionListResponse:
    """Get all contributions for a query"""
    try:
        service = QueryService(db)
        contributions = await service.get_query_contributions(query_id)

        return ContributionListResponse(
            contributions=[ContributionResponse.model_validate(c) for c in contributions],
            total=len(contributions)
        )
    except Exception as e:
        logger.error(f"Error getting contributions for query {query_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("/{query_id}/answer", response_model=CompiledAnswerResponse)
async def get_query_answer(
    query_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> CompiledAnswerResponse:
    """Get the compiled answer for a query"""
    try:
        service = QueryService(db)
        answer = await service.get_query_answer(query_id)

        if not answer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No compiled answer found for this query"
            )

        return CompiledAnswerResponse.model_validate(answer)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting answer for query {query_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.post("/{query_id}/synthesize")
async def synthesize_answer(
    query_id: UUID,
    custom_prompt: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Synthesize contributions into a final answer with citations"""
    try:
        service = SynthesisService(db)
        compiled_answer = await service.synthesize_answer(query_id, custom_prompt)
        
        # Get the compiled answer with citations for response
        query_service = QueryService(db)
        answer_with_citations = await query_service.get_query_answer(query_id)
        
        return {
            "success": True,
            "message": "Answer synthesized successfully",
            "answer_id": compiled_answer.id,
            "answer": CompiledAnswerResponse.model_validate(answer_with_citations)
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error synthesizing answer for query {query_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during synthesis"
        )


@router.get("/{query_id}/synthesis/status")
async def get_synthesis_status(
    query_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get the synthesis status for a query"""
    try:
        service = SynthesisService(db)
        status = await service.get_synthesis_status(query_id)
        return {
            "query_id": query_id,
            **status
        }
    except Exception as e:
        logger.error(f"Error getting synthesis status for query {query_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.post("/{query_id}/accept", response_model=AcceptAnswerResponse)
async def accept_answer(
    query_id: UUID,
    accept_data: AcceptAnswerRequest,
    db: AsyncSession = Depends(get_db),
) -> AcceptAnswerResponse:
    """Accept the answer and trigger payment distribution"""
    try:
        service = QueryService(db)
        result = await service.accept_answer(query_id, accept_data)

        return AcceptAnswerResponse(**result)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error accepting answer for query {query_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.post("/{query_id}/contributions", response_model=ContributionResponse, status_code=status.HTTP_201_CREATED)
async def submit_contribution(
    query_id: UUID,
    contribution_data: ContributionCreate,
    db: AsyncSession = Depends(get_db),
) -> ContributionResponse:
    """Submit a contribution/response to a query"""
    try:
        service = QueryService(db)
        contribution = await service.create_contribution(query_id, contribution_data)
        
        if not contribution:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Query not found or not accepting contributions"
            )
            
        return ContributionResponse.model_validate(contribution)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting contribution for query {query_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )
