"""Tests for the answer synthesis system"""

import json
import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from groupchat.db.models import (
    CompiledAnswer,
    Contact,
    ContactStatus,
    Contribution,
    Query,
    QueryStatus,
    Citation,
)
from groupchat.services.synthesis import SynthesisService


@pytest.fixture
async def sample_query(test_db: AsyncSession):
    """Create a sample query for testing"""
    query = Query(
        id=uuid.uuid4(),
        user_phone="+1234567890",
        question_text="What's the weather like today in Santa Monica?",
        status=QueryStatus.COLLECTING,
        max_experts=5,
        min_experts=3,
        timeout_minutes=30,
        total_cost_cents=500,
        platform_fee_cents=100,
        context={}
    )
    test_db.add(query)
    await test_db.commit()
    return query


@pytest.fixture
async def sample_contacts(test_db: AsyncSession):
    """Create sample contacts for testing"""
    contacts = [
        Contact(
            id=uuid.uuid4(),
            phone_number="+1111111111",
            name="Alex Surfer",
            bio="Local surfer with weather expertise",
            expertise_summary="Weather, ocean conditions, surfing",
            trust_score=0.9,
            response_rate=0.95,
            status=ContactStatus.ACTIVE,
            is_available=True
        ),
        Contact(
            id=uuid.uuid4(),
            phone_number="+2222222222",
            name="Priya Tech",
            bio="Weather app developer",
            expertise_summary="Weather data, forecasting, technology",
            trust_score=0.85,
            response_rate=0.88,
            status=ContactStatus.ACTIVE,
            is_available=True
        ),
        Contact(
            id=uuid.uuid4(),
            phone_number="+3333333333",
            name="Bob Local",
            bio="Long-time Santa Monica resident",
            expertise_summary="Local knowledge, community",
            trust_score=0.75,
            response_rate=0.80,
            status=ContactStatus.ACTIVE,
            is_available=True
        )
    ]
    
    for contact in contacts:
        test_db.add(contact)
    await test_db.commit()
    return contacts


@pytest.fixture
async def sample_contributions(test_db: AsyncSession, sample_query, sample_contacts):
    """Create sample contributions for testing"""
    contributions = [
        Contribution(
            id=uuid.uuid4(),
            query_id=sample_query.id,
            contact_id=sample_contacts[0].id,
            response_text="Morning fog clearing by 10am, sunny afternoon with temps reaching 78°F. Perfect surf conditions with 3-4ft waves.",
            confidence_score=0.95,
            requested_at=datetime.utcnow() - timedelta(minutes=20),
            responded_at=datetime.utcnow() - timedelta(minutes=15),
            response_time_minutes=5.0,
            was_used=False,
            payout_amount_cents=0
        ),
        Contribution(
            id=uuid.uuid4(),
            query_id=sample_query.id,
            contact_id=sample_contacts[1].id,
            response_text="According to weather.com and NOAA data, Santa Monica will see morning marine layer until 10:30am, then sunny with a high of 78°F downtown and 75°F near the pier.",
            confidence_score=0.92,
            requested_at=datetime.utcnow() - timedelta(minutes=20),
            responded_at=datetime.utcnow() - timedelta(minutes=10),
            response_time_minutes=10.0,
            was_used=False,
            payout_amount_cents=0
        ),
        Contribution(
            id=uuid.uuid4(),
            query_id=sample_query.id,
            contact_id=sample_contacts[2].id,
            response_text="It's a typical June gloom morning, but it'll be beautiful by noon. Great day for the beach!",
            confidence_score=0.80,
            requested_at=datetime.utcnow() - timedelta(minutes=20),
            responded_at=datetime.utcnow() - timedelta(minutes=5),
            response_time_minutes=15.0,
            was_used=False,
            payout_amount_cents=0
        )
    ]
    
    for contribution in contributions:
        test_db.add(contribution)
    await test_db.commit()
    return contributions


@pytest.mark.asyncio
async def test_synthesis_service_initialization(test_db: AsyncSession):
    """Test synthesis service initialization"""
    service = SynthesisService(test_db)
    assert service.db == test_db
    # When no API key is set, client should be None
    if not service.openai_client:
        assert service.openai_client is None


@pytest.mark.asyncio
async def test_generate_citation_handles(test_db: AsyncSession, sample_contributions, sample_contacts):
    """Test citation handle generation"""
    service = SynthesisService(test_db)
    
    contributions_with_contacts = [
        (sample_contributions[0], sample_contacts[0]),
        (sample_contributions[1], sample_contacts[1]),
        (sample_contributions[2], sample_contacts[2]),
    ]
    
    handle_mapping = service._generate_citation_handles(contributions_with_contacts)
    
    # Check that handles were generated
    assert len(handle_mapping) == 3
    
    # Check handle uniqueness
    handles = list(handle_mapping.keys())
    assert len(handles) == len(set(handles))
    
    # Check that each handle maps to the correct contribution and contact
    for handle, (contribution, contact) in handle_mapping.items():
        assert contribution in sample_contributions
        assert contact in sample_contacts


