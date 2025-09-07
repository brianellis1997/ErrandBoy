"""Tests for agent tools and workflow integration"""

import uuid
from datetime import datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from groupchat.agent.tools import AgentTools, ToolResult
from groupchat.agent.workflow import GroupChatWorkflow, QueryState
from groupchat.db.models import Contact, ContactStatus, Query, QueryStatus


@pytest.fixture
async def agent_tools(test_db):
    """Create agent tools instance"""
    return AgentTools(test_db)


@pytest.fixture
async def workflow(test_db):
    """Create workflow instance"""
    return GroupChatWorkflow(test_db)


@pytest.fixture
async def sample_contact(test_db):
    """Create a sample contact for testing"""
    contact = Contact(
        id=uuid.uuid4(),
        phone_number="+1234567890",
        name="Test Expert",
        bio="AI and technology expert",
        status=ContactStatus.ACTIVE,
        trust_score=0.85,
        expertise_summary="Artificial intelligence, machine learning, technology trends"
    )
    test_db.add(contact)
    await test_db.commit()
    await test_db.refresh(contact)
    return contact


class TestAgentTools:
    """Test cases for AgentTools"""

    async def test_save_contact_profile_success(self, agent_tools):
        """Test successful contact profile creation"""
        
        result = await agent_tools.save_contact_profile(
            name="Jane Doe",
            phone="+1987654321",
            role="Software Engineer",
            bio="Full stack developer with 5 years experience",
            email="jane@example.com",
            consent=True
        )
        
        assert result.success is True
        assert result.tool_name == "save_contact_profile"
        assert result.data["name"] == "Jane Doe"
        assert result.data["phone"] == "+1987654321"
        assert result.data["status"] == "active"
        assert result.error is None

    async def test_save_contact_profile_duplicate_phone(self, agent_tools, sample_contact):
        """Test handling of duplicate phone numbers"""
        
        result = await agent_tools.save_contact_profile(
            name="Duplicate User",
            phone=sample_contact.phone_number,  # Duplicate phone
            consent=True
        )
        
        assert result.success is False
        assert result.tool_name == "save_contact_profile"
        assert "phone" in result.error.lower() or "duplicate" in result.error.lower()

    async def test_update_expertise_success(self, agent_tools, sample_contact):
        """Test successful expertise update"""
        
        result = await agent_tools.update_expertise(
            contact_id=str(sample_contact.id),
            expertise_summary="Machine learning and data science expert",
            tags=["ML", "Data Science", "Python"]
        )
        
        assert result.success is True
        assert result.tool_name == "update_expertise"
        assert result.data["contact_id"] == str(sample_contact.id)
        assert result.data["expertise_updated"] is True

    async def test_update_expertise_invalid_contact(self, agent_tools):
        """Test expertise update with invalid contact ID"""
        
        fake_id = str(uuid.uuid4())
        result = await agent_tools.update_expertise(
            contact_id=fake_id,
            expertise_summary="Test expertise"
        )
        
        assert result.success is False
        assert result.tool_name == "update_expertise"

    async def test_search_contacts_success(self, agent_tools, sample_contact):
        """Test successful contact search"""
        
        result = await agent_tools.search_contacts(
            query="artificial intelligence",
            limit=5
        )
        
        assert result.success is True
        assert result.tool_name == "search_contacts"
        assert result.data["query"] == "artificial intelligence"
        assert isinstance(result.data["results"], list)
        assert result.data["count"] >= 0

    async def test_create_query_success(self, agent_tools):
        """Test successful query creation"""
        
        result = await agent_tools.create_query(
            user_phone="+1555123456",
            question_text="What are the latest trends in AI?",
            max_spend_cents=500
        )
        
        assert result.success is True
        assert result.tool_name == "create_query"
        assert result.data["user_phone"] == "+1555123456"
        assert result.data["question_text"] == "What are the latest trends in AI?"
        assert result.data["status"] == "pending"
        assert uuid.UUID(result.data["query_id"])  # Valid UUID

    async def test_get_query_status_success(self, agent_tools):
        """Test getting query status"""
        
        # First create a query
        create_result = await agent_tools.create_query(
            user_phone="+1555123456",
            question_text="Test question",
            max_spend_cents=300
        )
        
        assert create_result.success is True
        query_id = create_result.data["query_id"]
        
        # Then get its status
        status_result = await agent_tools.get_query_status(query_id)
        
        assert status_result.success is True
        assert status_result.tool_name == "get_query_status"
        assert status_result.data is not None

    async def test_get_query_status_not_found(self, agent_tools):
        """Test getting status for non-existent query"""
        
        fake_id = str(uuid.uuid4())
        result = await agent_tools.get_query_status(fake_id)
        
        assert result.success is False
        assert result.tool_name == "get_query_status"
        assert "not found" in result.error.lower()

    async def test_send_sms_success(self, agent_tools, sample_contact):
        """Test SMS sending (will use mock/test mode)"""
        
        result = await agent_tools.send_sms(
            contact_id=str(sample_contact.id),
            message="Test message for expert"
        )
        
        # In test mode, this should work but not send real SMS
        assert result.tool_name == "send_sms"
        assert result.data["contact_id"] == str(sample_contact.id)
        assert result.data["phone"] == sample_contact.phone_number

    async def test_send_sms_invalid_contact(self, agent_tools):
        """Test SMS sending with invalid contact"""
        
        fake_id = str(uuid.uuid4())
        result = await agent_tools.send_sms(
            contact_id=fake_id,
            message="Test message"
        )
        
        assert result.success is False
        assert result.tool_name == "send_sms"
        assert "not found" in result.error.lower()

    async def test_record_contribution_success(self, agent_tools, sample_contact):
        """Test recording a contribution"""
        
        # First create a query
        create_result = await agent_tools.create_query(
            user_phone="+1555123456",
            question_text="Test question for contribution",
            max_spend_cents=300
        )
        
        assert create_result.success is True
        query_id = create_result.data["query_id"]
        
        # Then record a contribution
        result = await agent_tools.record_contribution(
            query_id=query_id,
            contact_id=str(sample_contact.id),
            response_text="This is my expert response to the question",
            confidence_score=0.9
        )
        
        assert result.success is True
        assert result.tool_name == "record_contribution"
        assert result.data["query_id"] == query_id
        assert result.data["contact_id"] == str(sample_contact.id)
        assert result.data["confidence_score"] == 0.9

    async def test_tool_result_structure(self, agent_tools):
        """Test that all tools return proper ToolResult structure"""
        
        # Test with a simple operation
        result = await agent_tools.search_contacts("test query")
        
        assert isinstance(result, ToolResult)
        assert hasattr(result, 'success')
        assert hasattr(result, 'data')
        assert hasattr(result, 'error')
        assert hasattr(result, 'tool_name')
        assert hasattr(result, 'timestamp')
        assert isinstance(result.timestamp, datetime)

    async def test_error_handling_consistency(self, agent_tools):
        """Test that error handling is consistent across tools"""
        
        # Test with invalid UUIDs
        invalid_id = "not-a-uuid"
        
        tools_to_test = [
            ("update_expertise", {"contact_id": invalid_id, "expertise_summary": "test"}),
            ("get_query_status", {"query_id": invalid_id}),
            ("send_sms", {"contact_id": invalid_id, "message": "test"}),
        ]
        
        for tool_name, kwargs in tools_to_test:
            method = getattr(agent_tools, tool_name)
            result = await method(**kwargs)
            
            assert result.success is False
            assert result.error is not None
            assert result.tool_name == tool_name


