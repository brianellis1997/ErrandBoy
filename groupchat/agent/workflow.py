"""LangGraph workflow for GroupChat query processing"""

import logging
from typing import Any, Literal, Optional, TypedDict

from langgraph.graph import StateGraph, END
from sqlalchemy.ext.asyncio import AsyncSession

from groupchat.agent.tools import AgentTools

logger = logging.getLogger(__name__)


class QueryState(TypedDict):
    """State object for the query processing workflow"""
    # Input
    user_phone: str
    question_text: str
    max_spend_cents: int
    
    # Processing state
    query_id: Optional[str]
    current_step: str
    error: Optional[str]
    
    # Expert matching
    matched_experts: list[dict[str, Any]]
    experts_contacted: int
    
    # Response collection
    contributions: list[dict[str, Any]]
    contributions_received: int
    
    # Synthesis
    final_answer: Optional[str]
    answer_id: Optional[str]
    confidence_score: float
    
    # Payment
    payment_processed: bool
    total_payout_cents: int
    
    # Workflow control
    should_continue: bool
    workflow_complete: bool


class GroupChatWorkflow:
    """LangGraph workflow orchestrating the GroupChat system"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.tools = AgentTools(db)
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow"""
        
        workflow = StateGraph(QueryState)
        
        # Add nodes
        workflow.add_node("parse_query", self.parse_query_node)
        workflow.add_node("match_experts", self.match_experts_node)
        workflow.add_node("send_outreach", self.outreach_node)
        workflow.add_node("collect_responses", self.collect_node)
        workflow.add_node("synthesize", self.synthesis_node)
        workflow.add_node("distribute_payment", self.payment_node)
        workflow.add_node("finalize", self.finalize_node)
        
        # Add edges
        workflow.add_edge("parse_query", "match_experts")
        workflow.add_edge("match_experts", "send_outreach")
        workflow.add_edge("send_outreach", "collect_responses")
        workflow.add_conditional_edges(
            "collect_responses",
            self.should_synthesize,
            {
                "synthesize": "synthesize",
                "wait": "collect_responses",
                "error": "finalize"
            }
        )
        workflow.add_edge("synthesize", "distribute_payment")
        workflow.add_edge("distribute_payment", "finalize")
        workflow.add_edge("finalize", END)
        
        # Set entry point
        workflow.set_entry_point("parse_query")
        
        return workflow.compile()

    async def parse_query_node(self, state: QueryState) -> QueryState:
        """Parse and validate the incoming query"""
        
        logger.info(f"Parsing query from {state['user_phone']}")
        
        try:
            # Create the query in the system
            result = await self.tools.create_query(
                user_phone=state["user_phone"],
                question_text=state["question_text"],
                max_spend_cents=state["max_spend_cents"]
            )
            
            if result.success:
                state["query_id"] = result.data["query_id"]
                state["current_step"] = "parsed"
                logger.info(f"Query created with ID: {state['query_id']}")
            else:
                state["error"] = f"Failed to create query: {result.error}"
                state["should_continue"] = False
                
        except Exception as e:
            logger.error(f"Error in parse_query_node: {e}")
            state["error"] = str(e)
            state["should_continue"] = False
            
        return state

    async def match_experts_node(self, state: QueryState) -> QueryState:
        """Find and match relevant experts"""
        
        logger.info(f"Matching experts for query {state['query_id']}")
        
        try:
            # Search for relevant experts
            search_result = await self.tools.search_contacts(
                query=state["question_text"],
                limit=10
            )
            
            if search_result.success:
                state["matched_experts"] = search_result.data["results"]
                state["current_step"] = "experts_matched"
                logger.info(f"Found {len(state['matched_experts'])} potential experts")
            else:
                state["error"] = f"Failed to find experts: {search_result.error}"
                state["should_continue"] = False
                
        except Exception as e:
            logger.error(f"Error in match_experts_node: {e}")
            state["error"] = str(e)
            state["should_continue"] = False
            
        return state

    async def outreach_node(self, state: QueryState) -> QueryState:
        """Send outreach messages to selected experts"""
        
        logger.info(f"Sending outreach for query {state['query_id']}")
        
        try:
            experts_contacted = 0
            max_experts = min(5, len(state["matched_experts"]))
            
            # Select top experts and send outreach
            for expert in state["matched_experts"][:max_experts]:
                message = self._create_outreach_message(
                    state["question_text"],
                    expert["name"]
                )
                
                sms_result = await self.tools.send_sms(
                    contact_id=expert["contact_id"],
                    message=message
                )
                
                if sms_result.success:
                    experts_contacted += 1
                    logger.info(f"Contacted expert {expert['name']}")
                else:
                    logger.warning(f"Failed to contact {expert['name']}: {sms_result.error}")
            
            state["experts_contacted"] = experts_contacted
            state["current_step"] = "outreach_sent"
            
            if experts_contacted == 0:
                state["error"] = "No experts could be contacted"
                state["should_continue"] = False
                
        except Exception as e:
            logger.error(f"Error in outreach_node: {e}")
            state["error"] = str(e)
            state["should_continue"] = False
            
        return state

    async def collect_node(self, state: QueryState) -> QueryState:
        """Collect responses from experts"""
        
        logger.info(f"Collecting responses for query {state['query_id']}")
        
        try:
            # Get current query status to see contributions
            status_result = await self.tools.get_query_status(state["query_id"])
            
            if status_result.success:
                contributions_count = status_result.data.get("contributions_received", 0)
                state["contributions_received"] = contributions_count
                state["current_step"] = "collecting_responses"
                
                logger.info(f"Received {contributions_count} contributions so far")
                
                # For demo purposes, we'll simulate having contributions
                # In real implementation, this would check actual contributions
                if contributions_count >= 2:  # Minimum threshold
                    state["should_continue"] = True
                else:
                    # In real scenario, this would wait for more responses
                    # For demo, we'll proceed with what we have
                    state["should_continue"] = True
            else:
                state["error"] = f"Failed to get query status: {status_result.error}"
                state["should_continue"] = False
                
        except Exception as e:
            logger.error(f"Error in collect_node: {e}")
            state["error"] = str(e)
            state["should_continue"] = False
            
        return state

    async def synthesis_node(self, state: QueryState) -> QueryState:
        """Synthesize expert contributions into final answer"""
        
        logger.info(f"Synthesizing answer for query {state['query_id']}")
        
        try:
            result = await self.tools.synthesize_answer(state["query_id"])
            
            if result.success:
                state["final_answer"] = result.data["final_answer"]
                state["answer_id"] = result.data["answer_id"]
                state["confidence_score"] = result.data["confidence_score"]
                state["current_step"] = "synthesized"
                logger.info("Answer synthesized successfully")
            else:
                state["error"] = f"Failed to synthesize answer: {result.error}"
                state["should_continue"] = False
                
        except Exception as e:
            logger.error(f"Error in synthesis_node: {e}")
            state["error"] = str(e)
            state["should_continue"] = False
            
        return state

    async def payment_node(self, state: QueryState) -> QueryState:
        """Process payments to contributors"""
        
        logger.info(f"Processing payments for query {state['query_id']}")
        
        try:
            result = await self.tools.calculate_payments(state["query_id"])
            
            if result.success:
                state["payment_processed"] = True
                state["total_payout_cents"] = result.data.get("total_amount_cents", 0)
                state["current_step"] = "payment_processed"
                logger.info(f"Payments processed: ${state['total_payout_cents']/100:.4f}")
            else:
                # Payment failure shouldn't stop the workflow
                logger.warning(f"Payment processing failed: {result.error}")
                state["payment_processed"] = False
                state["total_payout_cents"] = 0
                
        except Exception as e:
            logger.error(f"Error in payment_node: {e}")
            state["payment_processed"] = False
            state["total_payout_cents"] = 0
            
        return state

    async def finalize_node(self, state: QueryState) -> QueryState:
        """Finalize the workflow and prepare results"""
        
        logger.info(f"Finalizing workflow for query {state['query_id']}")
        
        state["workflow_complete"] = True
        state["current_step"] = "completed"
        
        if state.get("error"):
            logger.error(f"Workflow completed with error: {state['error']}")
        else:
            logger.info("Workflow completed successfully")
            
        return state

    def should_synthesize(self, state: QueryState) -> Literal["synthesize", "wait", "error"]:
        """Decide whether to proceed with synthesis"""
        
        if state.get("error"):
            return "error"
            
        # For demo purposes, proceed if we have any contributions
        # In production, this would check contribution quality and quantity
        if state.get("contributions_received", 0) >= 1:
            return "synthesize"
        else:
            return "wait"

    def _create_outreach_message(self, question: str, expert_name: str) -> str:
        """Create personalized outreach message"""
        
        return f"""Hi {expert_name}! 

A user has asked: "{question[:100]}..."

Your expertise could help provide a valuable answer. Please reply with your insights if you can assist.

Thanks!
- GroupChat Network"""

    async def process_query(
        self,
        user_phone: str,
        question_text: str,
        max_spend_cents: int = 500
    ) -> dict[str, Any]:
        """Process a complete query through the workflow"""
        
        logger.info(f"Starting workflow for query from {user_phone}")
        
        initial_state = QueryState(
            user_phone=user_phone,
            question_text=question_text,
            max_spend_cents=max_spend_cents,
            query_id=None,
            current_step="initializing",
            error=None,
            matched_experts=[],
            experts_contacted=0,
            contributions=[],
            contributions_received=0,
            final_answer=None,
            answer_id=None,
            confidence_score=0.0,
            payment_processed=False,
            total_payout_cents=0,
            should_continue=True,
            workflow_complete=False
        )
        
        try:
            # Execute the workflow
            final_state = await self.graph.ainvoke(initial_state)
            
            return {
                "success": not bool(final_state.get("error")),
                "query_id": final_state.get("query_id"),
                "final_answer": final_state.get("final_answer"),
                "confidence_score": final_state.get("confidence_score", 0.0),
                "experts_contacted": final_state.get("experts_contacted", 0),
                "contributions_received": final_state.get("contributions_received", 0),
                "payment_processed": final_state.get("payment_processed", False),
                "total_payout_cents": final_state.get("total_payout_cents", 0),
                "error": final_state.get("error"),
                "workflow_state": final_state
            }
            
        except Exception as e:
            logger.error(f"Workflow execution failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "query_id": None,
                "final_answer": None
            }