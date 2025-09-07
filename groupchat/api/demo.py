"""Demo API endpoints for orchestrating end-to-end demonstrations"""

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from groupchat.db.database import get_db
from groupchat.services.demo import DemoMode, DemoOrchestrator

logger = logging.getLogger(__name__)
router = APIRouter(tags=["demo"])

# Global demo orchestrator (in production, this might be managed differently)
_demo_orchestrator: DemoOrchestrator = None


async def get_demo_orchestrator(db: AsyncSession = Depends(get_db)) -> DemoOrchestrator:
    """Get or create demo orchestrator instance"""
    global _demo_orchestrator
    if _demo_orchestrator is None:
        _demo_orchestrator = DemoOrchestrator(db)
    return _demo_orchestrator


class StartDemoRequest(BaseModel):
    """Request to start a demo session"""
    scenario_id: str = Field(..., description="ID of the demo scenario to run")
    mode: str = Field("realistic", description="Demo mode: 'fast', 'realistic', or 'manual'")
    user_phone: str = Field("+15559999999", description="Demo user phone number")


class DemoControlRequest(BaseModel):
    """Request to control demo execution"""
    action: str = Field(..., description="Control action: 'pause', 'resume', 'reset', 'skip'")
    target_stage: str = Field(None, description="Target stage for 'skip' action")


class DemoScenarioResponse(BaseModel):
    """Demo scenario information"""
    id: str
    title: str
    description: str
    question: str
    expert_count: int
    estimated_duration: int


class DemoStatusResponse(BaseModel):
    """Current demo status"""
    demo_id: str = None
    status: str
    current_stage: str = None
    progress_percent: int = 0
    scenario_title: str = None
    mode: str = None
    query_id: str = None
    experts_contacted: int = 0
    contributions_received: int = 0
    elapsed_time: float = 0
    final_answer: Dict[str, Any] = None


@router.get("/scenarios", response_model=List[DemoScenarioResponse])
async def list_demo_scenarios(
    orchestrator: DemoOrchestrator = Depends(get_demo_orchestrator)
) -> List[DemoScenarioResponse]:
    """Get list of available demo scenarios"""
    
    try:
        scenarios = orchestrator.get_available_scenarios()
        return [DemoScenarioResponse(**scenario) for scenario in scenarios]
    
    except Exception as e:
        logger.error(f"Error listing demo scenarios: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve demo scenarios"
        )


@router.post("/start")
async def start_demo(
    request: StartDemoRequest,
    orchestrator: DemoOrchestrator = Depends(get_demo_orchestrator)
) -> Dict[str, Any]:
    """Start a new demo session"""
    
    try:
        # Validate mode
        try:
            mode = DemoMode(request.mode)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid demo mode: {request.mode}. Must be 'fast', 'realistic', or 'manual'"
            )
        
        result = await orchestrator.start_demo(
            scenario_id=request.scenario_id,
            mode=mode,
            user_phone=request.user_phone
        )
        
        return {
            "success": True,
            "data": result
        }
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error starting demo: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start demo"
        )


@router.get("/status", response_model=DemoStatusResponse)
async def get_demo_status(
    orchestrator: DemoOrchestrator = Depends(get_demo_orchestrator)
) -> DemoStatusResponse:
    """Get current demo status"""
    
    try:
        status_data = orchestrator.get_demo_status()
        return DemoStatusResponse(**status_data)
    
    except Exception as e:
        logger.error(f"Error getting demo status: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get demo status"
        )


@router.post("/control")
async def control_demo(
    request: DemoControlRequest,
    orchestrator: DemoOrchestrator = Depends(get_demo_orchestrator)
) -> Dict[str, Any]:
    """Control demo execution (pause, resume, reset, skip)"""
    
    try:
        action = request.action.lower()
        
        if action == "pause":
            result = await orchestrator.pause_demo()
        elif action == "resume":
            result = await orchestrator.resume_demo()
        elif action == "reset":
            result = await orchestrator.reset_demo()
        elif action == "skip":
            # For now, skip is not implemented - would jump to target stage
            result = {"status": "skip_not_implemented"}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid action: {action}. Must be 'pause', 'resume', 'reset', or 'skip'"
            )
        
        return {
            "success": True,
            "data": result
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error controlling demo: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to control demo"
        )


@router.get("/health")
async def demo_health_check() -> Dict[str, Any]:
    """Health check for demo service"""
    return {
        "status": "healthy",
        "service": "demo_orchestration",
        "version": "1.0.0"
    }


@router.delete("/cleanup")
async def cleanup_demo_data(
    orchestrator: DemoOrchestrator = Depends(get_demo_orchestrator)
) -> Dict[str, Any]:
    """Clean up all demo data (admin endpoint)"""
    
    try:
        await orchestrator.reset_demo()
        return {
            "success": True,
            "message": "Demo data cleaned up successfully"
        }
    
    except Exception as e:
        logger.error(f"Error cleaning up demo data: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to clean up demo data"
        )