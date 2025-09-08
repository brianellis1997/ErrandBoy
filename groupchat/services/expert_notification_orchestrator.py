"""Expert notification orchestration service - coordinates SMS, email, and real-time notifications"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from groupchat.api.websockets import notify_expert_query_invitation, is_expert_online
from groupchat.config import settings
from groupchat.db.models import (
    Contact,
    ContactStatus,
    ExpertNotificationPreferences,
    NotificationSchedule,
    NotificationUrgency,
    Query as QueryModel,
)
from groupchat.schemas.expert_notifications import NotificationDeliveryStatus
from groupchat.services.email_notifications import EmailNotificationService
from groupchat.services.sms import TwilioService

logger = logging.getLogger(__name__)


class ExpertNotificationOrchestrator:
    """
    Coordinates multi-channel notifications to experts for new queries.
    
    This service determines the best notification strategy for each expert based on:
    - Expert notification preferences
    - Query urgency level
    - Expert availability status
    - Time zones and quiet hours
    - Rate limiting constraints
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.twilio_service = TwilioService(db)
        self.email_service = EmailNotificationService()
    
    async def notify_experts_for_query(
        self,
        query: QueryModel,
        expert_contact_ids: List[UUID],
        urgency: NotificationUrgency = NotificationUrgency.NORMAL
    ) -> Dict[str, any]:
        """
        Send notifications to multiple experts for a new query.
        
        Args:
            query: The query needing expert responses
            expert_contact_ids: List of expert contact IDs to notify
            urgency: Query urgency level affecting notification strategy
            
        Returns:
            Summary of notification delivery results
        """
        logger.info(f"Starting expert notifications for query {query.id} to {len(expert_contact_ids)} experts")
        
        results = {
            "query_id": str(query.id),
            "urgency": urgency.value,
            "experts_notified": 0,
            "notification_channels_used": set(),
            "delivery_summary": {
                "real_time": {"sent": 0, "failed": 0},
                "sms": {"sent": 0, "failed": 0, "skipped": 0},
                "email": {"sent": 0, "failed": 0, "skipped": 0}
            },
            "expert_details": []
        }
        
        # Calculate estimated payout per expert
        estimated_payout_cents = query.total_cost_cents // max(1, len(expert_contact_ids))
        
        for contact_id in expert_contact_ids:
            try:
                expert_result = await self._notify_single_expert(
                    query, contact_id, urgency, estimated_payout_cents
                )
                
                results["expert_details"].append(expert_result)
                
                if expert_result["notified"]:
                    results["experts_notified"] += 1
                
                # Aggregate channel results
                for channel, channel_result in expert_result["channels"].items():
                    if channel_result["sent"]:
                        results["delivery_summary"][channel]["sent"] += 1
                        results["notification_channels_used"].add(channel)
                    elif channel_result["failed"]:
                        results["delivery_summary"][channel]["failed"] += 1
                    else:
                        results["delivery_summary"][channel]["skipped"] += 1
                
            except Exception as e:
                logger.error(f"Error notifying expert {contact_id} for query {query.id}: {e}")
                results["expert_details"].append({
                    "contact_id": str(contact_id),
                    "notified": False,
                    "error": str(e),
                    "channels": {}
                })
        
        # Convert set to list for JSON serialization
        results["notification_channels_used"] = list(results["notification_channels_used"])
        
        logger.info(f"Expert notification complete for query {query.id}: "
                   f"{results['experts_notified']}/{len(expert_contact_ids)} experts notified "
                   f"via {len(results['notification_channels_used'])} channels")
        
        return results
    
    async def _notify_single_expert(
        self,
        query: QueryModel,
        contact_id: UUID,
        urgency: NotificationUrgency,
        estimated_payout_cents: int
    ) -> Dict[str, any]:
        """Notify a single expert via appropriate channels"""
        
        # Get expert contact and preferences
        expert_data = await self._get_expert_notification_data(contact_id)
        
        if not expert_data["contact"]:
            return {
                "contact_id": str(contact_id),
                "notified": False,
                "reason": "Expert not found",
                "channels": {}
            }
        
        contact = expert_data["contact"]
        preferences = expert_data["preferences"]
        
        # Check if expert is available and eligible
        eligibility_check = await self._check_expert_eligibility(
            contact, preferences, urgency
        )
        
        if not eligibility_check["eligible"]:
            return {
                "contact_id": str(contact_id),
                "expert_name": contact.name,
                "notified": False,
                "reason": eligibility_check["reason"],
                "channels": {}
            }
        
        # Determine notification channels based on preferences and urgency
        channels_to_use = self._determine_notification_channels(
            preferences, urgency, contact
        )
        
        # Send notifications via each channel
        channel_results = {}
        notification_sent = False
        
        # Real-time WebSocket notification (highest priority)
        if "real_time" in channels_to_use:
            channel_results["real_time"] = await self._send_realtime_notification(
                contact_id, query, urgency, estimated_payout_cents
            )
            if channel_results["real_time"]["sent"]:
                notification_sent = True
        
        # SMS notification
        if "sms" in channels_to_use:
            channel_results["sms"] = await self._send_sms_notification(
                contact, query, estimated_payout_cents
            )
            if channel_results["sms"]["sent"]:
                notification_sent = True
        
        # Email notification
        if "email" in channels_to_use:
            channel_results["email"] = await self._send_email_notification(
                contact_id, query, urgency, estimated_payout_cents
            )
            if channel_results["email"]["sent"]:
                notification_sent = True
        
        return {
            "contact_id": str(contact_id),
            "expert_name": contact.name,
            "notified": notification_sent,
            "channels_used": [ch for ch, result in channel_results.items() if result.get("sent", False)],
            "channels": channel_results
        }
    
    async def _get_expert_notification_data(self, contact_id: UUID) -> Dict[str, any]:
        """Get expert contact and notification preferences"""
        
        # Get contact
        result = await self.db.execute(
            select(Contact).where(
                and_(
                    Contact.id == contact_id,
                    Contact.status == ContactStatus.ACTIVE
                )
            )
        )
        contact = result.scalar_one_or_none()
        
        if not contact:
            return {"contact": None, "preferences": None}
        
        # Get or create notification preferences
        prefs_result = await self.db.execute(
            select(ExpertNotificationPreferences).where(
                ExpertNotificationPreferences.contact_id == contact_id
            )
        )
        preferences = prefs_result.scalar_one_or_none()
        
        if not preferences:
            # Create default preferences
            preferences = ExpertNotificationPreferences(contact_id=contact_id)
            self.db.add(preferences)
            await self.db.commit()
            await self.db.refresh(preferences)
        
        return {"contact": contact, "preferences": preferences}
    
    async def _check_expert_eligibility(
        self,
        contact: Contact,
        preferences: ExpertNotificationPreferences,
        urgency: NotificationUrgency
    ) -> Dict[str, any]:
        """Check if expert is eligible to receive notifications"""
        
        # Check if expert is available
        if not contact.is_available:
            return {"eligible": False, "reason": "Expert is unavailable"}
        
        # Check urgency filter
        urgency_levels = {
            NotificationUrgency.LOW: 0,
            NotificationUrgency.NORMAL: 1,
            NotificationUrgency.HIGH: 2,
            NotificationUrgency.URGENT: 3
        }
        
        if urgency_levels.get(urgency, 1) < urgency_levels.get(preferences.urgency_filter, 0):
            return {"eligible": False, "reason": f"Query urgency ({urgency.value}) below expert filter ({preferences.urgency_filter.value})"}
        
        # Check quiet hours
        if preferences.quiet_hours_enabled and self._is_quiet_hours(preferences):
            # Allow urgent notifications through quiet hours
            if urgency != NotificationUrgency.URGENT:
                return {"eligible": False, "reason": "Currently in quiet hours"}
        
        # Check daily notification limits
        if await self._exceeds_daily_limits(contact.id, preferences):
            return {"eligible": False, "reason": "Daily notification limit reached"}
        
        return {"eligible": True, "reason": "Eligible for notifications"}
    
    def _determine_notification_channels(
        self,
        preferences: ExpertNotificationPreferences,
        urgency: NotificationUrgency,
        contact: Contact
    ) -> Set[str]:
        """Determine which notification channels to use"""
        
        channels = set()
        
        # Real-time notifications (WebSocket) - always try if expert is online
        channels.add("real_time")
        
        # For urgent notifications, use all enabled channels
        if urgency == NotificationUrgency.URGENT:
            if preferences.sms_enabled and contact.phone_number:
                channels.add("sms")
            if preferences.email_enabled and contact.email:
                channels.add("email")
        
        # For normal notifications, respect scheduling preferences
        elif preferences.notification_schedule == NotificationSchedule.IMMEDIATE:
            if preferences.sms_enabled and contact.phone_number:
                channels.add("sms")
            if preferences.email_enabled and contact.email:
                channels.add("email")
        
        # Batched notifications would be handled by a separate background job
        # For now, treat as immediate for high/normal urgency
        elif urgency in [NotificationUrgency.HIGH, NotificationUrgency.NORMAL]:
            if preferences.email_enabled and contact.email:
                channels.add("email")
        
        return channels
    
    async def _send_realtime_notification(
        self,
        contact_id: UUID,
        query: QueryModel,
        urgency: NotificationUrgency,
        estimated_payout_cents: int
    ) -> Dict[str, any]:
        """Send real-time WebSocket notification"""
        
        try:
            # Check if expert is online
            is_online = await is_expert_online(str(contact_id))
            
            if not is_online:
                return {"sent": False, "failed": False, "reason": "Expert not online"}
            
            # Send WebSocket notification
            await notify_expert_query_invitation(str(contact_id), {
                "query_id": str(query.id),
                "question": query.question_text,
                "urgency": urgency.value,
                "estimated_payout_cents": estimated_payout_cents,
                "timeout_minutes": query.timeout_minutes,
                "user_phone": query.user_phone
            })
            
            return {"sent": True, "failed": False, "channel": "websocket"}
            
        except Exception as e:
            logger.error(f"Failed to send real-time notification to {contact_id}: {e}")
            return {"sent": False, "failed": True, "error": str(e)}
    
    async def _send_sms_notification(
        self,
        contact: Contact,
        query: QueryModel,
        estimated_payout_cents: int
    ) -> Dict[str, any]:
        """Send SMS notification"""
        
        try:
            message_sid = await self.twilio_service.send_query_invitation(
                contact, query, "User"  # TODO: Get actual user name
            )
            
            if message_sid:
                return {"sent": True, "failed": False, "message_sid": message_sid}
            else:
                return {"sent": False, "failed": False, "reason": "SMS sending skipped (rate limited or opted out)"}
                
        except Exception as e:
            logger.error(f"Failed to send SMS notification to {contact.phone_number}: {e}")
            return {"sent": False, "failed": True, "error": str(e)}
    
    async def _send_email_notification(
        self,
        contact_id: UUID,
        query: QueryModel,
        urgency: NotificationUrgency,
        estimated_payout_cents: int
    ) -> Dict[str, any]:
        """Send email notification"""
        
        try:
            success = await self.email_service.send_query_invitation_email(
                contact_id, query, estimated_payout_cents, urgency, self.db
            )
            
            if success:
                return {"sent": True, "failed": False}
            else:
                return {"sent": False, "failed": False, "reason": "Email sending skipped (not configured or opted out)"}
                
        except Exception as e:
            logger.error(f"Failed to send email notification to {contact_id}: {e}")
            return {"sent": False, "failed": True, "error": str(e)}
    
    def _is_quiet_hours(self, preferences: ExpertNotificationPreferences) -> bool:
        """Check if current time is within expert's quiet hours"""
        # This is a simplified implementation - production would need timezone handling
        current_hour = datetime.utcnow().hour
        
        quiet_start = int(preferences.quiet_hours_start.split(":")[0])
        quiet_end = int(preferences.quiet_hours_end.split(":")[0])
        
        if quiet_start <= quiet_end:
            # Normal range (e.g., 22:00 to 08:00 next day)
            return current_hour >= quiet_start or current_hour < quiet_end
        else:
            # Crosses midnight (e.g., 08:00 to 22:00)
            return quiet_start <= current_hour < quiet_end
    
    async def _exceeds_daily_limits(
        self,
        contact_id: UUID,
        preferences: ExpertNotificationPreferences
    ) -> bool:
        """Check if expert has exceeded daily notification limits"""
        # This would require tracking notification history in the database
        # For now, return False - this would be implemented with proper tracking
        return False
    
    async def get_notification_status(
        self,
        query_id: UUID,
        contact_id: Optional[UUID] = None
    ) -> List[NotificationDeliveryStatus]:
        """Get notification delivery status for a query"""
        # This would query notification history from database
        # Placeholder implementation
        return []


# Helper function for use in other services
async def notify_experts_for_new_query(
    db: AsyncSession,
    query: QueryModel,
    expert_contact_ids: List[UUID],
    urgency: NotificationUrgency = NotificationUrgency.NORMAL
) -> Dict[str, any]:
    """
    Convenience function to notify experts about a new query.
    
    This should be called after query matching to notify selected experts.
    """
    orchestrator = ExpertNotificationOrchestrator(db)
    return await orchestrator.notify_experts_for_query(
        query, expert_contact_ids, urgency
    )