class TestWorkflowIntegration:
    """Test cases for workflow integration"""

    async def test_workflow_initialization(self, workflow):
        """Test that workflow initializes correctly"""
        
        assert workflow.tools is not None
        assert workflow.graph is not None

    async def test_parse_query_node(self, workflow):
        """Test the parse query node"""
        
        initial_state = QueryState(
            user_phone="+1555123456",
            question_text="What's the weather like?",
            max_spend_cents=500,
            query_id=None,
            current_step="initializing",
            error=None,
            matched_experts=[],
            experts_contacted=0,
            contributions=[],
            contributions_received=0,
            final_answer=None,
            answer_id=None,
            confidence_score=0.0,
            payment_processed=False,
            total_payout_cents=0,
            should_continue=True,
            workflow_complete=False
        )
        
        result_state = await workflow.parse_query_node(initial_state)
        
        if not result_state.get("error"):
            assert result_state["query_id"] is not None
            assert result_state["current_step"] == "parsed"
            assert uuid.UUID(result_state["query_id"])  # Valid UUID

    async def test_match_experts_node(self, workflow, sample_contact):
        """Test the expert matching node"""
        
        state = QueryState(
            user_phone="+1555123456",
            question_text="AI and machine learning question",
            max_spend_cents=500,
            query_id=str(uuid.uuid4()),  # Mock query ID
            current_step="parsed",
            error=None,
            matched_experts=[],
            experts_contacted=0,
            contributions=[],
            contributions_received=0,
            final_answer=None,
            answer_id=None,
            confidence_score=0.0,
            payment_processed=False,
            total_payout_cents=0,
            should_continue=True,
            workflow_complete=False
        )
        
        result_state = await workflow.match_experts_node(state)
        
        if not result_state.get("error"):
            assert isinstance(result_state["matched_experts"], list)
            assert result_state["current_step"] == "experts_matched"

    async def test_outreach_message_creation(self, workflow):
        """Test outreach message creation"""
        
        message = workflow._create_outreach_message(
            "What are the best practices for AI development?",
            "Dr. Smith"
        )
        
        assert "Dr. Smith" in message
        assert "AI development" in message
        assert len(message) > 50  # Reasonable message length

    async def test_should_synthesize_logic(self, workflow):
        """Test the synthesis decision logic"""
        
        # Test with error
        state_with_error = {"error": "Some error"}
        assert workflow.should_synthesize(state_with_error) == "error"
        
        # Test with sufficient contributions
        state_with_contributions = {"contributions_received": 2}
        assert workflow.should_synthesize(state_with_contributions) == "synthesize"
        
        # Test with insufficient contributions
        state_insufficient = {"contributions_received": 0}
        assert workflow.should_synthesize(state_insufficient) == "wait"

    async def test_workflow_state_transitions(self, workflow):
        """Test that state transitions work correctly"""
        
        # Test basic state progression
        initial_state = QueryState(
            user_phone="+1555123456",
            question_text="Test question",
            max_spend_cents=500,
            query_id=None,
            current_step="initializing",
            error=None,
            matched_experts=[],
            experts_contacted=0,
            contributions=[],
            contributions_received=0,
            final_answer=None,
            answer_id=None,
            confidence_score=0.0,
            payment_processed=False,
            total_payout_cents=0,
            should_continue=True,
            workflow_complete=False
        )
        
        # Test parse query
        state_after_parse = await workflow.parse_query_node(initial_state)
        if not state_after_parse.get("error"):
            assert state_after_parse["current_step"] == "parsed"
            
            # Test expert matching
            state_after_matching = await workflow.match_experts_node(state_after_parse)
            if not state_after_matching.get("error"):
                assert state_after_matching["current_step"] == "experts_matched"