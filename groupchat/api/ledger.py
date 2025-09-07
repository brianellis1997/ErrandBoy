"""API endpoints for ledger and payment operations"""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from groupchat.db.database import get_db
from groupchat.services.ledger import LedgerService

router = APIRouter(tags=["ledger"])


@router.get("/balance/{account_type}/{account_id}")
async def get_balance(
    account_type: str,
    account_id: str,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Get current balance for an account"""
    
    ledger_service = LedgerService(db)
    
    try:
        balance = await ledger_service.get_user_balance(account_type, account_id)
        return {
            "success": True,
            "data": balance
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting balance: {str(e)}")


@router.get("/transactions")
async def get_transaction_history(
    account_type: str | None = Query(None),
    account_id: str | None = Query(None),
    transaction_id: str | None = Query(None),
    limit: int = Query(50, ge=1, le=1000),
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Get transaction history with optional filters"""
    
    ledger_service = LedgerService(db)
    
    try:
        # Parse transaction_id if provided
        parsed_transaction_id = None
        if transaction_id:
            try:
                parsed_transaction_id = uuid.UUID(transaction_id)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid transaction_id format")
        
        transactions = await ledger_service.get_transaction_history(
            account_type=account_type,
            account_id=account_id,
            transaction_id=parsed_transaction_id,
            limit=limit
        )
        
        return {
            "success": True,
            "data": {
                "transactions": transactions,
                "count": len(transactions),
                "filters": {
                    "account_type": account_type,
                    "account_id": account_id,
                    "transaction_id": transaction_id,
                    "limit": limit
                }
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting transactions: {str(e)}")


@router.get("/transaction/{transaction_id}/validate")
async def validate_transaction(
    transaction_id: str,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Validate that a transaction is balanced (debits = credits)"""
    
    ledger_service = LedgerService(db)
    
    try:
        parsed_transaction_id = uuid.UUID(transaction_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid transaction_id format")
    
    try:
        validation = await ledger_service.validate_transaction_balance(parsed_transaction_id)
        return {
            "success": True,
            "data": validation
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error validating transaction: {str(e)}")


@router.post("/process-payment")
async def process_query_payment(
    query_id: str,
    compiled_answer_id: str,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Process payment for a completed query (admin endpoint)"""
    
    ledger_service = LedgerService(db)
    
    try:
        parsed_query_id = uuid.UUID(query_id)
        parsed_answer_id = uuid.UUID(compiled_answer_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID format")
    
    try:
        result = await ledger_service.process_query_payment(
            query_id=parsed_query_id,
            compiled_answer_id=parsed_answer_id
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing payment: {str(e)}")


@router.get("/contact/{contact_id}/earnings")
async def get_contact_earnings(
    contact_id: str,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Get earnings summary for a contact"""
    
    try:
        contact_uuid = uuid.UUID(contact_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid contact_id format")
    
    ledger_service = LedgerService(db)
    
    try:
        # Get balance for this contact
        balance = await ledger_service.get_user_balance(
            account_type="contributor", 
            account_id=f"contact_{contact_id}"
        )
        
        # Get recent transactions
        transactions = await ledger_service.get_transaction_history(
            account_type="contributor",
            account_id=f"contact_{contact_id}",
            limit=20
        )
        
        # Calculate earnings metrics
        earnings_transactions = [
            t for t in transactions 
            if t["transaction_type"] == "contribution_payout" and t["entry_type"] == "credit"
        ]
        
        total_queries = len(set(t["query_id"] for t in earnings_transactions if t["query_id"]))
        
        return {
            "success": True,
            "data": {
                "contact_id": contact_id,
                "current_balance": balance,
                "total_queries_contributed": total_queries,
                "recent_transactions": transactions,
                "earnings_summary": {
                    "total_earned_cents": balance["total_credits_cents"],
                    "total_earned_dollars": balance["total_credits_cents"] / 100.0,
                    "queries_contributed": total_queries
                }
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting earnings: {str(e)}")


@router.get("/stats/platform")
async def get_platform_stats(
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Get platform earnings and payment statistics"""
    
    ledger_service = LedgerService(db)
    
    try:
        # Get platform balance
        platform_balance = await ledger_service.get_user_balance(
            account_type="platform",
            account_id="platform_revenue"
        )
        
        # Get referral pool balance  
        referral_balance = await ledger_service.get_user_balance(
            account_type="referral",
            account_id="referral_pool"
        )
        
        # Get recent platform transactions
        platform_transactions = await ledger_service.get_transaction_history(
            account_type="platform",
            account_id="platform_revenue",
            limit=20
        )
        
        # Calculate metrics
        fee_transactions = [
            t for t in platform_transactions 
            if t["transaction_type"] == "platform_fee" and t["entry_type"] == "credit"
        ]
        
        total_queries_processed = len(set(t["query_id"] for t in fee_transactions if t["query_id"]))
        
        return {
            "success": True,
            "data": {
                "platform_balance": platform_balance,
                "referral_pool_balance": referral_balance,
                "total_queries_processed": total_queries_processed,
                "recent_platform_transactions": platform_transactions,
                "summary": {
                    "total_platform_fees_cents": platform_balance["balance_cents"],
                    "total_platform_fees_dollars": platform_balance["balance_cents"] / 100.0,
                    "total_referral_pool_cents": referral_balance["balance_cents"],
                    "total_referral_pool_dollars": referral_balance["balance_cents"] / 100.0,
                    "queries_processed": total_queries_processed
                }
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting platform stats: {str(e)}")