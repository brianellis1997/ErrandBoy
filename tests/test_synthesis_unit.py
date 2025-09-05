"""Unit tests for synthesis service without database"""

import json
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from groupchat.db.models import Contact, Contribution, Query, QueryStatus
from groupchat.services.synthesis import SynthesisService


class TestSynthesisHelpers:
    """Test synthesis helper methods"""
    
    def test_create_handle_from_name(self):
        """Test handle creation from different name formats"""
        db_mock = MagicMock()
        service = SynthesisService(db_mock)
        
        # Test single word
        assert service._create_handle_from_name("Alex") == "alex"
        
        # Test two words
        handle = service._create_handle_from_name("Alex Surfer")
        assert len(handle) > 0
        assert handle.islower()
        assert "sur" in handle or "ale" in handle
        
        # Test three words
        handle = service._create_handle_from_name("John Paul Smith")
        assert len(handle) > 0
        assert handle.islower()
        
        # Test name with special characters
        handle = service._create_handle_from_name("Mary-Jane O'Connor")
        assert len(handle) > 0
        assert handle.islower()
        assert not any(c in handle for c in "-'")
    
    def test_generate_citation_handles(self):
        """Test citation handle generation"""
        db_mock = MagicMock()
        service = SynthesisService(db_mock)
        
        # Create mock data
        contact1 = MagicMock()
        contact1.name = "Alex Surfer"
        contact1.id = uuid.uuid4()
        
        contact2 = MagicMock()
        contact2.name = "Priya Tech"
        contact2.id = uuid.uuid4()
        
        contribution1 = MagicMock()
        contribution1.id = uuid.uuid4()
        
        contribution2 = MagicMock()
        contribution2.id = uuid.uuid4()
        
        contributions_with_contacts = [
            (contribution1, contact1),
            (contribution2, contact2),
        ]
        
        handle_mapping = service._generate_citation_handles(contributions_with_contacts)
        
        # Check that handles were generated
        assert len(handle_mapping) == 2
        
        # Check handle uniqueness
        handles = list(handle_mapping.keys())
        assert len(handles) == len(set(handles))
        
        # Check that each handle maps correctly
        for handle, (contribution, contact) in handle_mapping.items():
            assert contribution in [contribution1, contribution2]
            assert contact in [contact1, contact2]
    
    def test_calculate_contribution_weights(self):
        """Test contribution weight calculation"""
        db_mock = MagicMock()
        service = SynthesisService(db_mock)
        
        contrib1_id = uuid.uuid4()
        contrib2_id = uuid.uuid4()
        contrib3_id = uuid.uuid4()
        
        # Create mock citations data
        citations_data = [
            {"contribution_id": contrib1_id},
            {"contribution_id": contrib1_id},
            {"contribution_id": contrib2_id},
            {"contribution_id": contrib1_id},
            {"contribution_id": contrib3_id},
        ]
        
        weights = service._calculate_contribution_weights(citations_data)
        
        # Check that weights were calculated
        assert len(weights) == 3
        
        # Check that weights sum to 1.0
        assert abs(sum(weights.values()) - 1.0) < 0.001
        
        # Check specific weight values
        assert abs(weights[contrib1_id] - 0.6) < 0.001  # 3/5 citations
        assert abs(weights[contrib2_id] - 0.2) < 0.001  # 1/5 citations
        assert abs(weights[contrib3_id] - 0.2) < 0.001  # 1/5 citations
    
    def test_extract_citations(self):
        """Test citation extraction from synthesized answer"""
        db_mock = MagicMock()
        service = SynthesisService(db_mock)
        
        # Create mock data
        contrib1 = MagicMock()
        contrib1.id = uuid.uuid4()
        contrib1.response_text = "Morning fog clearing by 10am"
        contrib1.confidence_score = 0.95
        
        contrib2 = MagicMock()
        contrib2.id = uuid.uuid4()
        contrib2.response_text = "Temperature reaching 78°F downtown"
        contrib2.confidence_score = 0.90
        
        contact1 = MagicMock()
        contact1.id = uuid.uuid4()
        contact1.name = "Alex S"
        
        contact2 = MagicMock()
        contact2.id = uuid.uuid4()
        contact2.name = "Priya T"
        
        handle_mapping = {
            "alexs": (contrib1, contact1),
            "priyat": (contrib2, contact2),
        }
        
        contributions_with_contacts = [
            (contrib1, contact1),
            (contrib2, contact2),
        ]
        
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
            assert "handle" in citation
            assert "claim_text" in citation
            assert "source_excerpt" in citation
            assert "position" in citation
            assert "confidence" in citation
            
            # Check that IDs are valid UUIDs
            assert citation["contribution_id"] in [contrib1.id, contrib2.id]
    
    def test_extract_claim_text(self):
        """Test claim text extraction around citations"""
        db_mock = MagicMock()
        service = SynthesisService(db_mock)
        
        answer_text = "The weather is sunny. It will be warm [@expert1] with no rain. Perfect for outdoor activities."
        
        # Find citation position
        citation_pos = answer_text.index("[@expert1]")
        
        claim = service._extract_claim_text(answer_text, citation_pos)
        
        # Should extract the sentence containing the citation
        assert "warm" in claim
        assert "[@expert1]" in claim or "rain" in claim
    
    def test_mock_synthesis_response(self):
        """Test mock synthesis response generation"""
        db_mock = MagicMock()
        service = SynthesisService(db_mock)
        
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
        
        # Check that alice and bob are mentioned
        assert "alice" in response["answer"] or "bob" in response["answer"]
    
    def test_build_synthesis_prompt(self):
        """Test synthesis prompt building"""
        db_mock = MagicMock()
        service = SynthesisService(db_mock)
        
        question = "What's the weather like today?"
        
        # Create mock data
        contrib1 = MagicMock()
        contrib1.response_text = "Sunny and warm"
        
        contrib2 = MagicMock()
        contrib2.response_text = "78 degrees"
        
        contact1 = MagicMock()
        contact1.name = "Alex"
        contact1.expertise_summary = "Weather expert"
        
        contact2 = MagicMock()
        contact2.name = "Bob"
        contact2.expertise_summary = None
        
        contributions_with_contacts = [
            (contrib1, contact1),
            (contrib2, contact2),
        ]
        
        handle_mapping = {
            "alex": (contrib1, contact1),
            "bob": (contrib2, contact2),
        }
        
        prompt = service._build_synthesis_prompt(
            question,
            contributions_with_contacts,
            handle_mapping
        )
        
        # Check that prompt contains all necessary elements
        assert question in prompt
        assert "Sunny and warm" in prompt
        assert "78 degrees" in prompt
        assert "[@alex]" in prompt
        assert "[@bob]" in prompt
        assert "synthesize" in prompt.lower()
        assert "citation" in prompt.lower()
        assert "JSON" in prompt


