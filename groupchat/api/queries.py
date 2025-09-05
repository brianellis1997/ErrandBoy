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
    ContributionListResponse,
    QueryCreate,
    QueryDetailResponse,
    QueryListResponse,
    QueryResponse,
    QueryStatusResponse,
    QueryUpdate,
)
from groupchat.services.queries import QueryService

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
        return QueryResponse.model_validate(query)
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
