"""Webhook endpoints for external services"""

import hmac
import hashlib
import json
import logging

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from groupchat.config import settings
from groupchat.db.database import get_db
from groupchat.services.sms import SMSService
from groupchat.services.stripe_connect_service import StripeConnectService

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
        # Get raw request body and headers
        payload = await request.body()
        sig_header = request.headers.get('stripe-signature')
        
        if not sig_header:
            raise HTTPException(status_code=400, detail="Missing Stripe signature")
        
        # Verify webhook signature
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.stripe_webhook_secret
            )
        except ValueError as e:
            logger.error(f"Invalid Stripe webhook payload: {e}")
            raise HTTPException(status_code=400, detail="Invalid payload")
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Invalid Stripe webhook signature: {e}")
            raise HTTPException(status_code=400, detail="Invalid signature")

        logger.info(f"Received Stripe webhook: {event['type']}")

        # Handle different event types
        event_type = event['type']
        
        if event_type.startswith('account.'):
            # Stripe Connect account events
            stripe_service = StripeConnectService(db)
            result = await stripe_service.handle_account_webhook(event)
            logger.info(f"Processed Stripe Connect webhook: {result}")
            
        elif event_type.startswith('payment_intent.'):
            # Payment intent events (for deposits)
            await handle_payment_intent_webhook(event, db)
            
        elif event_type.startswith('transfer.'):
            # Transfer events (for payouts)
            await handle_transfer_webhook(event, db)
            
        else:
            logger.info(f"Unhandled Stripe webhook event type: {event_type}")

        return {
            "message": "Webhook processed successfully",
            "event_type": event_type,
            "status": "success"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing Stripe webhook: {e}")
        raise HTTPException(status_code=500, detail="Failed to process webhook")


@router.post("/plaid")
async def plaid_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Handle Plaid webhook events"""

    try:
        # Get webhook payload
        webhook_data = await request.json()
        
        # Verify webhook (in production, should verify webhook signature)
        webhook_type = webhook_data.get('webhook_type')
        webhook_code = webhook_data.get('webhook_code')
        item_id = webhook_data.get('item_id')
        
        if not all([webhook_type, webhook_code]):
            raise HTTPException(status_code=400, detail="Invalid Plaid webhook data")
            
        logger.info(f"Received Plaid webhook: {webhook_type}.{webhook_code} for item {item_id}")
        
        # Handle different webhook types
        if webhook_type == 'ITEM':
            await handle_plaid_item_webhook(webhook_data, db)
        elif webhook_type == 'TRANSACTIONS':
            await handle_plaid_transactions_webhook(webhook_data, db)
        elif webhook_type == 'AUTH':
            await handle_plaid_auth_webhook(webhook_data, db)
        else:
            logger.info(f"Unhandled Plaid webhook type: {webhook_type}")
            
        return {
            "message": "Plaid webhook processed successfully",
            "webhook_type": webhook_type,
            "webhook_code": webhook_code,
            "status": "success"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing Plaid webhook: {e}")
        raise HTTPException(status_code=500, detail="Failed to process Plaid webhook")


async def handle_payment_intent_webhook(event: dict, db: AsyncSession) -> None:
    """Handle Stripe payment intent webhook events"""
    
    event_type = event['type']
    payment_intent = event['data']['object']
    
    logger.info(f"Processing payment intent webhook: {event_type} - {payment_intent['id']}")
    
    # Update payment intent status in database
    # This would require linking Stripe payment intent IDs to our PaymentIntent records
    # For now, just log the event
    
    if event_type == 'payment_intent.succeeded':
        logger.info(f"Payment intent succeeded: {payment_intent['id']} - ${payment_intent['amount']/100:.2f}")
    elif event_type == 'payment_intent.payment_failed':
        logger.warning(f"Payment intent failed: {payment_intent['id']} - {payment_intent.get('last_payment_error', {}).get('message', 'Unknown error')}")


async def handle_transfer_webhook(event: dict, db: AsyncSession) -> None:
    """Handle Stripe transfer webhook events"""
    
    event_type = event['type']
    transfer = event['data']['object']
    
    logger.info(f"Processing transfer webhook: {event_type} - {transfer['id']}")
    
    if event_type == 'transfer.created':
        logger.info(f"Transfer created: {transfer['id']} - ${transfer['amount']/100:.2f} to {transfer['destination']}")
    elif event_type == 'transfer.paid':
        logger.info(f"Transfer completed: {transfer['id']} - ${transfer['amount']/100:.2f}")
    elif event_type == 'transfer.failed':
        logger.warning(f"Transfer failed: {transfer['id']} - ${transfer['amount']/100:.2f}")


async def handle_plaid_item_webhook(webhook_data: dict, db: AsyncSession) -> None:
    """Handle Plaid ITEM webhook events"""
    
    webhook_code = webhook_data.get('webhook_code')
    item_id = webhook_data.get('item_id')
    error = webhook_data.get('error')
    
    logger.info(f"Processing Plaid ITEM webhook: {webhook_code} for item {item_id}")
    
    if webhook_code == 'ERROR':
        logger.error(f"Plaid item error for {item_id}: {error}")
        # Update payment account status to error
        
    elif webhook_code == 'PENDING_EXPIRATION':
        logger.warning(f"Plaid item {item_id} access token expires soon")
        # Could trigger re-authentication flow
        
    elif webhook_code == 'USER_PERMISSION_REVOKED':
        logger.warning(f"User revoked permissions for Plaid item {item_id}")
        # Disable payment account


async def handle_plaid_transactions_webhook(webhook_data: dict, db: AsyncSession) -> None:
    """Handle Plaid TRANSACTIONS webhook events"""
    
    webhook_code = webhook_data.get('webhook_code')
    item_id = webhook_data.get('item_id')
    
    logger.info(f"Processing Plaid TRANSACTIONS webhook: {webhook_code} for item {item_id}")
    
    if webhook_code in ['INITIAL_UPDATE', 'HISTORICAL_UPDATE', 'DEFAULT_UPDATE']:
        # New transaction data available
        new_transactions = webhook_data.get('new_transactions', 0)
        modified_transactions = webhook_data.get('modified_transactions', 0)
        removed_transactions = webhook_data.get('removed_transactions', 0)
        
        logger.info(f"Transaction update: +{new_transactions} new, ~{modified_transactions} modified, -{removed_transactions} removed")


async def handle_plaid_auth_webhook(webhook_data: dict, db: AsyncSession) -> None:
    """Handle Plaid AUTH webhook events"""
    
    webhook_code = webhook_data.get('webhook_code')
    item_id = webhook_data.get('item_id')
    
    logger.info(f"Processing Plaid AUTH webhook: {webhook_code} for item {item_id}")
    
    if webhook_code == 'AUTOMATICALLY_VERIFIED':
        logger.info(f"Plaid auth automatically verified for item {item_id}")
    elif webhook_code == 'VERIFICATION_EXPIRED':
        logger.warning(f"Plaid auth verification expired for item {item_id}")
        # Could trigger re-verification
