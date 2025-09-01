"""Webhook endpoints for external services"""

import logging
from typing import Dict, Any

from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from groupchat.db.database import get_db
from groupchat.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/twilio")
async def twilio_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, str]:
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
        
        logger.info(f"Received SMS from {from_number}: {message_body[:50]}...")
        
        # TODO: Process the incoming message
        # 1. Find the contact by phone number
        # 2. Match to active query
        # 3. Store as contribution
        # 4. Send acknowledgment
        
        # Return TwiML response
        return {
            "message": "Message received",
            "status": "processed",
        }
        
    except Exception as e:
        logger.error(f"Error processing Twilio webhook: {e}")
        raise HTTPException(status_code=500, detail="Failed to process webhook")


@router.post("/stripe")
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, str]:
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