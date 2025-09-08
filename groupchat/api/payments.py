"""API endpoints for payment processing, bank account linking, and balance management"""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from groupchat.db.database import get_db
from groupchat.services.payment_service import PaymentService
from groupchat.services.plaid_service import PlaidService
from groupchat.services.stripe_connect_service import StripeConnectService

router = APIRouter(tags=["payments"])


# Request/Response Models
class ConnectBankRequest(BaseModel):
    user_phone: str = Field(..., description="User's phone number")


class LinkTokenResponse(BaseModel):
    link_token: str
    expiration: str
    request_id: str


class ExchangeTokenRequest(BaseModel):
    user_phone: str = Field(..., description="User's phone number")
    public_token: str = Field(..., description="Public token from Plaid Link")
    account_id: str | None = Field(None, description="Specific account ID to link")


class DepositRequest(BaseModel):
    user_phone: str = Field(..., description="User's phone number")
    payment_account_id: str = Field(..., description="Payment account ID")
    amount_cents: int = Field(..., ge=100, description="Amount in cents (minimum $1.00)")
    description: str | None = Field(None, description="Optional deposit description")


class WithdrawRequest(BaseModel):
    user_phone: str = Field(..., description="User's phone number")
    payment_account_id: str = Field(..., description="Payment account ID")
    amount_cents: int = Field(..., ge=100, description="Amount in cents (minimum $1.00)")
    description: str | None = Field(None, description="Optional withdrawal description")


class AutopayRequest(BaseModel):
    user_phone: str = Field(..., description="User's phone number")
    payment_account_id: str = Field(..., description="Payment account ID for auto-deposits")
    min_balance_cents: int = Field(..., ge=0, description="Minimum balance threshold in cents")
    auto_deposit_amount_cents: int = Field(..., ge=100, description="Auto-deposit amount in cents")


class ExpertConnectRequest(BaseModel):
    contact_id: str = Field(..., description="Expert's contact ID")


