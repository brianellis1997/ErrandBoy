"""Agent tools for LangGraph integration with GroupChat system"""

import logging
import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from groupchat.services.contacts import ContactService
from groupchat.services.ledger import LedgerService
from groupchat.services.matching import ExpertMatchingService
from groupchat.services.queries import QueryService
from groupchat.services.sms import SMSService
from groupchat.services.synthesis import SynthesisService

logger = logging.getLogger(__name__)


class ToolResult(BaseModel):
    """Standard result format for all agent tools"""
    success: bool
    data: Any = None
    error: Optional[str] = None
    tool_name: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class AgentTools:
    """Collection of agent tools for LangGraph integration"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.contact_service = ContactService(db)
        self.query_service = QueryService(db)
        self.matching_service = ExpertMatchingService(db)
        self.sms_service = SMSService(db)
        self.synthesis_service = SynthesisService(db)
        self.ledger_service = LedgerService(db)

    async def save_contact_profile(
        self,
        name: str,
        phone: str,
        role: Optional[str] = None,
        bio: Optional[str] = None,
        email: Optional[str] = None,
        consent: bool = True
    ) -> ToolResult:
        """Save a new contact profile to the system"""
        
        try:
            logger.info(f"Creating contact profile for {name} ({phone})")
            
            # Format phone number (ensure it starts with +)
            formatted_phone = phone
            if not phone.startswith('+'):
                if phone.startswith('1') and len(phone) == 11:
                    formatted_phone = '+' + phone
                elif len(phone) == 10:
                    formatted_phone = '+1' + phone
                else:
                    formatted_phone = '+' + phone
            
            # Create contact data using ContactCreate schema
            from groupchat.schemas.contacts import ContactCreate
            
            contact_data = ContactCreate(
                name=name,
                phone_number=formatted_phone,
                bio=bio or f"{role}" if role else None,
                email=email,
                is_available=True,
                max_queries_per_day=3,  # Default from signup form
                preferred_contact_method="sms",
                extra_metadata={"signup_consent": consent, "professional_role": role}
            )
            
            contact = await self.contact_service.create_contact(contact_data)
            
            return ToolResult(
                success=True,
                data={
                    "contact_id": str(contact.id),
                    "name": contact.name,
                    "phone": contact.phone_number,
                    "status": contact.status.value
                },
                tool_name="save_contact_profile"
            )
            
        except Exception as e:
            logger.error(f"Error saving contact profile: {e}")
            return ToolResult(
                success=False,
                error=str(e),
                tool_name="save_contact_profile"
            )

    async def update_expertise(
        self,
        contact_id: str,
        expertise_summary: str,
        tags: Optional[list[str]] = None
    ) -> ToolResult:
        """Update contact expertise information"""
        
        try:
            logger.info(f"Updating expertise for contact {contact_id}")
            
            contact_uuid = uuid.UUID(contact_id)
            
            # Update expertise
            await self.contact_service.update_expertise(
                contact_id=contact_uuid,
                expertise_summary=expertise_summary,
                expertise_tags=tags or []
            )
            
            return ToolResult(
                success=True,
                data={
                    "contact_id": contact_id,
                    "expertise_updated": True,
                    "expertise_summary": expertise_summary,
                    "tags": tags
                },
                tool_name="update_expertise"
            )
            
        except Exception as e:
            logger.error(f"Error updating expertise: {e}")
            return ToolResult(
                success=False,
                error=str(e),
                tool_name="update_expertise"
            )

    async def search_contacts(
        self,
        query: str,
        limit: int = 10
    ) -> ToolResult:
        """Search for contacts by expertise or name"""
        
        try:
            logger.info(f"Searching contacts for query: {query}")
            
            # Use the contact service to search for contacts
            contacts, total = await self.contact_service.search_contacts(
                query=query,
                skip=0,
                limit=limit
            )
            
            results = []
            for contact in contacts:
                results.append({
                    "contact_id": str(contact.id),
                    "name": contact.name,
                    "phone": contact.phone_number,
                    "expertise_summary": contact.expertise_summary,
                    "trust_score": contact.trust_score,
                    "match_score": 0.8  # Default match score
                })
            
            return ToolResult(
                success=True,
                data={
                    "query": query,
                    "results": results,
                    "count": len(results)
                },
                tool_name="search_contacts"
            )
            
        except Exception as e:
            logger.error(f"Error searching contacts: {e}")
            return ToolResult(
                success=False,
                error=str(e),
                tool_name="search_contacts"
            )

    async def create_query(
        self,
        user_phone: str,
        question_text: str,
        max_spend_cents: int = 500,
        max_experts: int = 5,
        min_experts: int = 3
    ) -> ToolResult:
        """Create a new query in the system"""
        
        try:
            logger.info(f"Creating query from {user_phone}: {question_text[:50]}...")
            
            from groupchat.schemas.queries import QueryCreate
            
            query_data = QueryCreate(
                user_phone=user_phone,
                question_text=question_text,
                max_spend_cents=max_spend_cents,
                max_experts=max_experts,
                min_experts=min_experts,
                timeout_minutes=30
            )
            
            query = await self.query_service.create_query(query_data)
            
            return ToolResult(
                success=True,
                data={
                    "query_id": str(query.id),
                    "user_phone": query.user_phone,
                    "question_text": query.question_text,
                    "status": query.status.value,
                    "max_spend_cents": query.total_cost_cents
                },
                tool_name="create_query"
            )
            
        except Exception as e:
            logger.error(f"Error creating query: {e}")
            return ToolResult(
                success=False,
                error=str(e),
                tool_name="create_query"
            )

    async def get_query_status(self, query_id: str) -> ToolResult:
        """Get current status of a query"""
        
        try:
            logger.info(f"Getting status for query {query_id}")
            
            query_uuid = uuid.UUID(query_id)
            status = await self.query_service.get_query_status(query_uuid)
            
            if not status:
                return ToolResult(
                    success=False,
                    error="Query not found",
                    tool_name="get_query_status"
                )
            
            return ToolResult(
                success=True,
                data=status,
                tool_name="get_query_status"
            )
            
        except Exception as e:
            logger.error(f"Error getting query status: {e}")
            return ToolResult(
                success=False,
                error=str(e),
                tool_name="get_query_status"
            )

    async def match_experts(
        self,
        query_id: str,
        limit: int = 5
    ) -> ToolResult:
        """Find and match experts for a query"""
        
        try:
            logger.info(f"Matching experts for query {query_id}")
            
            query_uuid = uuid.UUID(query_id)
            
            # Route the query to experts
            result = await self.query_service.route_query_to_experts(query_uuid, max_experts=limit)
            
            return ToolResult(
                success=True,
                data={
                    "query_id": query_id,
                    "experts_matched": result.get("experts_matched", 0),
                    "routing_result": result
                },
                tool_name="match_experts"
            )
            
        except Exception as e:
            logger.error(f"Error matching experts: {e}")
            return ToolResult(
                success=False,
                error=str(e),
                tool_name="match_experts"
            )

    async def send_query_to_experts(
        self,
        query_id: str,
        enable_sms: bool = False
    ) -> ToolResult:
        """Send query notifications to matched experts via SMS (if enabled)"""
        
        try:
            from groupchat.config import settings
            
            logger.info(f"Sending query {query_id} to experts (SMS enabled: {enable_sms and settings.enable_real_sms})")
            
            query_uuid = uuid.UUID(query_id)
            
            # Get the query and its matched experts
            query = await self.query_service.get_query(query_uuid)
            if not query:
                return ToolResult(
                    success=False,
                    error="Query not found",
                    tool_name="send_query_to_experts"
                )
            
            # Check if SMS should be sent based on config and request
            should_send_sms = enable_sms and settings.enable_real_sms
            
            if should_send_sms:
                # Get matched experts from query metadata
                from groupchat.services.matching import ExpertMatchingService
                from groupchat.schemas.matching import MatchingRequest
                
                matching_service = ExpertMatchingService(self.db)
                request = MatchingRequest(
                    query_id=query_uuid,
                    limit=query.max_experts,
                    location_boost=True,
                    exclude_recent=True,
                    wave_size=3
                )
                
                # Get expert matches
                matching_result = await matching_service.match_experts(query, request)
                matched_contacts = [match.contact for match in matching_result.matches]
                
                if matched_contacts:
                    # Send SMS notifications to matched experts
                    sms_result = await self.sms_service.send_query_to_experts(
                        query=query,
                        expert_contacts=matched_contacts,
                        user_name="User"  # Could be enhanced to get actual user name
                    )
                    
                    logger.info(f"SMS outreach completed: {len(sms_result['sent'])} sent, "
                               f"{len(sms_result['failed'])} failed, {len(sms_result['skipped'])} skipped")
                    
                    return ToolResult(
                        success=True,
                        data={
                            "query_id": query_id,
                            "sms_enabled": True,
                            "experts_contacted": len(matched_contacts),
                            "sms_sent": len(sms_result['sent']),
                            "sms_failed": len(sms_result['failed']),
                            "sms_skipped": len(sms_result['skipped']),
                            "sms_details": sms_result
                        },
                        tool_name="send_query_to_experts"
                    )
                else:
                    return ToolResult(
                        success=True,
                        data={
                            "query_id": query_id,
                            "sms_enabled": True,
                            "experts_contacted": 0,
                            "message": "No experts found to contact"
                        },
                        tool_name="send_query_to_experts"
                    )
            else:
                return ToolResult(
                    success=True,
                    data={
                        "query_id": query_id,
                        "sms_enabled": False,
                        "message": "SMS notifications disabled - demo mode or SMS not configured"
                    },
                    tool_name="send_query_to_experts"
                )
            
        except Exception as e:
            logger.error(f"Error sending query to experts: {e}")
            return ToolResult(
                success=False,
                error=str(e),
                tool_name="send_query_to_experts"
            )

    async def send_sms(
        self,
        contact_id: str,
        message: str
    ) -> ToolResult:
        """Send SMS to a contact"""
        
        try:
            logger.info(f"Sending SMS to contact {contact_id}")
            
            contact_uuid = uuid.UUID(contact_id)
            
            # Get contact details
            contact = await self.contact_service.get_contact(contact_uuid)
            if not contact:
                return ToolResult(
                    success=False,
                    error="Contact not found",
                    tool_name="send_sms"
                )
            
            # Send SMS
            result = await self.sms_service.send_sms(
                to_number=contact.phone_number,
                message=message
            )
            
            return ToolResult(
                success=result["success"],
                data={
                    "contact_id": contact_id,
                    "phone": contact.phone_number,
                    "message_sent": result["success"],
                    "sms_result": result
                },
                error=result.get("error"),
                tool_name="send_sms"
            )
            
        except Exception as e:
            logger.error(f"Error sending SMS: {e}")
            return ToolResult(
                success=False,
                error=str(e),
                tool_name="send_sms"
            )

    async def record_contribution(
        self,
        query_id: str,
        contact_id: str,
        response_text: str,
        confidence_score: float = 1.0
    ) -> ToolResult:
        """Record a contribution from an expert"""
        
        try:
            logger.info(f"Recording contribution for query {query_id} from contact {contact_id}")
            
            query_uuid = uuid.UUID(query_id)
            contact_uuid = uuid.UUID(contact_id)
            
            contribution_data = {
                "query_id": query_uuid,
                "contact_id": contact_uuid,
                "response_text": response_text,
                "confidence_score": confidence_score,
                "responded_at": datetime.utcnow()
            }
            
            contribution = await self.query_service.record_contribution(contribution_data)
            
            return ToolResult(
                success=True,
                data={
                    "contribution_id": str(contribution.id),
                    "query_id": query_id,
                    "contact_id": contact_id,
                    "response_length": len(response_text),
                    "confidence_score": confidence_score
                },
                tool_name="record_contribution"
            )
            
        except Exception as e:
            logger.error(f"Error recording contribution: {e}")
            return ToolResult(
                success=False,
                error=str(e),
                tool_name="record_contribution"
            )

    async def synthesize_answer(self, query_id: str) -> ToolResult:
        """Synthesize contributions into a final answer"""
        
        try:
            logger.info(f"Synthesizing answer for query {query_id}")
            
            query_uuid = uuid.UUID(query_id)
            
            compiled_answer = await self.synthesis_service.synthesize_answer(query_uuid)
            
            return ToolResult(
                success=True,
                data={
                    "query_id": query_id,
                    "answer_id": str(compiled_answer.id),
                    "final_answer": compiled_answer.final_answer,
                    "summary": compiled_answer.summary,
                    "confidence_score": compiled_answer.confidence_score,
                    "citation_count": len(compiled_answer.citations) if compiled_answer.citations else 0
                },
                tool_name="synthesize_answer"
            )
            
        except Exception as e:
            logger.error(f"Error synthesizing answer: {e}")
            return ToolResult(
                success=False,
                error=str(e),
                tool_name="synthesize_answer"
            )

    async def calculate_payments(self, query_id: str) -> ToolResult:
        """Calculate payment splits for a completed query"""
        
        try:
            logger.info(f"Calculating payments for query {query_id}")
            
            query_uuid = uuid.UUID(query_id)
            
            # Get the compiled answer
            query = await self.query_service.get_query(query_uuid)
            if not query or not query.compiled_answer:
                return ToolResult(
                    success=False,
                    error="Query not found or not synthesized",
                    tool_name="calculate_payments"
                )
            
            # Process payment
            result = await self.ledger_service.process_query_payment(
                query_id=query_uuid,
                compiled_answer_id=query.compiled_answer.id
            )
            
            return ToolResult(
                success=result["success"],
                data=result,
                error=result.get("message") if not result["success"] else None,
                tool_name="calculate_payments"
            )
            
        except Exception as e:
            logger.error(f"Error calculating payments: {e}")
            return ToolResult(
                success=False,
                error=str(e),
                tool_name="calculate_payments"
            )

    async def settle_query(self, query_id: str) -> ToolResult:
        """Complete final settlement of a query (combining synthesis + payment)"""
        
        try:
            logger.info(f"Settling query {query_id}")
            
            # First synthesize the answer
            synthesis_result = await self.synthesize_answer(query_id)
            if not synthesis_result.success:
                return ToolResult(
                    success=False,
                    error=f"Synthesis failed: {synthesis_result.error}",
                    tool_name="settle_query"
                )
            
            # Then calculate payments (this is automatically done by synthesis service)
            # Just verify the payment was processed
            payment_result = await self.calculate_payments(query_id)
            
            return ToolResult(
                success=True,
                data={
                    "query_id": query_id,
                    "synthesis_result": synthesis_result.data,
                    "payment_result": payment_result.data if payment_result.success else None,
                    "settlement_complete": True
                },
                tool_name="settle_query"
            )
            
        except Exception as e:
            logger.error(f"Error settling query: {e}")
            return ToolResult(
                success=False,
                error=str(e),
                tool_name="settle_query"
            )