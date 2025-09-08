"""Plaid service for bank account linking and verification"""

import logging
import uuid
from datetime import datetime, timedelta
from typing import Any

import plaid
from plaid.api import plaid_api
from plaid.model.accounts_get_request import AccountsGetRequest
from plaid.model.country_code import CountryCode
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.products import Products
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from groupchat.config import settings
from groupchat.db.models import PaymentAccountStatus, UserPaymentAccount

logger = logging.getLogger(__name__)


class PlaidService:
    """Service for Plaid bank account integration"""

    def __init__(self, db: AsyncSession):
        self.db = db
        
        # Configure Plaid client
        configuration = plaid.Configuration(
            host=self._get_plaid_environment(),
            api_key={
                'clientId': settings.plaid_client_id,
                'secret': settings.plaid_secret,
            }
        )
        
        api_client = plaid.ApiClient(configuration)
        self.client = plaid_api.PlaidApi(api_client)

    def _get_plaid_environment(self) -> plaid.Environment:
        """Get Plaid environment based on app environment"""
        if settings.app_env == "production":
            return plaid.Environment.Production
        elif settings.app_env == "staging":
            return plaid.Environment.Development
        else:
            return plaid.Environment.Sandbox

    async def create_link_token(self, user_phone: str) -> dict[str, Any]:
        """
        Create a Plaid Link token for bank account connection
        
        Args:
            user_phone: User's phone number identifier
            
        Returns:
            Link token and expiration information
        """
        try:
            request = LinkTokenCreateRequest(
                products=[Products('auth'), Products('identity')],
                client_name="GroupChat Network Intelligence",
                country_codes=[CountryCode('US')],
                language='en',
                user=LinkTokenCreateRequestUser(
                    client_user_id=user_phone
                ),
                link_customization_name='default',
                account_filters={
                    'depository': {
                        'account_type': ['checking', 'savings']
                    }
                }
            )
            
            response = self.client.link_token_create(request)
            
            logger.info(f"Created Plaid link token for user {user_phone}")
            
            return {
                'link_token': response['link_token'],
                'expiration': response['expiration'],
                'request_id': response['request_id']
            }
            
        except Exception as e:
            logger.error(f"Failed to create Plaid link token for user {user_phone}: {str(e)}")
            raise Exception(f"Failed to create link token: {str(e)}")

    async def exchange_public_token(
        self, 
        user_phone: str, 
        public_token: str, 
        account_id: str = None
    ) -> dict[str, Any]:
        """
        Exchange public token for access token and save account info
        
        Args:
            user_phone: User's phone number
            public_token: Temporary public token from Link
            account_id: Specific account ID to link (optional)
            
        Returns:
            Payment account information
        """
        try:
            # Exchange public token for access token
            exchange_request = ItemPublicTokenExchangeRequest(
                public_token=public_token
            )
            exchange_response = self.client.item_public_token_exchange(exchange_request)
            
            access_token = exchange_response['access_token']
            item_id = exchange_response['item_id']
            
            # Get account information
            accounts_request = AccountsGetRequest(access_token=access_token)
            accounts_response = self.client.accounts_get(accounts_request)
            
            institution_name = accounts_response.get('item', {}).get('institution_id', 'Unknown')
            
            # Process accounts
            saved_accounts = []
            
            for account in accounts_response['accounts']:
                # If specific account_id provided, only process that account
                if account_id and account['account_id'] != account_id:
                    continue
                    
                # Create payment account record
                payment_account = await self._create_payment_account(
                    user_phone=user_phone,
                    access_token=access_token,
                    item_id=item_id,
                    account=account,
                    institution_name=institution_name
                )
                
                saved_accounts.append({
                    'id': str(payment_account.id),
                    'account_name': payment_account.account_name,
                    'account_type': payment_account.account_type,
                    'account_mask': payment_account.account_mask,
                    'institution_name': payment_account.institution_name,
                    'status': payment_account.status.value,
                    'can_deposit': payment_account.can_deposit,
                    'can_withdraw': payment_account.can_withdraw
                })
                
            await self.db.commit()
            
            logger.info(f"Successfully linked {len(saved_accounts)} accounts for user {user_phone}")
            
            return {
                'accounts': saved_accounts,
                'item_id': item_id
            }
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to exchange public token for user {user_phone}: {str(e)}")
            raise Exception(f"Failed to link bank account: {str(e)}")

    async def _create_payment_account(
        self,
        user_phone: str,
        access_token: str,
        item_id: str,
        account: dict[str, Any],
        institution_name: str
    ) -> UserPaymentAccount:
        """Create a payment account record from Plaid account data"""
        
        # Determine account capabilities based on type
        account_type = account.get('type', 'depository').lower()
        account_subtype = account.get('subtype', '').lower()
        
        can_deposit = account_type in ['depository'] and account_subtype in ['checking', 'savings']
        can_withdraw = can_deposit  # For now, same logic
        
        # Check if this is the first account (make it primary)
        stmt = select(UserPaymentAccount).where(
            UserPaymentAccount.user_phone == user_phone,
            UserPaymentAccount.deleted_at.is_(None)
        )
        result = await self.db.execute(stmt)
        existing_accounts = result.scalars().all()
        is_primary = len(existing_accounts) == 0
        
        payment_account = UserPaymentAccount(
            id=uuid.uuid4(),
            user_phone=user_phone,
            plaid_access_token=access_token,
            plaid_item_id=item_id,
            plaid_account_id=account['account_id'],
            account_name=account.get('name', 'Bank Account'),
            account_type=account_type,
            account_subtype=account_subtype,
            account_mask=account.get('mask', '****'),
            institution_name=institution_name,
            institution_id=account.get('institution_id', ''),
            status=PaymentAccountStatus.CONNECTED,
            is_verified=True,  # Plaid handles verification
            verified_at=datetime.utcnow(),
            can_deposit=can_deposit,
            can_withdraw=can_withdraw,
            is_primary=is_primary,
            extra_metadata={
                'account_data': {
                    'official_name': account.get('official_name'),
                    'type': account.get('type'),
                    'subtype': account.get('subtype'),
                    'verification_status': account.get('verification_status')
                }
            }
        )
        
        self.db.add(payment_account)
        return payment_account

    async def get_account_balance(self, payment_account_id: uuid.UUID) -> dict[str, Any]:
        """
        Get real-time account balance from Plaid
        
        Args:
            payment_account_id: Payment account UUID
            
        Returns:
            Account balance information
        """
        try:
            # Get payment account
            stmt = select(UserPaymentAccount).where(UserPaymentAccount.id == payment_account_id)
            result = await self.db.execute(stmt)
            payment_account = result.scalar_one_or_none()
            
            if not payment_account:
                raise ValueError(f"Payment account {payment_account_id} not found")
                
            # Get balance from Plaid
            from plaid.model.accounts_balance_get_request import AccountsBalanceGetRequest
            
            balance_request = AccountsBalanceGetRequest(
                access_token=payment_account.plaid_access_token,
                options={
                    'account_ids': [payment_account.plaid_account_id]
                }
            )
            
            balance_response = self.client.accounts_balance_get(balance_request)
            
            if not balance_response['accounts']:
                raise ValueError("Account not found in Plaid response")
                
            account = balance_response['accounts'][0]
            balances = account['balances']
            
            return {
                'account_id': str(payment_account_id),
                'available_balance': balances.get('available'),
                'current_balance': balances.get('current'),
                'currency': balances.get('iso_currency_code', 'USD'),
                'last_updated': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get balance for account {payment_account_id}: {str(e)}")
            raise Exception(f"Failed to retrieve account balance: {str(e)}")

    async def get_user_payment_accounts(self, user_phone: str) -> list[dict[str, Any]]:
        """
        Get all payment accounts for a user
        
        Args:
            user_phone: User's phone number
            
        Returns:
            List of payment accounts
        """
        try:
            stmt = select(UserPaymentAccount).where(
                UserPaymentAccount.user_phone == user_phone,
                UserPaymentAccount.deleted_at.is_(None)
            ).order_by(UserPaymentAccount.is_primary.desc(), UserPaymentAccount.created_at.desc())
            
            result = await self.db.execute(stmt)
            accounts = result.scalars().all()
            
            return [
                {
                    'id': str(account.id),
                    'account_name': account.account_name,
                    'account_type': account.account_type,
                    'account_subtype': account.account_subtype,
                    'account_mask': account.account_mask,
                    'institution_name': account.institution_name,
                    'status': account.status.value,
                    'is_verified': account.is_verified,
                    'is_primary': account.is_primary,
                    'can_deposit': account.can_deposit,
                    'can_withdraw': account.can_withdraw,
                    'created_at': account.created_at.isoformat(),
                }
                for account in accounts
            ]
            
        except Exception as e:
            logger.error(f"Failed to get payment accounts for user {user_phone}: {str(e)}")
            raise Exception(f"Failed to retrieve payment accounts: {str(e)}")

    async def remove_payment_account(self, user_phone: str, payment_account_id: uuid.UUID) -> bool:
        """
        Soft delete a payment account
        
        Args:
            user_phone: User's phone number
            payment_account_id: Account to remove
            
        Returns:
            True if successful
        """
        try:
            stmt = select(UserPaymentAccount).where(
                UserPaymentAccount.id == payment_account_id,
                UserPaymentAccount.user_phone == user_phone,
                UserPaymentAccount.deleted_at.is_(None)
            )
            result = await self.db.execute(stmt)
            account = result.scalar_one_or_none()
            
            if not account:
                raise ValueError(f"Payment account {payment_account_id} not found")
                
            # Soft delete
            account.deleted_at = datetime.utcnow()
            
            # If this was the primary account, make another account primary
            if account.is_primary:
                stmt = select(UserPaymentAccount).where(
                    UserPaymentAccount.user_phone == user_phone,
                    UserPaymentAccount.deleted_at.is_(None),
                    UserPaymentAccount.id != payment_account_id
                ).limit(1)
                result = await self.db.execute(stmt)
                next_account = result.scalar_one_or_none()
                
                if next_account:
                    next_account.is_primary = True
                    
            await self.db.commit()
            
            logger.info(f"Removed payment account {payment_account_id} for user {user_phone}")
            return True
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to remove payment account {payment_account_id}: {str(e)}")
            raise Exception(f"Failed to remove payment account: {str(e)}")