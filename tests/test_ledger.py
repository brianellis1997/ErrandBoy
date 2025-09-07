"""Tests for the ledger service micropayment system"""

import uuid
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from groupchat.db.models import (
    Citation,
    CompiledAnswer,
    Contact,
    ContactStatus,
    Contribution,
    Ledger,
    LedgerEntryType,
    PayoutSplit,
    Query,
    QueryStatus,
    TransactionType,
)
from groupchat.services.ledger import LedgerService


@pytest.fixture
async def ledger_service(test_db):
    """Create a ledger service instance"""
    return LedgerService(test_db)


@pytest.fixture
async def sample_query(test_db):
    """Create a sample query for testing"""
    query = Query(
        id=uuid.uuid4(),
        user_phone="+1234567890",
        question_text="What's the weather like?",
        status=QueryStatus.COMPLETED,
        total_cost_cents=500,  # $5.00
        platform_fee_cents=100,  # $1.00
        max_experts=3,
        min_experts=2,
        timeout_minutes=30
    )
    test_db.add(query)
    await test_db.commit()
    await test_db.refresh(query)
    return query


@pytest.fixture
async def sample_contacts(test_db):
    """Create sample contacts for testing"""
    contacts = []
    for i in range(3):
        contact = Contact(
            id=uuid.uuid4(),
            phone_number=f"+123456789{i}",
            name=f"Test Expert {i+1}",
            bio=f"Expert in area {i+1}",
            status=ContactStatus.ACTIVE,
            trust_score=0.8,
            total_earnings_cents=0,
            total_contributions=0
        )
        test_db.add(contact)
        contacts.append(contact)
    
    await test_db.commit()
    for contact in contacts:
        await test_db.refresh(contact)
    return contacts


@pytest.fixture
async def sample_contributions_and_citations(test_db, sample_query, sample_contacts):
    """Create sample contributions and citations for testing"""
    compiled_answer = CompiledAnswer(
        id=uuid.uuid4(),
        query_id=sample_query.id,
        final_answer="The weather is sunny with [@expert1] reporting 75°F and [@expert2] confirming clear skies.",
        summary="Sunny weather, 75°F",
        confidence_score=0.85,
        compilation_method="gpt-4",
        compilation_tokens_used=150
    )
    test_db.add(compiled_answer)
    
    # Create contributions
    contributions = []
    for i, contact in enumerate(sample_contacts):
        contribution = Contribution(
            id=uuid.uuid4(),
            query_id=sample_query.id,
            contact_id=contact.id,
            response_text=f"Weather response from expert {i+1}",
            confidence_score=0.8 + (i * 0.1),  # Varying confidence
            requested_at=sample_query.created_at,
            responded_at=sample_query.created_at,
            was_used=False,
            payout_amount_cents=0
        )
        test_db.add(contribution)
        contributions.append(contribution)
    
    await test_db.commit()
    await test_db.refresh(compiled_answer)
    
    # Create citations with different weights
    citations = []
    citation_weights = [0.5, 0.3, 0.2]  # Different citation importance
    
    for i, (contribution, weight) in enumerate(zip(contributions, citation_weights)):
        citation = Citation(
            id=uuid.uuid4(),
            compiled_answer_id=compiled_answer.id,
            contribution_id=contribution.id,
            claim_text=f"Weather claim {i+1}",
            source_excerpt=f"Source excerpt {i+1}",
            position_in_answer=i,
            confidence=weight  # Using confidence as weight
        )
        test_db.add(citation)
        citations.append(citation)
    
    await test_db.commit()
    
    return {
        "compiled_answer": compiled_answer,
        "contributions": contributions,
        "citations": citations
    }


