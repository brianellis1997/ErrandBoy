"""Payment service for orchestrating deposits, withdrawals, and payment flows"""

import logging
import uuid
from datetime import datetime
from typing import Any

import stripe
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from groupchat.config import settings
from groupchat.db.models import (
    LedgerEntryType,
    PaymentIntent,
    PaymentIntentStatus,
    TransactionType,
    UserPaymentAccount,
)
from groupchat.services.ledger import LedgerService
from groupchat.services.plaid_service import PlaidService
from groupchat.services.stripe_connect_service import StripeConnectService

logger = logging.getLogger(__name__)


class PaymentService:
    """Service for processing deposits, withdrawals, and payment flows"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.ledger_service = LedgerService(db)
        self.plaid_service = PlaidService(db)
        self.stripe_connect_service = StripeConnectService(db)
        
        # Configure Stripe
        stripe.api_key = settings.stripe_secret_key
        self.stripe_client = stripe

    async def process_deposit(
        self, 
        user_phone: str, 
        payment_account_id: uuid.UUID, 
        amount_cents: int,
        description: str = None
    ) -> dict[str, Any]:
        """
        Process a deposit from user's bank account to their GroupChat balance
        
        Args:
            user_phone: User's phone number
            payment_account_id: User's payment account ID
            amount_cents: Amount to deposit in cents
            description: Optional deposit description
            
        Returns:
            Deposit processing results
        """
        try:
            # Validate payment account
            payment_account = await self._get_user_payment_account(user_phone, payment_account_id)
            
            if not payment_account.can_deposit:
                raise ValueError("Deposit not enabled for this payment account")
                
            # Create payment intent
            payment_intent = PaymentIntent(
                id=uuid.uuid4(),
                user_phone=user_phone,
                amount_cents=amount_cents,
                intent_type="deposit",
                description=description or f"Deposit ${amount_cents/100:.2f} to GroupChat balance",
                status=PaymentIntentStatus.PENDING,
                payment_account_id=payment_account_id,
                extra_metadata={
                    'deposit_method': 'bank_transfer',
                    'institution_name': payment_account.institution_name,
                    'account_mask': payment_account.account_mask
                }
            )
            
            self.db.add(payment_intent)
            await self.db.flush()  # Get the payment intent ID
            
            # For MVP, we'll simulate the deposit process
            # In production, this would integrate with Stripe ACH or Plaid Transfer
            if settings.app_env == "production":
                # Use Stripe for ACH processing
                stripe_intent = await self._create_stripe_payment_intent(
                    payment_intent, payment_account
                )
                payment_intent.stripe_payment_intent_id = stripe_intent['id']
            else:
                # Simulate successful deposit in sandbox/development
                await self._simulate_successful_deposit(payment_intent)
                
            await self.db.commit()
            
            logger.info(f"Initiated deposit of ${amount_cents/100:.2f} for user {user_phone}")
            
            return {
                'payment_intent_id': str(payment_intent.id),
                'amount_cents': amount_cents,
                'amount_dollars': amount_cents / 100.0,
                'status': payment_intent.status.value,
                'description': payment_intent.description,
                'created_at': payment_intent.created_at.isoformat()
            }
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to process deposit for user {user_phone}: {str(e)}")
            raise Exception(f"Failed to process deposit: {str(e)}")

    async def process_withdrawal(
        self,
        user_phone: str,
        payment_account_id: uuid.UUID,
        amount_cents: int,
        description: str = None
    ) -> dict[str, Any]:
        """
        Process a withdrawal from user's GroupChat balance to their bank account
        
        Args:
            user_phone: User's phone number
            payment_account_id: User's payment account ID
            amount_cents: Amount to withdraw in cents
            description: Optional withdrawal description
            
        Returns:
            Withdrawal processing results
        """
        try:
            # Validate payment account
            payment_account = await self._get_user_payment_account(user_phone, payment_account_id)
            
            if not payment_account.can_withdraw:
                raise ValueError("Withdrawal not enabled for this payment account")
                
            # Check user balance
            user_balance = await self.ledger_service.get_user_balance("user", user_phone)
            
            if user_balance['balance_cents'] < amount_cents:
                raise ValueError(f"Insufficient balance. Available: ${user_balance['balance_cents']/100:.2f}")
                
            # Create payment intent
            payment_intent = PaymentIntent(
                id=uuid.uuid4(),
                user_phone=user_phone,
                amount_cents=amount_cents,
                intent_type="withdrawal",
                description=description or f"Withdraw ${amount_cents/100:.2f} from GroupChat balance",
                status=PaymentIntentStatus.PENDING,
                payment_account_id=payment_account_id,
                extra_metadata={
                    'withdrawal_method': 'bank_transfer',
                    'institution_name': payment_account.institution_name,
                    'account_mask': payment_account.account_mask
                }
            )
            
            self.db.add(payment_intent)
            await self.db.flush()
            
            # Process withdrawal
            if settings.app_env == "production":
                # Use actual bank transfer
                await self._create_bank_transfer(payment_intent, payment_account)
            else:
                # Simulate successful withdrawal
                await self._simulate_successful_withdrawal(payment_intent)
                
            await self.db.commit()
            
            logger.info(f"Initiated withdrawal of ${amount_cents/100:.2f} for user {user_phone}")
            
            return {
                'payment_intent_id': str(payment_intent.id),
                'amount_cents': amount_cents,
                'amount_dollars': amount_cents / 100.0,
                'status': payment_intent.status.value,
                'description': payment_intent.description,
                'created_at': payment_intent.created_at.isoformat()
            }
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to process withdrawal for user {user_phone}: {str(e)}")
            raise Exception(f"Failed to process withdrawal: {str(e)}")

    async def get_payment_intent_status(self, payment_intent_id: uuid.UUID) -> dict[str, Any]:
        """
        Get status of a payment intent
        
        Args:
            payment_intent_id: Payment intent ID
            
        Returns:
            Payment intent status and details
        """
        try:
            stmt = select(PaymentIntent).where(PaymentIntent.id == payment_intent_id)
            result = await self.db.execute(stmt)
            payment_intent = result.scalar_one_or_none()
            
            if not payment_intent:
                raise ValueError(f"Payment intent {payment_intent_id} not found")
                
            return {
                'payment_intent_id': str(payment_intent.id),
                'user_phone': payment_intent.user_phone,
                'amount_cents': payment_intent.amount_cents,
                'amount_dollars': payment_intent.amount_cents / 100.0,
                'intent_type': payment_intent.intent_type,
                'status': payment_intent.status.value,
                'description': payment_intent.description,
                'created_at': payment_intent.created_at.isoformat(),
                'processed_at': payment_intent.processed_at.isoformat() if payment_intent.processed_at else None,
                'failure_reason': payment_intent.failure_reason,
                'ledger_transaction_id': str(payment_intent.ledger_transaction_id) if payment_intent.ledger_transaction_id else None
            }
            
        except Exception as e:
            logger.error(f"Failed to get payment intent status {payment_intent_id}: {str(e)}")
            raise Exception(f"Failed to get payment intent status: {str(e)}")

    async def get_user_payment_history(
        self, 
        user_phone: str, 
        intent_type: str = None, 
        limit: int = 50
    ) -> list[dict[str, Any]]:
        """
        Get payment history for a user
        
        Args:
            user_phone: User's phone number
            intent_type: Filter by intent type (deposit, withdrawal)
            limit: Number of records to return
            
        Returns:
            List of payment intents
        """
        try:
            stmt = (
                select(PaymentIntent)
                .where(PaymentIntent.user_phone == user_phone)
                .order_by(PaymentIntent.created_at.desc())
                .limit(limit)
            )
            
            if intent_type:
                stmt = stmt.where(PaymentIntent.intent_type == intent_type)
                
            result = await self.db.execute(stmt)
            payment_intents = result.scalars().all()
            
            return [
                {
                    'payment_intent_id': str(intent.id),
                    'amount_cents': intent.amount_cents,
                    'amount_dollars': intent.amount_cents / 100.0,
                    'intent_type': intent.intent_type,
                    'status': intent.status.value,
                    'description': intent.description,
                    'created_at': intent.created_at.isoformat(),
                    'processed_at': intent.processed_at.isoformat() if intent.processed_at else None,
                    'failure_reason': intent.failure_reason
                }
                for intent in payment_intents
            ]
            
        except Exception as e:
            logger.error(f"Failed to get payment history for user {user_phone}: {str(e)}")
            raise Exception(f"Failed to get payment history: {str(e)}")

    async def setup_autopay(
        self,
        user_phone: str,
        payment_account_id: uuid.UUID,
        min_balance_cents: int,
        auto_deposit_amount_cents: int
    ) -> dict[str, Any]:
        """
        Setup automatic deposits when balance falls below threshold
        
        Args:
            user_phone: User's phone number
            payment_account_id: Payment account for auto-deposits
            min_balance_cents: Minimum balance threshold
            auto_deposit_amount_cents: Amount to auto-deposit
            
        Returns:
            Autopay configuration
        """
        try:
            # Validate payment account
            payment_account = await self._get_user_payment_account(user_phone, payment_account_id)
            
            if not payment_account.can_deposit:
                raise ValueError("Auto-deposit not supported for this payment account")
                
            # Store autopay configuration in payment account metadata
            payment_account.extra_metadata.update({
                'autopay': {
                    'enabled': True,
                    'min_balance_cents': min_balance_cents,
                    'auto_deposit_amount_cents': auto_deposit_amount_cents,
                    'configured_at': datetime.utcnow().isoformat()
                }
            })
            
            await self.db.commit()
            
            logger.info(f"Setup autopay for user {user_phone}: min ${min_balance_cents/100:.2f}, deposit ${auto_deposit_amount_cents/100:.2f}")
            
            return {
                'user_phone': user_phone,
                'payment_account_id': str(payment_account_id),
                'min_balance_cents': min_balance_cents,
                'min_balance_dollars': min_balance_cents / 100.0,
                'auto_deposit_amount_cents': auto_deposit_amount_cents,
                'auto_deposit_amount_dollars': auto_deposit_amount_cents / 100.0,
                'enabled': True
            }
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to setup autopay for user {user_phone}: {str(e)}")
            raise Exception(f"Failed to setup autopay: {str(e)}")

    async def check_and_trigger_autopay(self, user_phone: str) -> dict[str, Any]:
        """
        Check if user needs autopay and trigger if necessary
        
        Args:
            user_phone: User's phone number
            
        Returns:
            Autopay check results
        """
        try:
            # Get user's payment accounts with autopay enabled
            stmt = select(UserPaymentAccount).where(
                UserPaymentAccount.user_phone == user_phone,
                UserPaymentAccount.deleted_at.is_(None),
                UserPaymentAccount.extra_metadata['autopay']['enabled'].astext == 'true'
            )
            result = await self.db.execute(stmt)
            autopay_accounts = result.scalars().all()
            
            if not autopay_accounts:
                return {'autopay_triggered': False, 'reason': 'no_autopay_configured'}
                
            # Check user balance
            user_balance = await self.ledger_service.get_user_balance("user", user_phone)
            
            for account in autopay_accounts:
                autopay_config = account.extra_metadata.get('autopay', {})
                min_balance = autopay_config.get('min_balance_cents', 0)
                
                if user_balance['balance_cents'] < min_balance:
                    # Trigger autopay
                    auto_deposit_amount = autopay_config.get('auto_deposit_amount_cents', 1000)
                    
                    deposit_result = await self.process_deposit(
                        user_phone=user_phone,
                        payment_account_id=account.id,
                        amount_cents=auto_deposit_amount,
                        description=f"Automatic deposit - balance below ${min_balance/100:.2f}"
                    )
                    
                    return {
                        'autopay_triggered': True,
                        'deposit_amount_cents': auto_deposit_amount,
                        'deposit_amount_dollars': auto_deposit_amount / 100.0,
                        'payment_intent_id': deposit_result['payment_intent_id'],
                        'trigger_balance_cents': user_balance['balance_cents'],
                        'min_balance_cents': min_balance
                    }
                    
            return {'autopay_triggered': False, 'reason': 'balance_above_threshold'}
            
        except Exception as e:
            logger.error(f"Failed autopay check for user {user_phone}: {str(e)}")
            return {'autopay_triggered': False, 'reason': f'error: {str(e)}'}

    async def _get_user_payment_account(
        self, 
        user_phone: str, 
        payment_account_id: uuid.UUID
    ) -> UserPaymentAccount:
        """Get and validate user payment account"""
        stmt = select(UserPaymentAccount).where(
            UserPaymentAccount.id == payment_account_id,
            UserPaymentAccount.user_phone == user_phone,
            UserPaymentAccount.deleted_at.is_(None)
        )
        result = await self.db.execute(stmt)
        payment_account = result.scalar_one_or_none()
        
        if not payment_account:
            raise ValueError(f"Payment account {payment_account_id} not found for user {user_phone}")
            
        return payment_account

    async def _simulate_successful_deposit(self, payment_intent: PaymentIntent) -> None:
        """Simulate successful deposit for development/testing"""
        # Update payment intent status
        payment_intent.status = PaymentIntentStatus.SUCCEEDED
        payment_intent.processed_at = datetime.utcnow()
        
        # Create ledger transaction
        transaction_id = uuid.uuid4()
        
        await self.ledger_service._create_ledger_entry(
            transaction_id=transaction_id,
            transaction_type=TransactionType.QUERY_PAYMENT,  # Reusing enum, could add DEPOSIT
            account_type="user",
            account_id=payment_intent.user_phone,
            entry_type=LedgerEntryType.CREDIT,
            amount_cents=payment_intent.amount_cents,
            description=f"Deposit: {payment_intent.description}",
            extra_metadata={
                'payment_intent_id': str(payment_intent.id),
                'deposit_simulation': True
            }
        )
        
        payment_intent.ledger_transaction_id = transaction_id
        
        logger.info(f"Simulated successful deposit of ${payment_intent.amount_cents/100:.2f} for user {payment_intent.user_phone}")

    async def _simulate_successful_withdrawal(self, payment_intent: PaymentIntent) -> None:
        """Simulate successful withdrawal for development/testing"""
        # Update payment intent status
        payment_intent.status = PaymentIntentStatus.SUCCEEDED
        payment_intent.processed_at = datetime.utcnow()
        
        # Create ledger transaction
        transaction_id = uuid.uuid4()
        
        await self.ledger_service._create_ledger_entry(
            transaction_id=transaction_id,
            transaction_type=TransactionType.QUERY_PAYMENT,  # Reusing enum, could add WITHDRAWAL
            account_type="user",
            account_id=payment_intent.user_phone,
            entry_type=LedgerEntryType.DEBIT,
            amount_cents=payment_intent.amount_cents,
            description=f"Withdrawal: {payment_intent.description}",
            extra_metadata={
                'payment_intent_id': str(payment_intent.id),
                'withdrawal_simulation': True
            }
        )
        
        payment_intent.ledger_transaction_id = transaction_id
        
        logger.info(f"Simulated successful withdrawal of ${payment_intent.amount_cents/100:.2f} for user {payment_intent.user_phone}")

    async def _create_stripe_payment_intent(
        self, 
        payment_intent: PaymentIntent, 
        payment_account: UserPaymentAccount
    ) -> dict[str, Any]:
        """Create Stripe payment intent for production deposits"""
        # This would be implemented for production use
        # Would require additional Stripe setup for ACH payments
        raise NotImplementedError("Production Stripe ACH integration not implemented")

    async def _create_bank_transfer(
        self, 
        payment_intent: PaymentIntent, 
        payment_account: UserPaymentAccount
    ) -> None:
        """Create bank transfer for production withdrawals"""
        # This would be implemented for production use
        # Would use Stripe transfers or similar service
        raise NotImplementedError("Production bank transfer integration not implemented")