@pytest.mark.asyncio
class TestSynthesisAsync:
    """Test async synthesis methods"""
    
    async def test_synthesize_answer_invalid_query(self):
        """Test synthesis with invalid query ID"""
        db_mock = AsyncMock()
        service = SynthesisService(db_mock)
        
        # Mock query not found
        service._get_query_with_contributions = AsyncMock(return_value=None)
        
        invalid_id = uuid.uuid4()
        
        with pytest.raises(ValueError, match="not found"):
            await service.synthesize_answer(invalid_id)
    
    async def test_synthesize_answer_wrong_status(self):
        """Test synthesis with query in wrong status"""
        db_mock = AsyncMock()
        service = SynthesisService(db_mock)
        
        # Mock query with wrong status
        mock_query = MagicMock()
        mock_query.status = QueryStatus.PENDING
        mock_query.id = uuid.uuid4()
        
        service._get_query_with_contributions = AsyncMock(return_value=mock_query)
        
        with pytest.raises(ValueError, match="Cannot synthesize"):
            await service.synthesize_answer(mock_query.id)
    
    async def test_get_synthesis_status_not_synthesized(self):
        """Test getting synthesis status for query without synthesis"""
        db_mock = AsyncMock()
        service = SynthesisService(db_mock)
        
        # Mock no compiled answer
        db_mock.execute = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db_mock.execute.return_value = mock_result
        
        status = await service.get_synthesis_status(uuid.uuid4())
        
        assert status["synthesized"] is False
        assert status["answer_id"] is None
        assert status["confidence_score"] == 0.0
        assert status["citation_count"] == 0
    
    @patch('groupchat.services.synthesis.AsyncOpenAI')
    async def test_call_llm_for_synthesis_with_api(self, mock_openai_class):
        """Test LLM call with OpenAI API"""
        db_mock = AsyncMock()
        
        # Mock OpenAI client
        mock_client = AsyncMock()
        mock_openai_class.return_value = mock_client
        
        # Mock response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "answer": "Test answer with [@expert1] citation",
            "summary": "Test summary",
            "confidence": 0.85
        })
        mock_response.usage.total_tokens = 100
        
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        
        # Create service with mocked API key
        with patch('groupchat.config.settings.openai_api_key', 'test-key'):
            service = SynthesisService(db_mock)
            service.openai_client = mock_client
            
            result = await service._call_llm_for_synthesis("Test prompt")
        
        assert result["answer"] == "Test answer with [@expert1] citation"
        assert result["summary"] == "Test summary"
        assert result["confidence"] == 0.85
        assert result["tokens_used"] == 100
    
    async def test_call_llm_for_synthesis_fallback(self):
        """Test LLM call fallback to mock when no API key"""
        db_mock = AsyncMock()
        service = SynthesisService(db_mock)
        service.openai_client = None  # No API key
        
        prompt = "Test with [@alice] and [@bob]"
        result = await service._call_llm_for_synthesis(prompt)
        
        # Should fall back to mock response
        assert "answer" in result
        assert "summary" in result
        assert "confidence" in result
        assert "tokens_used" in result
        assert "[@" in result["answer"]