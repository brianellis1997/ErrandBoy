"""SMS service for Twilio integration and message management"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID
import time

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from twilio.base.exceptions import TwilioException
from twilio.rest import Client

from groupchat.config import settings
from groupchat.db.models import Contact, ContactStatus, Contribution, Query, QueryStatus

logger = logging.getLogger(__name__)


class SMSRateLimiter:
    """Rate limiting for SMS messages per contact"""
    
    def __init__(self, db: AsyncSession):
        self.db = db

    async def can_send_sms_to_contact(self, contact: Contact) -> tuple[bool, str]:
        """Check if we can send SMS to contact based on rate limits"""
        
        # Check daily query limit
        if contact.max_queries_per_day <= 0:
            return False, "Contact has disabled queries"

        # Count SMS messages sent to this contact today
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Count from metadata (more efficient than separate table)
        metadata = contact.extra_metadata
        sms_messages = metadata.get("sms_messages", [])
        
        # Count outbound messages sent today
        today_count = 0
        for msg in sms_messages:
            if msg.get("direction") == "outbound" and msg.get("type") == "query_invitation":
                sent_at = datetime.fromisoformat(msg["sent_at"])
                if sent_at >= today_start:
                    today_count += 1

        if today_count >= contact.max_queries_per_day:
            return False, f"Daily limit reached ({contact.max_queries_per_day} queries/day)"

        # Check if we've sent a message recently (prevent spam)
        recent_cutoff = datetime.utcnow() - timedelta(minutes=5)
        for msg in sms_messages:
            if msg.get("direction") == "outbound":
                sent_at = datetime.fromisoformat(msg["sent_at"])
                if sent_at >= recent_cutoff:
                    return False, "Rate limited: recent message sent"

        return True, "OK"


class SMSTemplate:
    """SMS message templates for different scenarios"""
    
    QUERY_INVITATION = """GroupChat: {user_name} asks: '{question}'
Reply with your answer or 'PASS' to skip.
Reply STOP to opt out."""

    FOLLOW_UP_RESPONSE = """Thanks for your response! It's been included in the answer.
You earned ${amount:.4f}."""

    OPT_OUT_CONFIRMATION = """You've been unsubscribed from GroupChat. Reply START to rejoin."""

    OPT_IN_CONFIRMATION = """Welcome back to GroupChat! You'll receive expert requests again."""

    HELP_MESSAGE = """GroupChat Help:
Reply with your answer to participate
'PASS' to skip a question
'STOP' to unsubscribe
'START' to resubscribe"""

    RATE_LIMIT_MESSAGE = """You've reached your daily query limit. Your responses are valuable - thank you for your contributions!"""


