"""Demo orchestration service for end-to-end GroupChat demonstrations"""

import asyncio
import logging
import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from groupchat.db.models import Contact, Query, QueryStatus, Contribution
from groupchat.services.contacts import ContactService
from groupchat.services.queries import QueryService
from groupchat.services.synthesis import SynthesisService

logger = logging.getLogger(__name__)


class DemoState(Enum):
    """Demo execution states"""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    ERROR = "error"


class DemoMode(Enum):
    """Demo execution modes"""
    FAST = "fast"  # Accelerated timing for quick demos
    REALISTIC = "realistic"  # Production-like timing
    MANUAL = "manual"  # Manual control only


class DemoScenario:
    """Demo scenario definition"""
    
    def __init__(
        self,
        id: str,
        title: str,
        description: str,
        question: str,
        expected_experts: List[Dict[str, Any]],
        sample_responses: List[Dict[str, Any]],
        expected_answer: str,
        timing_profile: Dict[str, int]
    ):
        self.id = id
        self.title = title
        self.description = description
        self.question = question
        self.expected_experts = expected_experts
        self.sample_responses = sample_responses
        self.expected_answer = expected_answer
        self.timing_profile = timing_profile


class DemoOrchestrator:
    """Orchestrates end-to-end demo flows"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.current_demo: Optional[Dict[str, Any]] = None
        self.demo_state = DemoState.IDLE
        self.demo_mode = DemoMode.REALISTIC
        self.progress_callbacks: List[callable] = []
        self.demo_task: Optional[asyncio.Task] = None
        
        # Services
        self.contact_service = ContactService(db)
        self.query_service = QueryService(db)
        self.synthesis_service = SynthesisService(db)
        
        # Initialize demo scenarios
        self.scenarios = self._initialize_scenarios()
    
    def _initialize_scenarios(self) -> Dict[str, DemoScenario]:
        """Initialize predefined demo scenarios"""
        scenarios = {}
        
        # Scenario 1: Technical Question
        scenarios["tech-scaling"] = DemoScenario(
            id="tech-scaling",
            title="Technical Question",
            description="PostgreSQL database scaling best practices",
            question="What are the best practices for scaling PostgreSQL databases?",
            expected_experts=[
                {"name": "Dr. Sarah Chen", "expertise": "Database Architecture", "phone": "+15551234567"},
                {"name": "Mike Rodriguez", "expertise": "DevOps Engineering", "phone": "+15551234568"},
                {"name": "Alex Kumar", "expertise": "Performance Optimization", "phone": "+15551234569"}
            ],
            sample_responses=[
                {
                    "expert": "Dr. Sarah Chen",
                    "response": "For PostgreSQL scaling, focus on three key areas: 1) Vertical scaling with proper hardware sizing, 2) Read replicas for distributing query load, and 3) Partitioning large tables by date or key ranges. Connection pooling with tools like PgBouncer is essential.",
                    "confidence": 0.95,
                    "response_time_minutes": 3.2
                },
                {
                    "expert": "Mike Rodriguez", 
                    "response": "From an ops perspective, implement database monitoring with tools like pg_stat_statements, set up automated failover with Patroni or similar, and use connection pooling. Consider read replicas and potentially sharding for very large datasets.",
                    "confidence": 0.88,
                    "response_time_minutes": 4.1
                },
                {
                    "expert": "Alex Kumar",
                    "response": "Performance optimization is crucial: proper indexing strategies, query optimization, VACUUM and ANALYZE scheduling, and memory configuration tuning (shared_buffers, work_mem). Monitor slow queries and optimize the most impactful ones first.",
                    "confidence": 0.92,
                    "response_time_minutes": 2.8
                }
            ],
            expected_answer="PostgreSQL database scaling requires a multi-faceted approach combining vertical scaling, read replicas, and performance optimization. [@db-expert] recommends focusing on hardware sizing, read replicas, and table partitioning. [@devops-mike] emphasizes the importance of monitoring, automated failover, and connection pooling. [@perf-sarah] highlights query optimization, proper indexing, and memory configuration as key performance factors.",
            timing_profile={
                "routing_seconds": 15,
                "expert_contact_seconds": 30,
                "response_collection_seconds": 180,
                "synthesis_seconds": 45
            }
        )
        
        # Scenario 2: Business Strategy
        scenarios["startup-pmf"] = DemoScenario(
            id="startup-pmf",
            title="Business Strategy",
            description="Startup product-market fit strategies",
            question="How should a startup approach finding product-market fit?",
            expected_experts=[
                {"name": "Lisa Thompson", "expertise": "Product Management", "phone": "+15551234570"},
                {"name": "Alex Patel", "expertise": "Startup Founder", "phone": "+15551234571"},
                {"name": "Tom Wilson", "expertise": "Growth Strategy", "phone": "+15551234572"}
            ],
            sample_responses=[
                {
                    "expert": "Lisa Thompson",
                    "response": "Product-market fit is about building something people desperately want. Start with customer interviews to identify real pain points, build an MVP to test core hypotheses, and iterate based on user feedback. Focus on retention metrics - if people keep coming back, you're on the right track.",
                    "confidence": 0.91,
                    "response_time_minutes": 2.5
                },
                {
                    "expert": "Alex Patel",
                    "response": "As someone who's been through this, PMF feels like pulling versus pushing. Before PMF, everything is hard - customer acquisition, retention, growth. After PMF, customers pull your product into the market. Key indicators: strong word-of-mouth growth, increasing usage frequency, customers getting upset when your product is down.",
                    "confidence": 0.94,
                    "response_time_minutes": 3.7
                },
                {
                    "expert": "Tom Wilson",
                    "response": "From a growth perspective, focus on leading indicators: customer lifetime value, retention cohorts, and organic growth rates. Use frameworks like Sean Ellis's PMF survey (40%+ would be very disappointed if product disappeared). Test different customer segments to find your early adopters.",
                    "confidence": 0.87,
                    "response_time_minutes": 4.2
                }
            ],
            expected_answer="Finding product-market fit requires a systematic approach to understanding customer needs and iterating quickly. [@product-lisa] emphasizes starting with customer interviews and focusing on retention metrics as key indicators. [@founder-alex] describes PMF as the shift from pushing to pulling - when customers naturally want your product. [@growth-tom] recommends tracking leading indicators like LTV and retention cohorts, using frameworks like the Sean Ellis PMF survey.",
            timing_profile={
                "routing_seconds": 20,
                "expert_contact_seconds": 25,
                "response_collection_seconds": 200,
                "synthesis_seconds": 40
            }
        )
        
        # Scenario 3: Creative Problem
        scenarios["remote-collaboration"] = DemoScenario(
            id="remote-collaboration", 
            title="Creative Problem",
            description="Innovative remote team collaboration approaches",
            question="What are innovative approaches to remote team collaboration?",
            expected_experts=[
                {"name": "Emma Chang", "expertise": "UX Design", "phone": "+15551234573"},
                {"name": "David Kim", "expertise": "Remote Work Consulting", "phone": "+15551234574"},
                {"name": "Rachel Green", "expertise": "Team Leadership", "phone": "+15551234575"}
            ],
            sample_responses=[
                {
                    "expert": "Emma Chang",
                    "response": "Design thinking principles apply to remote work too. Create virtual whiteboarding sessions with tools like Miro, establish 'virtual coffee breaks' for informal interaction, and use asynchronous video updates for context-rich communication. Visual collaboration tools are game-changers.",
                    "confidence": 0.89,
                    "response_time_minutes": 3.1
                },
                {
                    "expert": "David Kim",
                    "response": "The future is hybrid-async. Implement 'core collaboration hours' where everyone overlaps, use voice messages for nuanced communication, and create digital team spaces (like virtual offices). Focus on outcomes, not hours. Regular virtual retreats help maintain team bonds.",
                    "confidence": 0.93,
                    "response_time_minutes": 2.9
                },
                {
                    "expert": "Rachel Green",
                    "response": "Leadership in remote teams requires intentional culture building. Use rotating meeting facilitators, create 'show and tell' sessions for project sharing, and implement peer recognition systems. Document everything and make decisions transparent. Regular 1:1s become even more critical.",
                    "confidence": 0.90,
                    "response_time_minutes": 3.8
                }
            ],
            expected_answer="Innovative remote collaboration combines design thinking, hybrid work models, and intentional culture building. [@ux-designer] suggests using visual collaboration tools and asynchronous video updates for richer communication. [@remote-expert] recommends hybrid-async models with core overlap hours and virtual team spaces. [@team-lead] emphasizes intentional culture building through peer recognition and transparent decision-making.",
            timing_profile={
                "routing_seconds": 18,
                "expert_contact_seconds": 35,
                "response_collection_seconds": 190,
                "synthesis_seconds": 50
            }
        )
        
        return scenarios
    
    async def start_demo(
        self,
        scenario_id: str,
        mode: DemoMode = DemoMode.REALISTIC,
        user_phone: str = "+15559999999"
    ) -> Dict[str, Any]:
        """Start a demo session"""
        
        if self.demo_state != DemoState.IDLE:
            raise ValueError("Demo already running. Reset first.")
        
        if scenario_id not in self.scenarios:
            raise ValueError(f"Unknown scenario: {scenario_id}")
        
        scenario = self.scenarios[scenario_id]
        self.demo_mode = mode
        self.demo_state = DemoState.RUNNING
        
        # Initialize demo state
        self.current_demo = {
            "id": str(uuid.uuid4()),
            "scenario": scenario,
            "mode": mode,
            "user_phone": user_phone,
            "start_time": datetime.utcnow(),
            "current_stage": "initializing",
            "progress_percent": 0,
            "query_id": None,
            "expert_contacts": [],
            "contributions": [],
            "stages_completed": [],
            "timing_multiplier": 0.1 if mode == DemoMode.FAST else 1.0
        }
        
        # Start demo execution
        self.demo_task = asyncio.create_task(self._execute_demo())
        
        logger.info(f"Demo started: {scenario_id} in {mode.value} mode")
        
        return {
            "demo_id": self.current_demo["id"],
            "scenario": {
                "id": scenario.id,
                "title": scenario.title,
                "description": scenario.description,
                "question": scenario.question
            },
            "mode": mode.value,
            "status": "started"
        }
    
    async def _execute_demo(self):
        """Execute the demo workflow"""
        
        try:
            scenario = self.current_demo["scenario"]
            timing = scenario.timing_profile
            multiplier = self.current_demo["timing_multiplier"]
            
            # Stage 1: Query Creation and Routing
            await self._update_stage("routing", 10)
            await asyncio.sleep(timing["routing_seconds"] * multiplier)
            
            query_id = await self._create_demo_query()
            self.current_demo["query_id"] = query_id
            
            # Stage 2: Expert Contact
            await self._update_stage("contacting", 25) 
            await asyncio.sleep(timing["expert_contact_seconds"] * multiplier)
            
            await self._setup_demo_experts()
            
            # Stage 3: Response Collection
            await self._update_stage("collecting", 50)
            await asyncio.sleep(timing["response_collection_seconds"] * multiplier)
            
            await self._simulate_expert_responses()
            
            # Stage 4: Synthesis
            await self._update_stage("synthesizing", 80)
            await asyncio.sleep(timing["synthesis_seconds"] * multiplier)
            
            await self._create_demo_answer()
            
            # Stage 5: Completion
            await self._update_stage("completed", 100)
            self.demo_state = DemoState.COMPLETED
            
            logger.info(f"Demo completed successfully: {self.current_demo['id']}")
            
        except Exception as e:
            logger.error(f"Demo execution failed: {e}", exc_info=True)
            self.demo_state = DemoState.ERROR
            await self._update_stage("error", 0)
    
    async def _create_demo_query(self) -> str:
        """Create a demo query in the database"""
        scenario = self.current_demo["scenario"]
        
        # Use existing query service but mark as demo
        query_data = {
            "user_phone": self.current_demo["user_phone"],
            "question_text": scenario.question,
            "max_spend_cents": 500,
            "status": QueryStatus.ROUTING
        }
        
        # This would integrate with your existing QueryService
        # For now, return a mock query ID
        query_id = str(uuid.uuid4())
        logger.info(f"Created demo query: {query_id}")
        return query_id
    
    async def _setup_demo_experts(self):
        """Ensure demo experts exist in the database"""
        scenario = self.current_demo["scenario"]
        
        for expert_data in scenario.expected_experts:
            # Check if expert exists, create if not
            # This would integrate with ContactService
            self.current_demo["expert_contacts"].append({
                "name": expert_data["name"],
                "phone": expert_data["phone"],
                "expertise": expert_data["expertise"],
                "contacted_at": datetime.utcnow()
            })
    
    async def _simulate_expert_responses(self):
        """Simulate expert responses coming in"""
        scenario = self.current_demo["scenario"]
        
        for i, response_data in enumerate(scenario.sample_responses):
            # Stagger responses for realism
            if i > 0:
                await asyncio.sleep(30 * self.current_demo["timing_multiplier"])
            
            contribution = {
                "expert": response_data["expert"],
                "response": response_data["response"],
                "confidence": response_data["confidence"],
                "received_at": datetime.utcnow(),
                "response_time_minutes": response_data["response_time_minutes"]
            }
            
            self.current_demo["contributions"].append(contribution)
            await self._notify_progress()
    
    async def _create_demo_answer(self):
        """Create the synthesized demo answer"""
        scenario = self.current_demo["scenario"]
        
        # Store the expected answer
        self.current_demo["final_answer"] = {
            "content": scenario.expected_answer,
            "confidence_score": 0.91,
            "total_cost_cents": len(scenario.sample_responses) * 75,
            "expert_count": len(scenario.sample_responses)
        }
    
    async def _update_stage(self, stage: str, progress: int):
        """Update demo stage and progress"""
        self.current_demo["current_stage"] = stage
        self.current_demo["progress_percent"] = progress
        self.current_demo["stages_completed"].append({
            "stage": stage,
            "completed_at": datetime.utcnow()
        })
        
        await self._notify_progress()
    
    async def _notify_progress(self):
        """Notify all registered callbacks of progress update"""
        for callback in self.progress_callbacks:
            try:
                await callback(self.get_demo_status())
            except Exception as e:
                logger.error(f"Progress callback failed: {e}")
        
        # Also notify WebSocket clients
        try:
            from groupchat.api.websockets import notify_demo_progress
            await notify_demo_progress(self.get_demo_status())
        except Exception as e:
            logger.error(f"WebSocket notification failed: {e}")
    
    def register_progress_callback(self, callback: callable):
        """Register a callback for demo progress updates"""
        self.progress_callbacks.append(callback)
    
    def get_demo_status(self) -> Dict[str, Any]:
        """Get current demo status"""
        if not self.current_demo:
            return {"status": "idle"}
        
        status = {
            "demo_id": self.current_demo["id"],
            "status": self.demo_state.value,
            "current_stage": self.current_demo["current_stage"],
            "progress_percent": self.current_demo["progress_percent"],
            "scenario_title": self.current_demo["scenario"].title,
            "mode": self.demo_mode.value,
            "query_id": self.current_demo.get("query_id"),
            "experts_contacted": len(self.current_demo["expert_contacts"]),
            "contributions_received": len(self.current_demo["contributions"]),
            "elapsed_time": (datetime.utcnow() - self.current_demo["start_time"]).total_seconds()
        }
        
        if self.current_demo.get("final_answer"):
            status["final_answer"] = self.current_demo["final_answer"]
        
        return status
    
    async def pause_demo(self) -> Dict[str, Any]:
        """Pause the current demo"""
        if self.demo_state == DemoState.RUNNING:
            self.demo_state = DemoState.PAUSED
            if self.demo_task:
                self.demo_task.cancel()
            return {"status": "paused"}
        return {"status": "cannot_pause", "current_state": self.demo_state.value}
    
    async def resume_demo(self) -> Dict[str, Any]:
        """Resume a paused demo"""
        if self.demo_state == DemoState.PAUSED:
            self.demo_state = DemoState.RUNNING
            self.demo_task = asyncio.create_task(self._execute_demo())
            return {"status": "resumed"}
        return {"status": "cannot_resume", "current_state": self.demo_state.value}
    
    async def reset_demo(self) -> Dict[str, Any]:
        """Reset demo to initial state"""
        if self.demo_task:
            self.demo_task.cancel()
        
        self.demo_state = DemoState.IDLE
        self.current_demo = None
        self.demo_task = None
        
        # Clean up demo data from database if needed
        await self._cleanup_demo_data()
        
        logger.info("Demo reset completed")
        return {"status": "reset"}
    
    async def _cleanup_demo_data(self):
        """Clean up demo-specific data from database"""
        # This would clean up demo queries, contributions, etc.
        # Implementation depends on how you want to handle demo data
        pass
    
    def get_available_scenarios(self) -> List[Dict[str, Any]]:
        """Get list of available demo scenarios"""
        return [
            {
                "id": scenario.id,
                "title": scenario.title,
                "description": scenario.description,
                "question": scenario.question,
                "expert_count": len(scenario.expected_experts),
                "estimated_duration": sum(scenario.timing_profile.values())
            }
            for scenario in self.scenarios.values()
        ]