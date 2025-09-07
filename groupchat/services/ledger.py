"""Micropayment ledger service with double-entry bookkeeping"""

import logging
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from groupchat.config import settings
from groupchat.db.models import (
    Citation,
    CompiledAnswer,
    Contact,
    Ledger,
    LedgerEntryType,
    PayoutSplit,
    Query,
    TransactionType,
)

logger = logging.getLogger(__name__)


class LedgerService:
    """Service for micropayment ledger with double-entry bookkeeping"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def process_query_payment(
        self,
        query_id: uuid.UUID,
        compiled_answer_id: uuid.UUID
    ) -> dict[str, Any]:
        """
        Process payment for a completed query with citations
        
        Args:
            query_id: The completed query
            compiled_answer_id: The synthesized answer with citations
            
        Returns:
            Payment processing results
        """
        # Get query details
        query = await self._get_query(query_id)
        if not query:
            raise ValueError(f"Query {query_id} not found")

        # Get citations with weights
        citations = await self._get_citations_with_weights(compiled_answer_id)
        if not citations:
            logger.warning(f"No citations found for answer {compiled_answer_id}")
            return {"success": False, "message": "No citations to process payments for"}

        # Calculate payment splits
        payment_amount_cents = query.total_cost_cents or int(settings.query_price_cents * 100)
        splits = self._calculate_payment_splits(payment_amount_cents, citations)

        # Create transaction ID for this payment
        transaction_id = uuid.uuid4()

        # Create double-entry ledger transactions
        await self._create_payment_transactions(
            transaction_id=transaction_id,
            query_id=query_id,
            splits=splits
        )

        # Create payout split record
        await self._create_payout_split_record(
            query_id=query_id,
            splits=splits
        )

        # Update contributor earnings
        await self._update_contributor_earnings(citations, splits["contributors"])

        await self.db.commit()

        logger.info(f"Processed payment for query {query_id}, transaction {transaction_id}")

        return {
            "success": True,
            "transaction_id": transaction_id,
            "total_amount_cents": payment_amount_cents,
            "contributor_pool_cents": splits["contributor_pool_total"],
            "platform_fee_cents": splits["platform_fee"],
            "referral_bonus_cents": splits["referral_bonus"],
            "contributors_paid": len(splits["contributors"])
        }

    def _calculate_payment_splits(
        self,
        total_amount_cents: int,
        citations: list[tuple[Citation, Contact | None]]
    ) -> dict[str, Any]:
        """Calculate payment splits based on citation weights"""
        
        # Calculate pools
        contributor_pool = int(total_amount_cents * settings.contributor_pool_percentage)
        platform_fee = int(total_amount_cents * settings.platform_percentage)
        referral_bonus = int(total_amount_cents * settings.referrer_percentage)

        # Calculate total citation weight
        total_weight = sum(citation.confidence for citation, _ in citations)
        
        if total_weight == 0:
            logger.warning("Total citation weight is 0, using equal distribution")
            weight_per_citation = 1.0 / len(citations) if citations else 0
        else:
            weight_per_citation = None

        # Calculate individual contributor payouts
        contributors = []
        remaining_pool = contributor_pool
        
        for i, (citation, contact) in enumerate(citations):
            if weight_per_citation:
                weight = weight_per_citation
            else:
                weight = citation.confidence / total_weight
            
            # For last contributor, give remaining to avoid rounding issues
            if i == len(citations) - 1:
                payout_cents = remaining_pool
            else:
                payout_cents = int(contributor_pool * weight)
                remaining_pool -= payout_cents

            contributors.append({
                "citation_id": citation.id,
                "contribution_id": citation.contribution_id,
                "contact_id": contact.id if contact else None,
                "weight": weight,
                "payout_cents": payout_cents
            })

        return {
            "total_amount": total_amount_cents,
            "contributor_pool_total": contributor_pool,
            "platform_fee": platform_fee,
            "referral_bonus": referral_bonus,
            "contributors": contributors
        }

    async def _create_payment_transactions(
        self,
        transaction_id: uuid.UUID,
        query_id: uuid.UUID,
        splits: dict[str, Any]
    ) -> None:
        """Create double-entry ledger transactions for payment"""
        
        query = await self._get_query(query_id)
        
        # 1. Debit user account for total payment
        await self._create_ledger_entry(
            transaction_id=transaction_id,
            transaction_type=TransactionType.QUERY_PAYMENT,
            account_type="user",
            account_id=query.user_phone,
            entry_type=LedgerEntryType.DEBIT,
            amount_cents=splits["total_amount"],
            query_id=query_id,
            description=f"Payment for query {query_id}"
        )

        # 2. Credit platform fee account
        await self._create_ledger_entry(
            transaction_id=transaction_id,
            transaction_type=TransactionType.PLATFORM_FEE,
            account_type="platform",
            account_id="platform_revenue",
            entry_type=LedgerEntryType.CREDIT,
            amount_cents=splits["platform_fee"],
            query_id=query_id,
            description=f"Platform fee for query {query_id}"
        )

        # 3. Credit referral bonus account (if applicable)
        if splits["referral_bonus"] > 0:
            await self._create_ledger_entry(
                transaction_id=transaction_id,
                transaction_type=TransactionType.REFERRAL_BONUS,
                account_type="referral",
                account_id="referral_pool",
                entry_type=LedgerEntryType.CREDIT,
                amount_cents=splits["referral_bonus"],
                query_id=query_id,
                description=f"Referral bonus for query {query_id}"
            )

        # 4. Credit each contributor's account
        for contributor in splits["contributors"]:
            if contributor["payout_cents"] > 0:
                contact_account = f"contact_{contributor['contact_id']}" if contributor['contact_id'] else "anonymous"
                
                await self._create_ledger_entry(
                    transaction_id=transaction_id,
                    transaction_type=TransactionType.CONTRIBUTION_PAYOUT,
                    account_type="contributor",
                    account_id=contact_account,
                    entry_type=LedgerEntryType.CREDIT,
                    amount_cents=contributor["payout_cents"],
                    query_id=query_id,
                    contact_id=contributor["contact_id"],
                    description=f"Contribution payout for query {query_id}",
                    extra_metadata={
                        "citation_id": str(contributor["citation_id"]),
                        "contribution_id": str(contributor["contribution_id"]),
                        "weight": contributor["weight"]
                    }
                )

    async def _create_payout_split_record(
        self,
        query_id: uuid.UUID,
        splits: dict[str, Any]
    ) -> None:
        """Create a payout split record for tracking"""
        
        # Format distribution for JSONB storage
        distribution = []
        for contributor in splits["contributors"]:
            distribution.append({
                "contact_id": str(contributor["contact_id"]) if contributor["contact_id"] else None,
                "contribution_id": str(contributor["contribution_id"]),
                "citation_id": str(contributor["citation_id"]),
                "weight": contributor["weight"],
                "payout_cents": contributor["payout_cents"]
            })

        payout_split = PayoutSplit(
            id=uuid.uuid4(),
            query_id=query_id,
            total_amount_cents=splits["total_amount"],
            contributor_pool_cents=splits["contributor_pool_total"],
            platform_fee_cents=splits["platform_fee"],
            referral_bonus_cents=splits["referral_bonus"],
            distribution=distribution,
            is_processed=True,
            processed_at=datetime.utcnow(),
            extra_metadata={}
        )

        self.db.add(payout_split)

    async def _update_contributor_earnings(
        self,
        citations: list[tuple[Citation, Contact | None]],
        contributor_splits: list[dict[str, Any]]
    ) -> None:
        """Update contributor total earnings"""
        
        # Create lookup for payouts by contact
        payout_by_contact = {}
        for split in contributor_splits:
            contact_id = split["contact_id"]
            if contact_id:
                payout_by_contact[contact_id] = payout_by_contact.get(contact_id, 0) + split["payout_cents"]

        # Update contact earnings
        for contact_id, payout_cents in payout_by_contact.items():
            stmt = select(Contact).where(Contact.id == contact_id)
            result = await self.db.execute(stmt)
            contact = result.scalar_one_or_none()
            
            if contact:
                contact.total_earnings_cents += payout_cents
                contact.total_contributions += 1

    async def get_user_balance(self, account_type: str, account_id: str) -> dict[str, Any]:
        """Get current balance for a user account"""
        
        # Sum all credits
        credit_stmt = (
            select(func.sum(Ledger.amount_cents))
            .where(Ledger.account_type == account_type)
            .where(Ledger.account_id == account_id)
            .where(Ledger.entry_type == LedgerEntryType.CREDIT)
        )
        credit_result = await self.db.execute(credit_stmt)
        total_credits = credit_result.scalar() or 0

        # Sum all debits
        debit_stmt = (
            select(func.sum(Ledger.amount_cents))
            .where(Ledger.account_type == account_type)
            .where(Ledger.account_id == account_id)
            .where(Ledger.entry_type == LedgerEntryType.DEBIT)
        )
        debit_result = await self.db.execute(debit_stmt)
        total_debits = debit_result.scalar() or 0

        balance_cents = total_credits - total_debits

        return {
            "account_type": account_type,
            "account_id": account_id,
            "balance_cents": balance_cents,
            "balance_dollars": balance_cents / 100.0,
            "total_credits_cents": total_credits,
            "total_debits_cents": total_debits
        }

    async def get_transaction_history(
        self,
        account_type: str | None = None,
        account_id: str | None = None,
        transaction_id: uuid.UUID | None = None,
        limit: int = 50
    ) -> list[dict[str, Any]]:
        """Get transaction history with optional filters"""
        
        stmt = select(Ledger).order_by(Ledger.created_at.desc()).limit(limit)
        
        if account_type:
            stmt = stmt.where(Ledger.account_type == account_type)
        if account_id:
            stmt = stmt.where(Ledger.account_id == account_id)
        if transaction_id:
            stmt = stmt.where(Ledger.transaction_id == transaction_id)

        result = await self.db.execute(stmt)
        entries = result.scalars().all()

        return [
            {
                "id": str(entry.id),
                "transaction_id": str(entry.transaction_id),
                "transaction_type": entry.transaction_type.value,
                "account_type": entry.account_type,
                "account_id": entry.account_id,
                "entry_type": entry.entry_type.value,
                "amount_cents": entry.amount_cents,
                "amount_dollars": entry.amount_cents / 100.0,
                "currency": entry.currency,
                "description": entry.description,
                "created_at": entry.created_at.isoformat(),
                "query_id": str(entry.query_id) if entry.query_id else None,
                "contact_id": str(entry.contact_id) if entry.contact_id else None,
                "extra_metadata": entry.extra_metadata
            }
            for entry in entries
        ]

    async def validate_transaction_balance(self, transaction_id: uuid.UUID) -> dict[str, Any]:
        """Validate that a transaction is balanced (debits = credits)"""
        
        # Sum debits
        debit_stmt = (
            select(func.sum(Ledger.amount_cents))
            .where(Ledger.transaction_id == transaction_id)
            .where(Ledger.entry_type == LedgerEntryType.DEBIT)
        )
        debit_result = await self.db.execute(debit_stmt)
        total_debits = debit_result.scalar() or 0

        # Sum credits
        credit_stmt = (
            select(func.sum(Ledger.amount_cents))
            .where(Ledger.transaction_id == transaction_id)
            .where(Ledger.entry_type == LedgerEntryType.CREDIT)
        )
        credit_result = await self.db.execute(credit_stmt)
        total_credits = credit_result.scalar() or 0

        is_balanced = total_debits == total_credits

        return {
            "transaction_id": str(transaction_id),
            "is_balanced": is_balanced,
            "total_debits_cents": total_debits,
            "total_credits_cents": total_credits,
            "difference_cents": total_debits - total_credits
        }

    async def _get_query(self, query_id: uuid.UUID) -> Query | None:
        """Get query by ID"""
        stmt = select(Query).where(Query.id == query_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_citations_with_weights(
        self,
        compiled_answer_id: uuid.UUID
    ) -> list[tuple[Citation, Contact | None]]:
        """Get citations with associated contacts"""
        
        # First get citations
        citation_stmt = select(Citation).where(Citation.compiled_answer_id == compiled_answer_id)
        citation_result = await self.db.execute(citation_stmt)
        citations = citation_result.scalars().all()
        
        if not citations:
            return []
        
        # Then get contacts for each citation through contributions
        results = []
        for citation in citations:
            # Get the contribution to find the contact
            from groupchat.db.models import Contribution
            contrib_stmt = (
                select(Contact)
                .join(Contribution, Contact.id == Contribution.contact_id)
                .where(Contribution.id == citation.contribution_id)
            )
            contact_result = await self.db.execute(contrib_stmt)
            contact = contact_result.scalar_one_or_none()
            
            results.append((citation, contact))
        
        return results

    async def _create_ledger_entry(
        self,
        transaction_id: uuid.UUID,
        transaction_type: TransactionType,
        account_type: str,
        account_id: str,
        entry_type: LedgerEntryType,
        amount_cents: int,
        query_id: uuid.UUID | None = None,
        contact_id: uuid.UUID | None = None,
        description: str = "",
        extra_metadata: dict[str, Any] | None = None
    ) -> None:
        """Create a ledger entry"""
        
        entry = Ledger(
            id=uuid.uuid4(),
            transaction_id=transaction_id,
            transaction_type=transaction_type,
            account_type=account_type,
            account_id=account_id,
            entry_type=entry_type,
            amount_cents=amount_cents,
            query_id=query_id,
            contact_id=contact_id,
            description=description,
            extra_metadata=extra_metadata or {}
        )

        self.db.add(entry)
        logger.debug(f"Created ledger entry: {entry_type.value} ${amount_cents/100:.4f} for {account_type}:{account_id}")