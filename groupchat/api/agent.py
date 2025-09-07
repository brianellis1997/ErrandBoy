"""API endpoints for agent tools and workflow execution"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from groupchat.agent.tools import AgentTools
from groupchat.agent.workflow import GroupChatWorkflow
from groupchat.db.database import get_db

router = APIRouter(tags=["agent"])


class QueryRequest(BaseModel):
    """Request model for processing a query"""
    user_phone: str = Field(..., description="User's phone number")
    question_text: str = Field(..., description="The question to process")
    max_spend_cents: int = Field(500, description="Maximum spend in cents", ge=1, le=10000)


class ContactProfileRequest(BaseModel):
    """Request model for saving contact profile"""
    name: str = Field(..., description="Contact name")
    phone: str = Field(..., description="Contact phone number")
    role: str | None = Field(None, description="Professional role")
    bio: str | None = Field(None, description="Biography")
    email: str | None = Field(None, description="Email address")
    consent: bool = Field(True, description="Consent for communication")


class ExpertiseUpdateRequest(BaseModel):
    """Request model for updating expertise"""
    expertise_summary: str = Field(..., description="Expertise summary")
    tags: list[str] | None = Field(None, description="Expertise tags")


@router.post("/process-query")
async def process_query(
    request: QueryRequest,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Process a complete query through the agent workflow"""
    
    try:
        workflow = GroupChatWorkflow(db)
        
        result = await workflow.process_query(
            user_phone=request.user_phone,
            question_text=request.question_text,
            max_spend_cents=request.max_spend_cents
        )
        
        return {
            "success": result["success"],
            "data": {
                "query_id": result.get("query_id"),
                "final_answer": result.get("final_answer"),
                "confidence_score": result.get("confidence_score", 0.0),
                "experts_contacted": result.get("experts_contacted", 0),
                "contributions_received": result.get("contributions_received", 0),
                "payment_processed": result.get("payment_processed", False),
                "total_payout_cents": result.get("total_payout_cents", 0)
            },
            "error": result.get("error"),
            "workflow_details": result.get("workflow_state") if result["success"] else None
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Workflow execution failed: {str(e)}")


@router.post("/tools/save-contact")
async def save_contact_profile(
    request: ContactProfileRequest,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Save a new contact profile"""
    
    try:
        tools = AgentTools(db)
        
        result = await tools.save_contact_profile(
            name=request.name,
            phone=request.phone,
            role=request.role,
            bio=request.bio,
            email=request.email,
            consent=request.consent
        )
        
        if result.success:
            return {"success": True, "data": result.data}
        else:
            raise HTTPException(status_code=400, detail=result.error)
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save contact: {str(e)}")


@router.put("/tools/contacts/{contact_id}/expertise")
async def update_contact_expertise(
    contact_id: str,
    request: ExpertiseUpdateRequest,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Update contact expertise information"""
    
    try:
        tools = AgentTools(db)
        
        result = await tools.update_expertise(
            contact_id=contact_id,
            expertise_summary=request.expertise_summary,
            tags=request.tags
        )
        
        if result.success:
            return {"success": True, "data": result.data}
        else:
            raise HTTPException(status_code=400, detail=result.error)
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update expertise: {str(e)}")


@router.get("/tools/search-contacts")
async def search_contacts(
    query: str,
    limit: int = 10,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Search for contacts by expertise"""
    
    try:
        tools = AgentTools(db)
        
        result = await tools.search_contacts(query=query, limit=limit)
        
        if result.success:
            return {"success": True, "data": result.data}
        else:
            raise HTTPException(status_code=400, detail=result.error)
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.post("/tools/queries")
async def create_query(
    request: QueryRequest,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Create a new query (tool-level access)"""
    
    try:
        tools = AgentTools(db)
        
        result = await tools.create_query(
            user_phone=request.user_phone,
            question_text=request.question_text,
            max_spend_cents=request.max_spend_cents
        )
        
        if result.success:
            return {"success": True, "data": result.data}
        else:
            raise HTTPException(status_code=400, detail=result.error)
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create query: {str(e)}")


@router.get("/tools/queries/{query_id}/status")
async def get_query_status(
    query_id: str,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Get query status (tool-level access)"""
    
    try:
        tools = AgentTools(db)
        
        result = await tools.get_query_status(query_id)
        
        if result.success:
            return {"success": True, "data": result.data}
        else:
            raise HTTPException(status_code=404, detail=result.error)
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get query status: {str(e)}")


@router.post("/tools/queries/{query_id}/synthesize")
async def synthesize_answer(
    query_id: str,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Synthesize answer for a query (tool-level access)"""
    
    try:
        tools = AgentTools(db)
        
        result = await tools.synthesize_answer(query_id)
        
        if result.success:
            return {"success": True, "data": result.data}
        else:
            raise HTTPException(status_code=400, detail=result.error)
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to synthesize answer: {str(e)}")


@router.post("/tools/queries/{query_id}/settle")
async def settle_query(
    query_id: str,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Settle a query (synthesis + payment)"""
    
    try:
        tools = AgentTools(db)
        
        result = await tools.settle_query(query_id)
        
        if result.success:
            return {"success": True, "data": result.data}
        else:
            raise HTTPException(status_code=400, detail=result.error)
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to settle query: {str(e)}")


@router.get("/health")
async def agent_health_check() -> dict[str, Any]:
    """Health check for agent system"""
    
    return {
        "status": "healthy",
        "agent_tools": "available",
        "workflow_engine": "ready",
        "timestamp": "2025-09-06T20:30:00Z"
    }