"""Webhook endpoints for external services"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from groupchat.config import settings
from groupchat.db.database import get_db
from groupchat.services.sms import SMSService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/twilio")
async def twilio_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Handle incoming SMS from Twilio"""

    if not settings.enable_sms:
        raise HTTPException(status_code=503, detail="SMS functionality is disabled")

    try:
        # Parse Twilio webhook data
        form_data = await request.form()

        from_number = form_data.get("From")
        to_number = form_data.get("To")
        message_body = form_data.get("Body")
        message_sid = form_data.get("MessageSid")

        if not all([from_number, message_body, message_sid]):
            logger.error("Missing required Twilio webhook parameters")
            raise HTTPException(status_code=400, detail="Invalid webhook data")

        logger.info(f"Received SMS from {from_number}: {message_body[:50]}...")

        # Process the incoming message using SMS service
        sms_service = SMSService(db)
        result = await sms_service.process_incoming_sms(
            from_number=from_number,
            message_body=message_body,
            message_sid=message_sid
        )

        logger.info(f"SMS processed: {result}")

        # Return success response for Twilio
        return {
            "message": "Message processed successfully",
            "status": result.get("status", "processed"),
            "action": result.get("action", "unknown")
        }

    except Exception as e:
        logger.error(f"Error processing Twilio webhook: {e}")
        raise HTTPException(status_code=500, detail="Failed to process webhook")


@router.post("/stripe")
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Handle Stripe webhook events"""

    if not settings.enable_payments:
        raise HTTPException(status_code=503, detail="Payment functionality is disabled")

    try:
        # TODO: Implement Stripe webhook handling
        # 1. Verify webhook signature
        # 2. Process payment events
        # 3. Update ledger

        return {
            "message": "Webhook processed",
            "status": "success",
        }

    except Exception as e:
        logger.error(f"Error processing Stripe webhook: {e}")
        raise HTTPException(status_code=500, detail="Failed to process webhook")