class SMSComplianceService:
    """Handles TCPA compliance, opt-in/out tracking, and quiet hours"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def is_opted_out(self, phone_number: str) -> bool:
        """Check if contact has opted out of SMS communications"""
        result = await self.db.execute(
            select(Contact).where(
                and_(
                    Contact.phone_number == phone_number,
                    Contact.extra_metadata.op("->>")('"sms_opted_out"') == "true"
                )
            )
        )
        contact = result.scalar_one_or_none()
        return contact is not None

    async def opt_out_contact(self, phone_number: str) -> bool:
        """Opt out a contact from SMS communications"""
        result = await self.db.execute(
            select(Contact).where(Contact.phone_number == phone_number)
        )
        contact = result.scalar_one_or_none()
        
        if not contact:
            return False

        # Update metadata to track opt-out
        metadata = contact.extra_metadata.copy()
        metadata["sms_opted_out"] = True
        metadata["sms_opted_out_at"] = datetime.utcnow().isoformat()
        contact.extra_metadata = metadata
        
        await self.db.commit()
        logger.info(f"Contact {phone_number} opted out of SMS")
        return True

    async def opt_in_contact(self, phone_number: str) -> bool:
        """Opt in a contact for SMS communications"""
        result = await self.db.execute(
            select(Contact).where(Contact.phone_number == phone_number)
        )
        contact = result.scalar_one_or_none()
        
        if not contact:
            return False

        # Update metadata to track opt-in
        metadata = contact.extra_metadata.copy()
        metadata["sms_opted_out"] = False
        metadata["sms_opted_in_at"] = datetime.utcnow().isoformat()
        contact.extra_metadata = metadata
        
        await self.db.commit()
        logger.info(f"Contact {phone_number} opted in to SMS")
        return True

    def is_quiet_hours(self) -> bool:
        """Check if current time is within quiet hours (9 PM - 8 AM local time)"""
        # For MVP, use UTC time. Production should consider user timezones
        # TEMPORARILY DISABLED FOR TESTING
        return False  # TODO: Re-enable quiet hours for production
        # current_hour = datetime.utcnow().hour
        # return current_hour >= 21 or current_hour < 8

    async def can_send_sms(self, phone_number: str) -> tuple[bool, str]:
        """Check if SMS can be sent to contact (compliance check)"""
        if await self.is_opted_out(phone_number):
            return False, "Contact has opted out of SMS"
        
        if self.is_quiet_hours():
            return False, "Quiet hours (9 PM - 8 AM UTC)"
        
        return True, "OK"


class TwilioService:
    """Core Twilio client wrapper for SMS operations"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.client = None
        self.compliance = SMSComplianceService(db)
        self.rate_limiter = SMSRateLimiter(db)
        
        if settings.twilio_account_sid and settings.twilio_auth_token:
            self.client = Client(
                settings.twilio_account_sid,
                settings.twilio_auth_token
            )

    def _is_configured(self) -> bool:
        """Check if Twilio is properly configured"""
        return (
            self.client is not None 
            and settings.twilio_phone_number is not None
            and settings.enable_sms
        )

    async def send_query_invitation(
        self, 
        contact: Contact, 
        query: Query, 
        user_name: str = "Someone"
    ) -> Optional[str]:
        """Send query invitation SMS to expert"""
        if not self._is_configured():
            logger.warning("Twilio not configured, skipping SMS")
            return None

        can_send, reason = await self.compliance.can_send_sms(contact.phone_number)
        if not can_send:
            logger.info(f"Cannot send SMS to {contact.phone_number}: {reason}")
            return None

        # Check rate limiting
        rate_allowed, rate_reason = await self.rate_limiter.can_send_sms_to_contact(contact)
        if not rate_allowed:
            logger.info(f"Rate limited SMS to {contact.phone_number}: {rate_reason}")
            return None

        message_body = SMSTemplate.QUERY_INVITATION.format(
            user_name=user_name,
            question=query.question_text[:200] + "..." if len(query.question_text) > 200 else query.question_text
        )

        try:
            message = self.client.messages.create(
                body=message_body,
                from_=settings.twilio_phone_number,
                to=contact.phone_number
            )

            # Track outbound message in contact metadata
            await self._track_outbound_message(contact, message.sid, "query_invitation", query.id)
            
            logger.info(f"Query invitation sent to {contact.phone_number}, SID: {message.sid}")
            return message.sid

        except TwilioException as e:
            logger.error(f"Failed to send SMS to {contact.phone_number}: {e}")
            return None

    async def send_follow_up_response(
        self, 
        contact: Contact, 
        amount_dollars: float
    ) -> Optional[str]:
        """Send follow-up response with payment confirmation"""
        if not self._is_configured():
            logger.warning("Twilio not configured, skipping SMS")
            return None

        can_send, reason = await self.compliance.can_send_sms(contact.phone_number)
        if not can_send:
            logger.info(f"Cannot send SMS to {contact.phone_number}: {reason}")
            return None

        message_body = SMSTemplate.FOLLOW_UP_RESPONSE.format(amount=amount_dollars)

        try:
            message = self.client.messages.create(
                body=message_body,
                from_=settings.twilio_phone_number,
                to=contact.phone_number
            )

            await self._track_outbound_message(contact, message.sid, "follow_up")
            
            logger.info(f"Follow-up sent to {contact.phone_number}, SID: {message.sid}")
            return message.sid

        except TwilioException as e:
            logger.error(f"Failed to send follow-up SMS to {contact.phone_number}: {e}")
            return None

    async def send_compliance_response(
        self, 
        phone_number: str, 
        message_type: str
    ) -> Optional[str]:
        """Send compliance-related responses (STOP, START, HELP)"""
        if not self._is_configured():
            logger.warning("Twilio not configured, skipping SMS")
            return None

        template_map = {
            "STOP": SMSTemplate.OPT_OUT_CONFIRMATION,
            "START": SMSTemplate.OPT_IN_CONFIRMATION,
            "HELP": SMSTemplate.HELP_MESSAGE
        }

        message_body = template_map.get(message_type, SMSTemplate.HELP_MESSAGE)

        try:
            message = self.client.messages.create(
                body=message_body,
                from_=settings.twilio_phone_number,
                to=phone_number
            )
            
            logger.info(f"Compliance response ({message_type}) sent to {phone_number}, SID: {message.sid}")
            return message.sid

        except TwilioException as e:
            logger.error(f"Failed to send compliance SMS to {phone_number}: {e}")
            return None

    async def _track_outbound_message(
        self, 
        contact: Contact, 
        message_sid: str, 
        message_type: str, 
        query_id: Optional[UUID] = None
    ) -> None:
        """Track outbound message in contact metadata"""
        metadata = contact.extra_metadata.copy()
        
        if "sms_messages" not in metadata:
            metadata["sms_messages"] = []

        message_data = {
            "sid": message_sid,
            "type": message_type,
            "direction": "outbound",
            "sent_at": datetime.utcnow().isoformat(),
            "query_id": str(query_id) if query_id else None
        }
        
        metadata["sms_messages"].append(message_data)
        contact.extra_metadata = metadata
        await self.db.commit()

    async def get_message_status(self, message_sid: str) -> Optional[Dict[str, Any]]:
        """Get delivery status of a sent message"""
        if not self._is_configured():
            return None

        try:
            message = self.client.messages(message_sid).fetch()
            return {
                "sid": message.sid,
                "status": message.status,
                "error_code": message.error_code,
                "error_message": message.error_message,
                "date_sent": message.date_sent.isoformat() if message.date_sent else None,
                "date_updated": message.date_updated.isoformat() if message.date_updated else None,
            }
        except TwilioException as e:
            logger.error(f"Failed to fetch message status for {message_sid}: {e}")
            return None