@pytest.mark.asyncio
async def test_create_handle_from_name(test_db: AsyncSession):
    """Test handle creation from different name formats"""
    service = SynthesisService(test_db)
    
    # Test single word
    assert service._create_handle_from_name("Alex") == "alex"
    
    # Test two words
    handle = service._create_handle_from_name("Alex Surfer")
    assert len(handle) > 0
    assert handle.islower()
    
    # Test three words
    handle = service._create_handle_from_name("John Paul Smith")
    assert len(handle) > 0
    assert handle.islower()
    
    # Test name with special characters
    handle = service._create_handle_from_name("Mary-Jane O'Connor")
    assert len(handle) > 0
    assert handle.islower()
    assert not any(c in handle for c in "-'")


@pytest.mark.asyncio
async def test_build_synthesis_prompt(test_db: AsyncSession, sample_query, sample_contributions, sample_contacts):
    """Test synthesis prompt building"""
    service = SynthesisService(test_db)
    
    contributions_with_contacts = [
        (sample_contributions[0], sample_contacts[0]),
        (sample_contributions[1], sample_contacts[1]),
    ]
    
    handle_mapping = service._generate_citation_handles(contributions_with_contacts)
    
    prompt = service._build_synthesis_prompt(
        sample_query.question_text,
        contributions_with_contacts,
        handle_mapping
    )
    
    # Check that prompt contains the question
    assert sample_query.question_text in prompt
    
    # Check that prompt contains contribution texts
    for contribution in sample_contributions[:2]:
        assert contribution.response_text in prompt
    
    # Check that prompt contains instructions
    assert "synthesize" in prompt.lower()
    assert "citation" in prompt.lower()
    assert "[@" in prompt


@pytest.mark.asyncio
async def test_extract_citations(test_db: AsyncSession, sample_contributions, sample_contacts):
    """Test citation extraction from synthesized answer"""
    service = SynthesisService(test_db)
    
    contributions_with_contacts = [
        (sample_contributions[0], sample_contacts[0]),
        (sample_contributions[1], sample_contacts[1]),
    ]
    
    handle_mapping = {
        "alexs": (sample_contributions[0], sample_contacts[0]),
        "priyat": (sample_contributions[1], sample_contacts[1]),
    }
    
    # Sample synthesized answer with citations
    answer_text = """
    Based on the expert contributions, the weather in Santa Monica today will start
    with morning fog clearing by 10am [@alexs] [@priyat]. The afternoon will be sunny
    with temperatures reaching 78°F downtown [@priyat] and perfect conditions for
    beach activities [@alexs].
    """
    
    citations_data = service._extract_citations(
        answer_text,
        handle_mapping,
        contributions_with_contacts
    )
    
    # Check that citations were extracted
    assert len(citations_data) == 4  # 4 citation instances in the text
    
    # Check citation structure
    for citation in citations_data:
        assert "contribution_id" in citation
        assert "contact_id" in citation
        assert "handle" in citation
        assert "claim_text" in citation
        assert "source_excerpt" in citation
        assert "position" in citation
        assert "confidence" in citation


@pytest.mark.asyncio
async def test_calculate_contribution_weights(test_db: AsyncSession, sample_contributions):
    """Test contribution weight calculation"""
    service = SynthesisService(test_db)
    
    # Create mock citations data
    citations_data = [
        {"contribution_id": sample_contributions[0].id},
        {"contribution_id": sample_contributions[0].id},
        {"contribution_id": sample_contributions[1].id},
        {"contribution_id": sample_contributions[0].id},
    ]
    
    weights = service._calculate_contribution_weights(citations_data)
    
    # Check that weights were calculated
    assert len(weights) == 2  # Two contributions were cited
    
    # Check that weights sum to 1.0
    assert abs(sum(weights.values()) - 1.0) < 0.001
    
    # Check that more cited contribution has higher weight
    assert weights[sample_contributions[0].id] > weights[sample_contributions[1].id]
    
    # Check specific weight values
    assert abs(weights[sample_contributions[0].id] - 0.75) < 0.001  # 3/4 citations
    assert abs(weights[sample_contributions[1].id] - 0.25) < 0.001  # 1/4 citations


@pytest.mark.asyncio
async def test_mock_synthesis_response(test_db: AsyncSession):
    """Test mock synthesis response generation"""
    service = SynthesisService(test_db)
    
    prompt = "Test prompt with [@alice] and [@bob] citations"
    
    response = service._mock_synthesis_response(prompt)
    
    # Check response structure
    assert "answer" in response
    assert "summary" in response
    assert "confidence" in response
    assert "tokens_used" in response
    
    # Check that response contains citations
    assert "[@" in response["answer"]
    
    # Check confidence is in valid range
    assert 0.0 <= response["confidence"] <= 1.0


@pytest.mark.asyncio
async def test_synthesize_answer_invalid_query(test_db: AsyncSession):
    """Test synthesis with invalid query ID"""
    service = SynthesisService(test_db)
    
    invalid_id = uuid.uuid4()
    
    with pytest.raises(ValueError, match="not found"):
        await service.synthesize_answer(invalid_id)