class TestLedgerService:
    """Test cases for LedgerService"""

    async def test_process_query_payment_basic(
        self,
        ledger_service,
        sample_query,
        sample_contributions_and_citations
    ):
        """Test basic payment processing"""
        compiled_answer = sample_contributions_and_citations["compiled_answer"]
        
        result = await ledger_service.process_query_payment(
            query_id=sample_query.id,
            compiled_answer_id=compiled_answer.id
        )
        
        assert result["success"] is True
        assert result["total_amount_cents"] == 500
        assert result["contributor_pool_cents"] == 350  # 70% of 500
        assert result["platform_fee_cents"] == 100  # 20% of 500
        assert result["referral_bonus_cents"] == 50  # 10% of 500
        assert result["contributors_paid"] == 3

    async def test_payment_splits_calculation(
        self,
        ledger_service,
        sample_contributions_and_citations
    ):
        """Test payment split calculations"""
        citations_data = [
            (sample_contributions_and_citations["citations"][i], None)
            for i in range(3)
        ]
        
        splits = ledger_service._calculate_payment_splits(500, citations_data)
        
        assert splits["total_amount"] == 500
        assert splits["contributor_pool_total"] == 350
        assert splits["platform_fee"] == 100
        assert splits["referral_bonus"] == 50
        
        # Check individual contributor payouts based on weights
        contributors = splits["contributors"]
        assert len(contributors) == 3
        
        # Weights should be [0.5, 0.3, 0.2] normalized
        expected_payouts = [175, 105, 70]  # 50%, 30%, 20% of 350
        actual_payouts = [c["payout_cents"] for c in contributors]
        
        assert actual_payouts == expected_payouts

    async def test_double_entry_bookkeeping(
        self,
        ledger_service,
        sample_query,
        sample_contributions_and_citations,
        test_db
    ):
        """Test that all transactions are properly balanced"""
        compiled_answer = sample_contributions_and_citations["compiled_answer"]
        
        result = await ledger_service.process_query_payment(
            query_id=sample_query.id,
            compiled_answer_id=compiled_answer.id
        )
        
        transaction_id = uuid.UUID(result["transaction_id"])
        
        # Validate transaction balance
        validation = await ledger_service.validate_transaction_balance(transaction_id)
        
        assert validation["is_balanced"] is True
        assert validation["total_debits_cents"] == validation["total_credits_cents"]
        assert validation["difference_cents"] == 0

    async def test_user_balance_calculation(
        self,
        ledger_service,
        sample_query,
        sample_contributions_and_citations,
        sample_contacts
    ):
        """Test user balance calculation"""
        compiled_answer = sample_contributions_and_citations["compiled_answer"]
        
        # Process payment
        await ledger_service.process_query_payment(
            query_id=sample_query.id,
            compiled_answer_id=compiled_answer.id
        )
        
        # Check user balance (should be debited)
        user_balance = await ledger_service.get_user_balance("user", sample_query.user_phone)
        assert user_balance["balance_cents"] == -500  # User paid $5.00
        
        # Check platform balance
        platform_balance = await ledger_service.get_user_balance("platform", "platform_revenue")
        assert platform_balance["balance_cents"] == 100  # Platform earned $1.00
        
        # Check first contributor balance (highest weight = 50% of 350 = 175 cents)
        contact_id = str(sample_contacts[0].id)
        contributor_balance = await ledger_service.get_user_balance(
            "contributor", 
            f"contact_{contact_id}"
        )
        assert contributor_balance["balance_cents"] == 175

    async def test_contributor_earnings_update(
        self,
        ledger_service,
        sample_query,
        sample_contributions_and_citations,
        sample_contacts,
        test_db
    ):
        """Test that contributor earnings are properly updated"""
        compiled_answer = sample_contributions_and_citations["compiled_answer"]
        
        # Get initial earnings
        initial_earnings = [c.total_earnings_cents for c in sample_contacts]
        initial_contributions = [c.total_contributions for c in sample_contacts]
        
        # Process payment
        await ledger_service.process_query_payment(
            query_id=sample_query.id,
            compiled_answer_id=compiled_answer.id
        )
        
        # Refresh contacts and check updated earnings
        for contact in sample_contacts:
            await test_db.refresh(contact)
        
        # Check that earnings increased
        for i, contact in enumerate(sample_contacts):
            assert contact.total_earnings_cents > initial_earnings[i]
            assert contact.total_contributions == initial_contributions[i] + 1

    async def test_payout_split_record_creation(
        self,
        ledger_service,
        sample_query,
        sample_contributions_and_citations,
        test_db
    ):
        """Test that payout split records are created"""
        compiled_answer = sample_contributions_and_citations["compiled_answer"]
        
        # Process payment
        await ledger_service.process_query_payment(
            query_id=sample_query.id,
            compiled_answer_id=compiled_answer.id
        )
        
        # Check that payout split record was created
        from sqlalchemy import select
        stmt = select(PayoutSplit).where(PayoutSplit.query_id == sample_query.id)
        result = await test_db.execute(stmt)
        payout_split = result.scalar_one_or_none()
        
        assert payout_split is not None
        assert payout_split.total_amount_cents == 500
        assert payout_split.contributor_pool_cents == 350
        assert payout_split.platform_fee_cents == 100
        assert payout_split.referral_bonus_cents == 50
        assert payout_split.is_processed is True
        assert len(payout_split.distribution) == 3

    async def test_transaction_history(
        self,
        ledger_service,
        sample_query,
        sample_contributions_and_citations
    ):
        """Test transaction history retrieval"""
        compiled_answer = sample_contributions_and_citations["compiled_answer"]
        
        # Process payment
        result = await ledger_service.process_query_payment(
            query_id=sample_query.id,
            compiled_answer_id=compiled_answer.id
        )
        
        transaction_id = uuid.UUID(result["transaction_id"])
        
        # Get transaction history for this transaction
        history = await ledger_service.get_transaction_history(
            transaction_id=transaction_id
        )
        
        assert len(history) == 5  # 1 debit + 4 credits (platform + referral + 2 contributors)
        
        # Check that we have one debit and multiple credits
        debits = [t for t in history if t["entry_type"] == "debit"]
        credits = [t for t in history if t["entry_type"] == "credit"]
        
        assert len(debits) == 1
        assert len(credits) == 4
        
        # Verify amounts
        total_debits = sum(t["amount_cents"] for t in debits)
        total_credits = sum(t["amount_cents"] for t in credits)
        assert total_debits == total_credits == 500

    async def test_no_citations_handling(
        self,
        ledger_service,
        sample_query,
        test_db
    ):
        """Test handling of queries with no citations"""
        # Create compiled answer without citations
        compiled_answer = CompiledAnswer(
            id=uuid.uuid4(),
            query_id=sample_query.id,
            final_answer="Answer with no citations",
            summary="No citations",
            confidence_score=0.5,
            compilation_method="gpt-4",
            compilation_tokens_used=100
        )
        test_db.add(compiled_answer)
        await test_db.commit()
        
        # Process payment should handle gracefully
        result = await ledger_service.process_query_payment(
            query_id=sample_query.id,
            compiled_answer_id=compiled_answer.id
        )
        
        assert result["success"] is False
        assert "No citations" in result["message"]

    async def test_rounding_precision(
        self,
        ledger_service,
        sample_contributions_and_citations
    ):
        """Test that payment splits handle rounding correctly"""
        # Create citations with weights that don't divide evenly
        citations_data = []
        for i in range(3):
            citation = sample_contributions_and_citations["citations"][i]
            citation.confidence = 1.0 / 3.0  # This will cause rounding issues
            citations_data.append((citation, None))
        
        splits = ledger_service._calculate_payment_splits(100, citations_data)
        
        # Check that all cents are accounted for
        total_contributor_payout = sum(c["payout_cents"] for c in splits["contributors"])
        assert total_contributor_payout == 70  # 70% of 100

    async def test_invalid_query_handling(
        self,
        ledger_service
    ):
        """Test handling of invalid query IDs"""
        fake_query_id = uuid.uuid4()
        fake_answer_id = uuid.uuid4()
        
        with pytest.raises(ValueError, match="Query .* not found"):
            await ledger_service.process_query_payment(fake_query_id, fake_answer_id)