# Bank Account Connection Endpoints
@router.post("/connect-bank", response_model=LinkTokenResponse)
async def create_link_token(
    request: ConnectBankRequest,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Create a Plaid Link token for bank account connection"""
    
    plaid_service = PlaidService(db)
    
    try:
        result = await plaid_service.create_link_token(request.user_phone)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create link token: {str(e)}")


@router.post("/connect-bank/exchange")
async def exchange_public_token(
    request: ExchangeTokenRequest,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Exchange public token for access token and save bank account"""
    
    plaid_service = PlaidService(db)
    
    try:
        result = await plaid_service.exchange_public_token(
            user_phone=request.user_phone,
            public_token=request.public_token,
            account_id=request.account_id
        )
        return {
            "success": True,
            "data": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to link bank account: {str(e)}")


@router.get("/accounts/{user_phone}")
async def get_user_payment_accounts(
    user_phone: str,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Get all payment accounts for a user"""
    
    plaid_service = PlaidService(db)
    
    try:
        accounts = await plaid_service.get_user_payment_accounts(user_phone)
        return {
            "success": True,
            "data": {
                "accounts": accounts,
                "count": len(accounts)
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get payment accounts: {str(e)}")


@router.delete("/accounts/{user_phone}/{account_id}")
async def remove_payment_account(
    user_phone: str,
    account_id: str,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Remove a payment account"""
    
    plaid_service = PlaidService(db)
    
    try:
        account_uuid = uuid.UUID(account_id)
        result = await plaid_service.remove_payment_account(user_phone, account_uuid)
        return {
            "success": result,
            "message": "Payment account removed successfully"
        }
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid account ID format")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to remove payment account: {str(e)}")


# Balance and Transaction Endpoints
@router.get("/balance/{user_phone}")
async def get_user_balance(
    user_phone: str,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Get user's current GroupChat balance"""
    
    payment_service = PaymentService(db)
    
    try:
        balance = await payment_service.ledger_service.get_user_balance("user", user_phone)
        return {
            "success": True,
            "data": balance
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get balance: {str(e)}")


@router.get("/balance/bank-account/{account_id}")
async def get_bank_account_balance(
    account_id: str,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Get real-time bank account balance from Plaid"""
    
    plaid_service = PlaidService(db)
    
    try:
        account_uuid = uuid.UUID(account_id)
        balance = await plaid_service.get_account_balance(account_uuid)
        return {
            "success": True,
            "data": balance
        }
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid account ID format")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get bank account balance: {str(e)}")


@router.get("/transactions/{user_phone}")
async def get_payment_history(
    user_phone: str,
    intent_type: str | None = Query(None, description="Filter by intent type (deposit, withdrawal)"),
    limit: int = Query(50, ge=1, le=100, description="Number of transactions to return"),
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Get user's payment transaction history"""
    
    payment_service = PaymentService(db)
    
    try:
        transactions = await payment_service.get_user_payment_history(
            user_phone=user_phone,
            intent_type=intent_type,
            limit=limit
        )
        return {
            "success": True,
            "data": {
                "transactions": transactions,
                "count": len(transactions),
                "filters": {
                    "intent_type": intent_type,
                    "limit": limit
                }
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get payment history: {str(e)}")


# Deposit and Withdrawal Endpoints
@router.post("/deposit")
async def process_deposit(
    request: DepositRequest,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Process a deposit from user's bank account to GroupChat balance"""
    
    payment_service = PaymentService(db)
    
    try:
        payment_account_uuid = uuid.UUID(request.payment_account_id)
        result = await payment_service.process_deposit(
            user_phone=request.user_phone,
            payment_account_id=payment_account_uuid,
            amount_cents=request.amount_cents,
            description=request.description
        )
        return {
            "success": True,
            "data": result
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process deposit: {str(e)}")


@router.post("/withdraw")
async def process_withdrawal(
    request: WithdrawRequest,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Process a withdrawal from GroupChat balance to user's bank account"""
    
    payment_service = PaymentService(db)
    
    try:
        payment_account_uuid = uuid.UUID(request.payment_account_id)
        result = await payment_service.process_withdrawal(
            user_phone=request.user_phone,
            payment_account_id=payment_account_uuid,
            amount_cents=request.amount_cents,
            description=request.description
        )
        return {
            "success": True,
            "data": result
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process withdrawal: {str(e)}")


@router.get("/intent/{intent_id}")
async def get_payment_intent_status(
    intent_id: str,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Get status of a payment intent"""
    
    payment_service = PaymentService(db)
    
    try:
        intent_uuid = uuid.UUID(intent_id)
        result = await payment_service.get_payment_intent_status(intent_uuid)
        return {
            "success": True,
            "data": result
        }
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payment intent ID format")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get payment intent status: {str(e)}")


# Autopay Configuration
@router.post("/setup-autopay")
async def setup_autopay(
    request: AutopayRequest,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Setup automatic deposits when balance falls below threshold"""
    
    payment_service = PaymentService(db)
    
    try:
        payment_account_uuid = uuid.UUID(request.payment_account_id)
        result = await payment_service.setup_autopay(
            user_phone=request.user_phone,
            payment_account_id=payment_account_uuid,
            min_balance_cents=request.min_balance_cents,
            auto_deposit_amount_cents=request.auto_deposit_amount_cents
        )
        return {
            "success": True,
            "data": result
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to setup autopay: {str(e)}")


@router.post("/autopay/check/{user_phone}")
async def check_autopay(
    user_phone: str,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Check if user needs autopay and trigger if necessary"""
    
    payment_service = PaymentService(db)
    
    try:
        result = await payment_service.check_and_trigger_autopay(user_phone)
        return {
            "success": True,
            "data": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to check autopay: {str(e)}")


# Expert Stripe Connect Endpoints
@router.post("/expert/connect-stripe")
async def connect_expert_stripe(
    request: ExpertConnectRequest,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Create Stripe Connect account for expert"""
    
    stripe_service = StripeConnectService(db)
    
    try:
        contact_uuid = uuid.UUID(request.contact_id)
        result = await stripe_service.create_connected_account(contact_uuid)
        return {
            "success": True,
            "data": result
        }
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid contact ID format")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create Stripe Connect account: {str(e)}")


@router.post("/expert/{contact_id}/onboarding-link")
async def create_expert_onboarding_link(
    contact_id: str,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Create onboarding link for expert Stripe Connect account"""
    
    stripe_service = StripeConnectService(db)
    
    try:
        contact_uuid = uuid.UUID(contact_id)
        result = await stripe_service.create_account_link(contact_uuid)
        return {
            "success": True,
            "data": result
        }
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid contact ID format")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create onboarding link: {str(e)}")


@router.get("/expert/{contact_id}/status")
async def get_expert_account_status(
    contact_id: str,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Get expert's Stripe Connect account status"""
    
    stripe_service = StripeConnectService(db)
    
    try:
        contact_uuid = uuid.UUID(contact_id)
        result = await stripe_service.get_account_status(contact_uuid)
        return {
            "success": True,
            "data": result
        }
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid contact ID format")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get account status: {str(e)}")


@router.get("/expert/{contact_id}/payouts")
async def get_expert_payout_history(
    contact_id: str,
    limit: int = Query(20, ge=1, le=100, description="Number of payouts to return"),
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Get expert's payout history"""
    
    stripe_service = StripeConnectService(db)
    
    try:
        contact_uuid = uuid.UUID(contact_id)
        result = await stripe_service.get_payout_history(contact_uuid, limit=limit)
        return {
            "success": True,
            "data": {
                "payouts": result,
                "count": len(result)
            }
        }
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid contact ID format")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get payout history: {str(e)}")


# Admin/Testing Endpoints
@router.post("/admin/process-expert-payout")
async def process_expert_payout(
    contact_id: str,
    amount_cents: int = Query(..., ge=100, description="Amount in cents"),
    description: str = Query("Manual payout", description="Payout description"),
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Process a manual payout to expert (admin endpoint)"""
    
    stripe_service = StripeConnectService(db)
    
    try:
        contact_uuid = uuid.UUID(contact_id)
        result = await stripe_service.process_payout(
            contact_id=contact_uuid,
            amount_cents=amount_cents,
            description=description,
            metadata={'manual_payout': True}
        )
        return {
            "success": True,
            "data": result
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process payout: {str(e)}")