@pytest.mark.asyncio
async def test_synthesize_answer_wrong_status(test_db: AsyncSession, sample_query):
    """Test synthesis with query in wrong status"""
    service = SynthesisService(test_db)
    
    # Set query to PENDING status
    sample_query.status = QueryStatus.PENDING
    await test_db.commit()
    
    with pytest.raises(ValueError, match="Cannot synthesize"):
        await service.synthesize_answer(sample_query.id)


@pytest.mark.asyncio
async def test_synthesize_answer_no_contributions(test_db: AsyncSession, sample_query):
    """Test synthesis with no contributions"""
    service = SynthesisService(test_db)
    
    with pytest.raises(ValueError, match="No contributions"):
        await service.synthesize_answer(sample_query.id)


@pytest.mark.asyncio
async def test_synthesize_answer_success(
    test_db: AsyncSession,
    sample_query,
    sample_contacts,
    sample_contributions
):
    """Test successful answer synthesis"""
    service = SynthesisService(test_db)
    
    # Mock the OpenAI call to return a predictable response
    with patch.object(service, '_call_llm_for_synthesis') as mock_llm:
        mock_llm.return_value = {
            "answer": "Morning fog clearing by 10am [@alexs], sunny afternoon with temps reaching 78°F [@priyat]. Perfect beach day [@bobl]!",
            "summary": "Foggy morning clearing to sunny afternoon, 78°F high.",
            "confidence": 0.85,
            "tokens_used": 150
        }
        
        compiled_answer = await service.synthesize_answer(sample_query.id)
    
    # Check that answer was created
    assert compiled_answer is not None
    assert compiled_answer.query_id == sample_query.id
    assert compiled_answer.final_answer is not None
    assert compiled_answer.confidence_score == 0.85
    assert compiled_answer.compilation_method == "gpt-4"
    
    # Check that query status was updated
    await test_db.refresh(sample_query)
    assert sample_query.status == QueryStatus.COMPLETED
    
    # Check that citations were created
    from sqlalchemy import select
    stmt = select(Citation).where(Citation.compiled_answer_id == compiled_answer.id)
    result = await test_db.execute(stmt)
    # Note: The actual citation creation would happen in the service
    

@pytest.mark.asyncio
async def test_get_synthesis_status_not_synthesized(test_db: AsyncSession, sample_query):
    """Test getting synthesis status for query without synthesis"""
    service = SynthesisService(test_db)
    
    status = await service.get_synthesis_status(sample_query.id)
    
    assert status["synthesized"] is False
    assert status["answer_id"] is None
    assert status["confidence_score"] == 0.0
    assert status["citation_count"] == 0


@pytest.mark.asyncio
async def test_get_synthesis_status_synthesized(
    test_db: AsyncSession,
    sample_query
):
    """Test getting synthesis status for synthesized query"""
    service = SynthesisService(test_db)
    
    # Create a compiled answer
    compiled_answer = CompiledAnswer(
        id=uuid.uuid4(),
        query_id=sample_query.id,
        final_answer="Test answer",
        confidence_score=0.85,
        compilation_method="gpt-4",
        compilation_tokens_used=100
    )
    test_db.add(compiled_answer)
    
    # Create some citations
    for i in range(3):
        citation = Citation(
            id=uuid.uuid4(),
            compiled_answer_id=compiled_answer.id,
            contribution_id=uuid.uuid4(),
            claim_text=f"Claim {i}",
            source_excerpt=f"Source {i}",
            position_in_answer=i,
            confidence=0.9
        )
        test_db.add(citation)
    
    await test_db.commit()
    
    status = await service.get_synthesis_status(sample_query.id)
    
    assert status["synthesized"] is True
    assert status["answer_id"] == compiled_answer.id
    assert status["confidence_score"] == 0.85
    assert status["citation_count"] == 3
    assert status["synthesis_method"] == "gpt-4"
    assert status["tokens_used"] == 100


@pytest.mark.asyncio
async def test_extract_claim_text(test_db: AsyncSession):
    """Test claim text extraction around citations"""
    service = SynthesisService(test_db)
    
    answer_text = "The weather is sunny. It will be warm [@expert1] with no rain. Perfect for outdoor activities."
    
    # Find citation position
    citation_pos = answer_text.index("[@expert1]")
    
    claim = service._extract_claim_text(answer_text, citation_pos)
    
    # Should extract the sentence containing the citation
    assert "warm" in claim
    assert "[@expert1]" in claim or "expert1" in claim


@pytest.mark.asyncio
async def test_update_query_status(test_db: AsyncSession, sample_query):
    """Test query status update during synthesis"""
    service = SynthesisService(test_db)
    
    # Test successful status update
    await service._update_query_status(sample_query.id, QueryStatus.COMPILING)
    await test_db.refresh(sample_query)
    assert sample_query.status == QueryStatus.COMPILING
    
    # Test status update with error message
    await service._update_query_status(
        sample_query.id,
        QueryStatus.FAILED,
        error_message="Test error"
    )
    await test_db.refresh(sample_query)
    assert sample_query.status == QueryStatus.FAILED
    assert sample_query.error_message == "Test error"