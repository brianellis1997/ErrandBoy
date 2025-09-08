"""Stripe Connect service for expert payouts and account management"""

import logging
import uuid
from datetime import datetime, timedelta
from typing import Any

import stripe
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from groupchat.config import settings
from groupchat.db.models import Contact, StripeConnectedAccount

logger = logging.getLogger(__name__)


class StripeConnectService:
    """Service for Stripe Connect integration and expert payouts"""

    def __init__(self, db: AsyncSession):
        self.db = db
        
        # Configure Stripe
        stripe.api_key = settings.stripe_secret_key
        self.stripe_client = stripe

    async def create_connected_account(self, contact_id: uuid.UUID) -> dict[str, Any]:
        """
        Create a Stripe Connect Express account for an expert
        
        Args:
            contact_id: Expert's contact ID
            
        Returns:
            Account creation details and onboarding URL
        """
        try:
            # Get contact information
            stmt = select(Contact).where(Contact.id == contact_id)
            result = await self.db.execute(stmt)
            contact = result.scalar_one_or_none()
            
            if not contact:
                raise ValueError(f"Contact {contact_id} not found")
                
            # Check if account already exists
            stmt = select(StripeConnectedAccount).where(
                StripeConnectedAccount.contact_id == contact_id
            )
            result = await self.db.execute(stmt)
            existing_account = result.scalar_one_or_none()
            
            if existing_account:
                # Return existing account info
                return await self._get_account_info(existing_account)
                
            # Create Stripe Connect Express account
            account_data = {
                'type': 'express',
                'country': 'US',  # Default to US, can be configured per expert
                'email': contact.email,
                'capabilities': {
                    'transfers': {'requested': True},
                },
                'business_profile': {
                    'mcc': '7372',  # Computer programming services
                    'product_description': 'Expert knowledge and consultation services'
                },
                'metadata': {
                    'contact_id': str(contact_id),
                    'phone': contact.phone_number,
                    'groupchat_expert': 'true'
                }
            }
            
            stripe_account = self.stripe_client.Account.create(**account_data)
            
            # Save to database
            connected_account = StripeConnectedAccount(
                id=uuid.uuid4(),
                contact_id=contact_id,
                stripe_account_id=stripe_account['id'],
                stripe_account_type='express',
                charges_enabled=stripe_account.get('charges_enabled', False),
                payouts_enabled=stripe_account.get('payouts_enabled', False),
                details_submitted=stripe_account.get('details_submitted', False),
                onboarding_completed=False,
                requirements_currently_due=stripe_account.get('requirements', {}).get('currently_due', []),
                requirements_eventually_due=stripe_account.get('requirements', {}).get('eventually_due', []),
                extra_metadata={
                    'stripe_account_data': {
                        'created': stripe_account.get('created'),
                        'default_currency': stripe_account.get('default_currency'),
                        'country': stripe_account.get('country')
                    }
                }
            )
            
            self.db.add(connected_account)
            await self.db.commit()
            
            logger.info(f"Created Stripe Connect account {stripe_account['id']} for contact {contact_id}")
            
            return await self._get_account_info(connected_account)
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to create Stripe Connect account for contact {contact_id}: {str(e)}")
            raise Exception(f"Failed to create payment account: {str(e)}")

    async def create_account_link(self, contact_id: uuid.UUID) -> dict[str, Any]:
        """
        Create an account link for onboarding or re-authentication
        
        Args:
            contact_id: Expert's contact ID
            
        Returns:
            Account link URL and expiration
        """
        try:
            stmt = select(StripeConnectedAccount).where(
                StripeConnectedAccount.contact_id == contact_id
            )
            result = await self.db.execute(stmt)
            connected_account = result.scalar_one_or_none()
            
            if not connected_account:
                raise ValueError(f"No Stripe account found for contact {contact_id}")
                
            # Create account link
            account_link = self.stripe_client.AccountLink.create(
                account=connected_account.stripe_account_id,
                refresh_url=f"{settings.app_host}/expert?refresh=true",
                return_url=f"{settings.app_host}/expert?success=true",
                type='account_onboarding'
            )
            
            # Update database with new onboarding URL
            connected_account.onboarding_url = account_link['url']
            connected_account.onboarding_expires_at = datetime.utcnow() + timedelta(minutes=55)
            
            await self.db.commit()
            
            logger.info(f"Created account link for contact {contact_id}")
            
            return {
                'url': account_link['url'],
                'expires_at': account_link['expires_at'],
                'created': account_link['created']
            }
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to create account link for contact {contact_id}: {str(e)}")
            raise Exception(f"Failed to create onboarding link: {str(e)}")

    async def get_account_status(self, contact_id: uuid.UUID) -> dict[str, Any]:
        """
        Get current status of expert's Stripe Connect account
        
        Args:
            contact_id: Expert's contact ID
            
        Returns:
            Account status and requirements
        """
        try:
            stmt = select(StripeConnectedAccount).where(
                StripeConnectedAccount.contact_id == contact_id
            )
            result = await self.db.execute(stmt)
            connected_account = result.scalar_one_or_none()
            
            if not connected_account:
                return {
                    'has_account': False,
                    'needs_onboarding': True
                }
                
            # Get fresh data from Stripe
            stripe_account = self.stripe_client.Account.retrieve(
                connected_account.stripe_account_id
            )
            
            # Update local record
            connected_account.charges_enabled = stripe_account.get('charges_enabled', False)
            connected_account.payouts_enabled = stripe_account.get('payouts_enabled', False)
            connected_account.details_submitted = stripe_account.get('details_submitted', False)
            connected_account.requirements_currently_due = stripe_account.get('requirements', {}).get('currently_due', [])
            connected_account.requirements_eventually_due = stripe_account.get('requirements', {}).get('eventually_due', [])
            connected_account.requirements_disabled_reason = stripe_account.get('requirements', {}).get('disabled_reason')
            
            # Check if onboarding is complete
            requirements = stripe_account.get('requirements', {})
            onboarding_completed = (
                len(requirements.get('currently_due', [])) == 0 and
                stripe_account.get('details_submitted', False) and
                stripe_account.get('payouts_enabled', False)
            )
            
            connected_account.onboarding_completed = onboarding_completed
            
            await self.db.commit()
            
            return {
                'has_account': True,
                'account_id': connected_account.stripe_account_id,
                'onboarding_completed': onboarding_completed,
                'payouts_enabled': connected_account.payouts_enabled,
                'charges_enabled': connected_account.charges_enabled,
                'details_submitted': connected_account.details_submitted,
                'requirements': {
                    'currently_due': connected_account.requirements_currently_due,
                    'eventually_due': connected_account.requirements_eventually_due,
                    'disabled_reason': connected_account.requirements_disabled_reason
                },
                'needs_onboarding': not onboarding_completed,
                'created_at': connected_account.created_at.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get account status for contact {contact_id}: {str(e)}")
            raise Exception(f"Failed to retrieve account status: {str(e)}")

    async def process_payout(
        self, 
        contact_id: uuid.UUID, 
        amount_cents: int, 
        description: str,
        metadata: dict[str, Any] = None
    ) -> dict[str, Any]:
        """
        Process a payout to an expert's connected account
        
        Args:
            contact_id: Expert's contact ID
            amount_cents: Amount in cents
            description: Payout description
            metadata: Additional metadata
            
        Returns:
            Payout details
        """
        try:
            stmt = select(StripeConnectedAccount).where(
                StripeConnectedAccount.contact_id == contact_id
            )
            result = await self.db.execute(stmt)
            connected_account = result.scalar_one_or_none()
            
            if not connected_account:
                raise ValueError(f"No Stripe account found for contact {contact_id}")
                
            if not connected_account.payouts_enabled:
                raise ValueError(f"Payouts not enabled for contact {contact_id}")
                
            # Create transfer to connected account
            transfer = self.stripe_client.Transfer.create(
                amount=amount_cents,
                currency='usd',
                destination=connected_account.stripe_account_id,
                description=description,
                metadata={
                    'contact_id': str(contact_id),
                    'groupchat_payout': 'true',
                    **(metadata or {})
                }
            )
            
            logger.info(f"Created Stripe transfer {transfer['id']} for contact {contact_id}: ${amount_cents/100:.2f}")
            
            return {
                'transfer_id': transfer['id'],
                'amount_cents': amount_cents,
                'amount_dollars': amount_cents / 100.0,
                'currency': transfer['currency'],
                'destination_account': connected_account.stripe_account_id,
                'status': transfer['status'],
                'created': transfer['created'],
                'description': description
            }
            
        except Exception as e:
            logger.error(f"Failed to process payout for contact {contact_id}: {str(e)}")
            raise Exception(f"Failed to process payout: {str(e)}")

    async def get_payout_history(self, contact_id: uuid.UUID, limit: int = 20) -> list[dict[str, Any]]:
        """
        Get payout history for an expert
        
        Args:
            contact_id: Expert's contact ID
            limit: Number of payouts to retrieve
            
        Returns:
            List of payout records
        """
        try:
            stmt = select(StripeConnectedAccount).where(
                StripeConnectedAccount.contact_id == contact_id
            )
            result = await self.db.execute(stmt)
            connected_account = result.scalar_one_or_none()
            
            if not connected_account:
                raise ValueError(f"No Stripe account found for contact {contact_id}")
                
            # Get transfers to this account
            transfers = self.stripe_client.Transfer.list(
                destination=connected_account.stripe_account_id,
                limit=limit
            )
            
            return [
                {
                    'transfer_id': transfer['id'],
                    'amount_cents': transfer['amount'],
                    'amount_dollars': transfer['amount'] / 100.0,
                    'currency': transfer['currency'],
                    'status': transfer['status'],
                    'created': datetime.fromtimestamp(transfer['created']).isoformat(),
                    'description': transfer.get('description', ''),
                    'metadata': transfer.get('metadata', {})
                }
                for transfer in transfers['data']
            ]
            
        except Exception as e:
            logger.error(f"Failed to get payout history for contact {contact_id}: {str(e)}")
            raise Exception(f"Failed to retrieve payout history: {str(e)}")

    async def handle_account_webhook(self, event: dict[str, Any]) -> dict[str, Any]:
        """
        Handle Stripe Connect account webhooks
        
        Args:
            event: Stripe webhook event
            
        Returns:
            Processing results
        """
        try:
            event_type = event['type']
            account_id = event['data']['object']['id']
            
            logger.info(f"Processing Stripe Connect webhook: {event_type} for account {account_id}")
            
            # Find connected account
            stmt = select(StripeConnectedAccount).where(
                StripeConnectedAccount.stripe_account_id == account_id
            )
            result = await self.db.execute(stmt)
            connected_account = result.scalar_one_or_none()
            
            if not connected_account:
                logger.warning(f"Received webhook for unknown account {account_id}")
                return {'status': 'ignored', 'reason': 'account_not_found'}
                
            if event_type == 'account.updated':
                account_data = event['data']['object']
                
                # Update account status
                connected_account.charges_enabled = account_data.get('charges_enabled', False)
                connected_account.payouts_enabled = account_data.get('payouts_enabled', False)
                connected_account.details_submitted = account_data.get('details_submitted', False)
                connected_account.requirements_currently_due = account_data.get('requirements', {}).get('currently_due', [])
                connected_account.requirements_eventually_due = account_data.get('requirements', {}).get('eventually_due', [])
                connected_account.requirements_disabled_reason = account_data.get('requirements', {}).get('disabled_reason')
                
                # Check if onboarding completed
                requirements = account_data.get('requirements', {})
                onboarding_completed = (
                    len(requirements.get('currently_due', [])) == 0 and
                    account_data.get('details_submitted', False) and
                    account_data.get('payouts_enabled', False)
                )
                
                connected_account.onboarding_completed = onboarding_completed
                
                await self.db.commit()
                
                logger.info(f"Updated account status for {account_id}: onboarding_completed={onboarding_completed}")
                
            return {
                'status': 'processed',
                'event_type': event_type,
                'account_id': account_id
            }
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to process Stripe Connect webhook: {str(e)}")
            raise Exception(f"Failed to process webhook: {str(e)}")

    async def _get_account_info(self, connected_account: StripeConnectedAccount) -> dict[str, Any]:
        """Get formatted account information"""
        return {
            'account_id': connected_account.stripe_account_id,
            'contact_id': str(connected_account.contact_id),
            'onboarding_completed': connected_account.onboarding_completed,
            'payouts_enabled': connected_account.payouts_enabled,
            'charges_enabled': connected_account.charges_enabled,
            'details_submitted': connected_account.details_submitted,
            'onboarding_url': connected_account.onboarding_url,
            'onboarding_expires_at': connected_account.onboarding_expires_at.isoformat() if connected_account.onboarding_expires_at else None,
            'requirements': {
                'currently_due': connected_account.requirements_currently_due,
                'eventually_due': connected_account.requirements_eventually_due,
                'disabled_reason': connected_account.requirements_disabled_reason
            },
            'created_at': connected_account.created_at.isoformat()
        }