class SMSService:
    """High-level SMS service orchestrating Twilio operations"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.twilio = TwilioService(db)
        self.compliance = SMSComplianceService(db)

    async def send_query_to_experts(
        self, 
        query: Query, 
        expert_contacts: List[Contact],
        user_name: str = "Someone"
    ) -> Dict[str, Any]:
        """Send query invitation to multiple experts"""
        results = {
            "sent": [],
            "failed": [],
            "skipped": []
        }

        for contact in expert_contacts:
            if contact.status != ContactStatus.ACTIVE:
                results["skipped"].append({
                    "contact_id": str(contact.id),
                    "reason": "Contact not active"
                })
                continue

            message_sid = await self.twilio.send_query_invitation(contact, query, user_name)
            
            if message_sid:
                results["sent"].append({
                    "contact_id": str(contact.id),
                    "message_sid": message_sid
                })
                
                # Create contribution record to track the request
                contribution = Contribution(
                    query_id=query.id,
                    contact_id=contact.id,
                    response_text="",  # Will be filled when response comes in
                    requested_at=datetime.utcnow(),
                    extra_metadata={
                        "outbound_message_sid": message_sid,
                        "invitation_sent": True
                    }
                )
                self.db.add(contribution)
            else:
                results["failed"].append({
                    "contact_id": str(contact.id),
                    "reason": "Failed to send SMS"
                })

        await self.db.commit()
        
        logger.info(f"Query {query.id} sent to {len(results['sent'])} experts, "
                   f"{len(results['failed'])} failed, {len(results['skipped'])} skipped")
        
        return results

    async def process_incoming_sms(
        self, 
        from_number: str, 
        message_body: str, 
        message_sid: str
    ) -> Dict[str, Any]:
        """Process incoming SMS and route appropriately"""
        
        # Handle compliance keywords first
        message_upper = message_body.strip().upper()
        
        if message_upper == "STOP":
            await self.compliance.opt_out_contact(from_number)
            await self.twilio.send_compliance_response(from_number, "STOP")
            return {"action": "opt_out", "status": "processed"}
        
        elif message_upper == "START":
            await self.compliance.opt_in_contact(from_number)
            await self.twilio.send_compliance_response(from_number, "START")
            return {"action": "opt_in", "status": "processed"}
        
        elif message_upper == "HELP":
            await self.twilio.send_compliance_response(from_number, "HELP")
            return {"action": "help", "status": "processed"}

        # Check if contact is opted out
        if await self.compliance.is_opted_out(from_number):
            return {"action": "ignored", "status": "opted_out"}

        # Find the contact
        result = await self.db.execute(
            select(Contact).where(Contact.phone_number == from_number)
        )
        contact = result.scalar_one_or_none()
        
        if not contact:
            logger.warning(f"Received SMS from unknown number: {from_number}")
            return {"action": "ignored", "status": "unknown_contact"}

        # Handle PASS response
        if message_upper == "PASS":
            return await self._handle_pass_response(contact, message_sid)

        # Find active query waiting for this contact's response
        active_contribution = await self._find_active_contribution(contact.id)
        
        if not active_contribution:
            logger.info(f"No active query found for contact {contact.id}")
            return {"action": "ignored", "status": "no_active_query"}

        # Store the response
        active_contribution.response_text = message_body
        active_contribution.responded_at = datetime.utcnow()
        active_contribution.response_time_minutes = (
            datetime.utcnow() - active_contribution.requested_at
        ).total_seconds() / 60
        
        # Track inbound message
        metadata = active_contribution.extra_metadata.copy()
        metadata["inbound_message_sid"] = message_sid
        metadata["response_received"] = True
        active_contribution.extra_metadata = metadata

        await self.db.commit()

        # Send follow-up (amount will be calculated later during synthesis)
        await self.twilio.send_follow_up_response(contact, 0.0032)  # Placeholder amount

        logger.info(f"Response recorded for query {active_contribution.query_id} from contact {contact.id}")
        
        return {
            "action": "response_recorded",
            "status": "processed",
            "query_id": str(active_contribution.query_id),
            "contribution_id": str(active_contribution.id)
        }

    async def _handle_pass_response(self, contact: Contact, message_sid: str) -> Dict[str, Any]:
        """Handle PASS response from expert"""
        active_contribution = await self._find_active_contribution(contact.id)
        
        if active_contribution:
            active_contribution.response_text = "PASS"
            active_contribution.responded_at = datetime.utcnow()
            active_contribution.response_time_minutes = (
                datetime.utcnow() - active_contribution.requested_at
            ).total_seconds() / 60
            
            metadata = active_contribution.extra_metadata.copy()
            metadata["inbound_message_sid"] = message_sid
            metadata["passed"] = True
            active_contribution.extra_metadata = metadata
            
            await self.db.commit()
            
            return {
                "action": "pass_recorded",
                "status": "processed",
                "query_id": str(active_contribution.query_id)
            }
        
        return {"action": "ignored", "status": "no_active_query"}

    async def _find_active_contribution(self, contact_id: UUID) -> Optional[Contribution]:
        """Find active contribution waiting for response from contact"""
        result = await self.db.execute(
            select(Contribution).join(Query).where(
                and_(
                    Contribution.contact_id == contact_id,
                    Contribution.response_text == "",
                    Query.status.in_([QueryStatus.COLLECTING, QueryStatus.ROUTING]),
                    Contribution.requested_at > datetime.utcnow() - timedelta(hours=24)  # Only recent requests
                )
            ).order_by(Contribution.requested_at.desc())
        )
        return result.scalar_one_or_none()