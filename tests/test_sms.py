"""Tests for SMS service functionality"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from groupchat.db.models import Contact, ContactStatus, Contribution, Query, QueryStatus
from groupchat.services.sms import SMSService, TwilioService, SMSComplianceService, SMSRateLimiter


class TestSMSComplianceService:
    """Test SMS compliance functionality"""

    @pytest.fixture
    async def compliance_service(self, test_db):
        return SMSComplianceService(test_db)

    @pytest.fixture
    async def test_contact(self, test_db):
        contact = Contact(
            id=uuid4(),
            phone_number="+1234567890",
            email="test@example.com",
            name="Test Expert",
            bio="Test expert for SMS testing",
            extra_metadata={}
        )
        test_db.add(contact)
        await test_db.commit()
        return contact

    async def test_opt_out_contact(self, compliance_service, test_contact):
        """Test opting out a contact"""
        # Initially not opted out
        assert not await compliance_service.is_opted_out(test_contact.phone_number)
        
        # Opt out
        result = await compliance_service.opt_out_contact(test_contact.phone_number)
        assert result is True
        
        # Now should be opted out
        assert await compliance_service.is_opted_out(test_contact.phone_number)

    async def test_opt_in_contact(self, compliance_service, test_contact):
        """Test opting in a contact after opt-out"""
        # Opt out first
        await compliance_service.opt_out_contact(test_contact.phone_number)
        assert await compliance_service.is_opted_out(test_contact.phone_number)
        
        # Opt back in
        result = await compliance_service.opt_in_contact(test_contact.phone_number)
        assert result is True
        
        # Should not be opted out anymore
        assert not await compliance_service.is_opted_out(test_contact.phone_number)

    async def test_opt_out_nonexistent_contact(self, compliance_service):
        """Test opting out a non-existent contact"""
        result = await compliance_service.opt_out_contact("+9999999999")
        assert result is False

    @patch('groupchat.services.sms.datetime')
    def test_quiet_hours(self, mock_datetime, compliance_service):
        """Test quiet hours detection"""
        # Mock current time to be 10 PM (22:00)
        mock_datetime.utcnow.return_value = datetime(2023, 1, 1, 22, 0, 0)
        assert compliance_service.is_quiet_hours() is True
        
        # Mock current time to be 7 AM (07:00)
        mock_datetime.utcnow.return_value = datetime(2023, 1, 1, 7, 0, 0)
        assert compliance_service.is_quiet_hours() is True
        
        # Mock current time to be 2 PM (14:00)
        mock_datetime.utcnow.return_value = datetime(2023, 1, 1, 14, 0, 0)
        assert compliance_service.is_quiet_hours() is False

    async def test_can_send_sms_opted_out(self, compliance_service, test_contact):
        """Test can_send_sms when contact is opted out"""
        await compliance_service.opt_out_contact(test_contact.phone_number)
        
        can_send, reason = await compliance_service.can_send_sms(test_contact.phone_number)
        assert can_send is False
        assert "opted out" in reason

    @patch('groupchat.services.sms.datetime')
    async def test_can_send_sms_quiet_hours(self, mock_datetime, compliance_service, test_contact):
        """Test can_send_sms during quiet hours"""
        mock_datetime.utcnow.return_value = datetime(2023, 1, 1, 22, 0, 0)
        
        can_send, reason = await compliance_service.can_send_sms(test_contact.phone_number)
        assert can_send is False
        assert "Quiet hours" in reason


class TestSMSRateLimiter:
    """Test SMS rate limiting functionality"""

    @pytest.fixture
    async def rate_limiter(self, test_db):
        return SMSRateLimiter(test_db)

    @pytest.fixture
    async def test_contact_with_messages(self, test_db):
        # Create contact with existing SMS messages
        current_time = datetime.utcnow()
        contact = Contact(
            id=uuid4(),
            phone_number="+1234567890",
            email="test@example.com",
            name="Test Expert",
            bio="Test expert for rate limiting",
            max_queries_per_day=5,
            extra_metadata={
                "sms_messages": [
                    {
                        "sid": "SM123",
                        "type": "query_invitation",
                        "direction": "outbound",
                        "sent_at": current_time.isoformat()
                    },
                    {
                        "sid": "SM124",
                        "type": "query_invitation", 
                        "direction": "outbound",
                        "sent_at": (current_time - timedelta(hours=1)).isoformat()
                    }
                ]
            }
        )
        test_db.add(contact)
        await test_db.commit()
        return contact

    async def test_daily_limit_not_reached(self, rate_limiter, test_contact_with_messages):
        """Test rate limiting when daily limit is not reached"""
        can_send, reason = await rate_limiter.can_send_sms_to_contact(test_contact_with_messages)
        assert can_send is True
        assert reason == "OK"

    async def test_daily_limit_reached(self, rate_limiter, test_db):
        """Test rate limiting when daily limit is reached"""
        current_time = datetime.utcnow()
        
        # Create contact with max daily messages already sent
        contact = Contact(
            id=uuid4(),
            phone_number="+1234567890",
            email="test@example.com",
            name="Test Expert",
            max_queries_per_day=2,
            extra_metadata={
                "sms_messages": [
                    {
                        "sid": "SM123",
                        "type": "query_invitation",
                        "direction": "outbound",
                        "sent_at": current_time.isoformat()
                    },
                    {
                        "sid": "SM124",
                        "type": "query_invitation",
                        "direction": "outbound", 
                        "sent_at": (current_time - timedelta(hours=1)).isoformat()
                    }
                ]
            }
        )
        test_db.add(contact)
        await test_db.commit()
        
        can_send, reason = await rate_limiter.can_send_sms_to_contact(contact)
        assert can_send is False
        assert "Daily limit reached" in reason

    async def test_recent_message_rate_limit(self, rate_limiter, test_db):
        """Test rate limiting for recent messages"""
        current_time = datetime.utcnow()
        
        # Create contact with very recent message (2 minutes ago)
        contact = Contact(
            id=uuid4(),
            phone_number="+1234567890",
            email="test@example.com",
            name="Test Expert",
            max_queries_per_day=10,
            extra_metadata={
                "sms_messages": [
                    {
                        "sid": "SM123",
                        "type": "query_invitation",
                        "direction": "outbound",
                        "sent_at": (current_time - timedelta(minutes=2)).isoformat()
                    }
                ]
            }
        )
        test_db.add(contact)
        await test_db.commit()
        
        can_send, reason = await rate_limiter.can_send_sms_to_contact(contact)
        assert can_send is False
        assert "Rate limited: recent message sent" in reason

    async def test_queries_disabled(self, rate_limiter, test_db):
        """Test rate limiting when contact has disabled queries"""
        contact = Contact(
            id=uuid4(),
            phone_number="+1234567890",
            email="test@example.com",
            name="Test Expert",
            max_queries_per_day=0,  # Disabled
            extra_metadata={}
        )
        test_db.add(contact)
        await test_db.commit()
        
        can_send, reason = await rate_limiter.can_send_sms_to_contact(contact)
        assert can_send is False
        assert "Contact has disabled queries" in reason


class TestTwilioService:
    """Test Twilio service functionality"""

    @pytest.fixture
    async def twilio_service(self, test_db):
        return TwilioService(test_db)

    @pytest.fixture
    async def test_contact(self, test_db):
        contact = Contact(
            id=uuid4(),
            phone_number="+1234567890",
            email="test@example.com",
            name="Test Expert",
            status=ContactStatus.ACTIVE,
            max_queries_per_day=10,
            extra_metadata={}
        )
        test_db.add(contact)
        await test_db.commit()
        return contact

    @pytest.fixture
    async def test_query(self, test_db):
        query = Query(
            id=uuid4(),
            user_phone="+1987654321",
            question_text="What is the best programming language for web development?",
            status=QueryStatus.COLLECTING
        )
        test_db.add(query)
        await test_db.commit()
        return query

    @patch('groupchat.services.sms.settings')
    def test_is_not_configured(self, mock_settings, twilio_service):
        """Test Twilio not configured"""
        mock_settings.enable_sms = False
        assert twilio_service._is_configured() is False

    @patch('groupchat.services.sms.settings')
    @patch('groupchat.services.sms.Client')
    async def test_send_query_invitation_not_configured(self, mock_client, mock_settings, twilio_service, test_contact, test_query):
        """Test sending SMS when Twilio is not configured"""
        mock_settings.enable_sms = False
        twilio_service.client = None
        
        result = await twilio_service.send_query_invitation(test_contact, test_query)
        assert result is None

    @patch('groupchat.services.sms.settings')
    @patch('groupchat.services.sms.Client')
    async def test_send_query_invitation_success(self, mock_client_class, mock_settings, twilio_service, test_contact, test_query):
        """Test successful SMS sending"""
        # Mock settings
        mock_settings.enable_sms = True
        mock_settings.twilio_account_sid = "test_sid"
        mock_settings.twilio_auth_token = "test_token"
        mock_settings.twilio_phone_number = "+1000000000"
        
        # Mock Twilio client
        mock_client = MagicMock()
        mock_message = MagicMock()
        mock_message.sid = "SM123456789"
        mock_client.messages.create.return_value = mock_message
        twilio_service.client = mock_client
        
        # Mock compliance and rate limiting to allow sending
        twilio_service.compliance.can_send_sms = AsyncMock(return_value=(True, "OK"))
        twilio_service.rate_limiter.can_send_sms_to_contact = AsyncMock(return_value=(True, "OK"))
        
        result = await twilio_service.send_query_invitation(test_contact, test_query, "John")
        
        assert result == "SM123456789"
        mock_client.messages.create.assert_called_once()
        
        # Verify message content
        call_args = mock_client.messages.create.call_args
        assert "John asks:" in call_args.kwargs["body"]
        assert test_query.question_text in call_args.kwargs["body"]

    async def test_send_compliance_response_stop(self, twilio_service):
        """Test sending STOP compliance response"""
        # Mock Twilio client
        mock_client = MagicMock()
        mock_message = MagicMock()
        mock_message.sid = "SM987654321"
        mock_client.messages.create.return_value = mock_message
        twilio_service.client = mock_client
        
        with patch('groupchat.services.sms.settings') as mock_settings:
            mock_settings.enable_sms = True
            mock_settings.twilio_phone_number = "+1000000000"
            
            result = await twilio_service.send_compliance_response("+1234567890", "STOP")
            
            assert result == "SM987654321"
            mock_client.messages.create.assert_called_once()
            
            # Verify STOP message content
            call_args = mock_client.messages.create.call_args
            assert "unsubscribed" in call_args.kwargs["body"]


class TestSMSService:
    """Test high-level SMS service orchestration"""

    @pytest.fixture
    async def sms_service(self, test_db):
        return SMSService(test_db)

    @pytest.fixture
    async def test_contact(self, test_db):
        contact = Contact(
            id=uuid4(),
            phone_number="+1234567890",
            email="test@example.com",
            name="Test Expert",
            status=ContactStatus.ACTIVE,
            extra_metadata={}
        )
        test_db.add(contact)
        await test_db.commit()
        return contact

    @pytest.fixture
    async def test_query(self, test_db):
        query = Query(
            id=uuid4(),
            user_phone="+1987654321",
            question_text="Test question",
            status=QueryStatus.COLLECTING
        )
        test_db.add(query)
        await test_db.commit()
        return query

    async def test_process_incoming_sms_stop(self, sms_service, test_contact):
        """Test processing STOP message"""
        sms_service.twilio.send_compliance_response = AsyncMock(return_value="SM123")
        
        result = await sms_service.process_incoming_sms(
            test_contact.phone_number, 
            "STOP", 
            "SM123456"
        )
        
        assert result["action"] == "opt_out"
        assert result["status"] == "processed"

    async def test_process_incoming_sms_start(self, sms_service, test_contact):
        """Test processing START message"""
        # First opt out the contact
        await sms_service.compliance.opt_out_contact(test_contact.phone_number)
        
        sms_service.twilio.send_compliance_response = AsyncMock(return_value="SM123")
        
        result = await sms_service.process_incoming_sms(
            test_contact.phone_number,
            "START", 
            "SM123456"
        )
        
        assert result["action"] == "opt_in"
        assert result["status"] == "processed"

    async def test_process_incoming_sms_help(self, sms_service, test_contact):
        """Test processing HELP message"""
        sms_service.twilio.send_compliance_response = AsyncMock(return_value="SM123")
        
        result = await sms_service.process_incoming_sms(
            test_contact.phone_number,
            "HELP",
            "SM123456"
        )
        
        assert result["action"] == "help"
        assert result["status"] == "processed"

    async def test_process_incoming_sms_unknown_contact(self, sms_service):
        """Test processing SMS from unknown contact"""
        result = await sms_service.process_incoming_sms(
            "+9999999999",  # Unknown number
            "Hello", 
            "SM123456"
        )
        
        assert result["action"] == "ignored"
        assert result["status"] == "unknown_contact"

    async def test_process_incoming_sms_response(self, sms_service, test_contact, test_query, test_db):
        """Test processing expert response"""
        # Create active contribution waiting for response
        contribution = Contribution(
            id=uuid4(),
            query_id=test_query.id,
            contact_id=test_contact.id,
            response_text="",
            requested_at=datetime.utcnow(),
            extra_metadata={"invitation_sent": True}
        )
        test_db.add(contribution)
        await test_db.commit()
        
        sms_service.twilio.send_follow_up_response = AsyncMock(return_value="SM123")
        
        result = await sms_service.process_incoming_sms(
            test_contact.phone_number,
            "This is my expert response",
            "SM123456"
        )
        
        assert result["action"] == "response_recorded"
        assert result["status"] == "processed"
        assert "query_id" in result
        assert "contribution_id" in result

    async def test_process_incoming_sms_pass(self, sms_service, test_contact, test_query, test_db):
        """Test processing PASS response"""
        # Create active contribution
        contribution = Contribution(
            id=uuid4(),
            query_id=test_query.id,
            contact_id=test_contact.id,
            response_text="",
            requested_at=datetime.utcnow(),
            extra_metadata={"invitation_sent": True}
        )
        test_db.add(contribution)
        await test_db.commit()
        
        result = await sms_service.process_incoming_sms(
            test_contact.phone_number,
            "PASS",
            "SM123456"
        )
        
        assert result["action"] == "pass_recorded"
        assert result["status"] == "processed"

    async def test_send_query_to_experts(self, sms_service, test_contact, test_query):
        """Test sending query to multiple experts"""
        sms_service.twilio.send_query_invitation = AsyncMock(return_value="SM123456")
        
        results = await sms_service.send_query_to_experts(
            test_query,
            [test_contact],
            "Test User"
        )
        
        assert len(results["sent"]) == 1
        assert len(results["failed"]) == 0
        assert len(results["skipped"]) == 0
        assert results["sent"][0]["message_sid"] == "SM123456"


class TestSMSIntegration:
    """Integration tests for SMS functionality"""

    async def test_full_sms_workflow(self, test_db):
        """Test complete SMS workflow from query to response"""
        # Create test data
        contact = Contact(
            id=uuid4(),
            phone_number="+1234567890",
            email="test@example.com",
            name="Test Expert",
            status=ContactStatus.ACTIVE,
            extra_metadata={}
        )
        
        query = Query(
            id=uuid4(),
            user_phone="+1987654321",
            question_text="Integration test question",
            status=QueryStatus.COLLECTING
        )
        
        test_db.add(contact)
        test_db.add(query)
        await test_db.commit()
        
        # Initialize SMS service
        sms_service = SMSService(test_db)
        
        # Mock Twilio calls
        sms_service.twilio.send_query_invitation = AsyncMock(return_value="SM123456")
        sms_service.twilio.send_follow_up_response = AsyncMock(return_value="SM789")
        
        # Send query to expert
        results = await sms_service.send_query_to_experts(query, [contact], "Test User")
        assert len(results["sent"]) == 1
        
        # Simulate expert response
        response_result = await sms_service.process_incoming_sms(
            contact.phone_number,
            "This is my expert response to the integration test",
            "SM654321"
        )
        
        assert response_result["action"] == "response_recorded"
        assert response_result["status"] == "processed"