"""Integration tests for API endpoints"""

import pytest
import uuid
from httpx import AsyncClient

from groupchat.main import app
from groupchat.db.models import Contact, ContactStatus


@pytest.fixture
async def api_client(test_db):
    """Create test client with database dependency override"""
    from groupchat.db.database import get_db
    
    async def override_get_db():
        yield test_db
    
    app.dependency_overrides[get_db] = override_get_db
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client
    
    app.dependency_overrides.clear()


@pytest.fixture
async def sample_contact_data():
    """Sample contact data for testing"""
    return {
        "name": "Dr. Test Expert",
        "phone_number": "+1234567890",
        "email": "test@example.com",
        "bio": "Test expert in AI and machine learning",
        "expertise_summary": "AI, ML, Python, Research"
    }


@pytest.fixture
async def sample_query_data():
    """Sample query data for testing"""
    return {
        "user_phone": "+1987654321",
        "question_text": "What are the latest trends in artificial intelligence?",
        "max_spend_cents": 500,
        "max_experts": 3,
        "min_experts": 2,
        "timeout_minutes": 30
    }


class TestHealthEndpoints:
    """Test health check endpoints"""
    
    @pytest.mark.integration
    async def test_basic_health_check(self, api_client):
        """Test basic health endpoint"""
        response = await api_client.get("/health/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
    
    @pytest.mark.integration
    async def test_readiness_check(self, api_client):
        """Test readiness check"""
        response = await api_client.get("/health/ready")
        assert response.status_code == 200
        data = response.json()
        assert "database" in data
    
    @pytest.mark.integration
    async def test_liveness_probe(self, api_client):
        """Test liveness probe"""
        response = await api_client.get("/health/live")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "alive"


class TestContactEndpoints:
    """Test contact management endpoints"""
    
    @pytest.mark.integration
    async def test_create_contact_success(self, api_client, sample_contact_data):
        """Test successful contact creation"""
        response = await api_client.post("/api/v1/contacts/", json=sample_contact_data)
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == sample_contact_data["name"]
        assert data["phone_number"] == sample_contact_data["phone_number"]
        assert data["status"] == "pending"
    
    @pytest.mark.integration
    async def test_create_contact_duplicate_phone(self, api_client, sample_contact_data):
        """Test contact creation with duplicate phone"""
        # Create first contact
        await api_client.post("/api/v1/contacts/", json=sample_contact_data)
        
        # Try to create duplicate
        response = await api_client.post("/api/v1/contacts/", json=sample_contact_data)
        assert response.status_code == 400
        assert "phone" in response.json()["detail"].lower()
    
    @pytest.mark.integration
    async def test_get_contact_success(self, api_client, sample_contact_data):
        """Test getting contact details"""
        # Create contact first
        create_response = await api_client.post("/api/v1/contacts/", json=sample_contact_data)
        contact_id = create_response.json()["id"]
        
        # Get contact
        response = await api_client.get(f"/api/v1/contacts/{contact_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == sample_contact_data["name"]
    
    @pytest.mark.integration
    async def test_get_contact_not_found(self, api_client):
        """Test getting non-existent contact"""
        fake_id = str(uuid.uuid4())
        response = await api_client.get(f"/api/v1/contacts/{fake_id}")
        assert response.status_code == 404
    
    @pytest.mark.integration
    async def test_list_contacts(self, api_client, sample_contact_data):
        """Test listing contacts"""
        # Create a contact first
        await api_client.post("/api/v1/contacts/", json=sample_contact_data)
        
        # List contacts
        response = await api_client.get("/api/v1/contacts/")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["contacts"], list)
        assert data["total"] >= 1
    
    @pytest.mark.integration
    async def test_search_contacts(self, api_client, sample_contact_data):
        """Test searching contacts"""
        # Create contact first
        await api_client.post("/api/v1/contacts/", json=sample_contact_data)
        
        # Search for contacts
        response = await api_client.get("/api/v1/contacts/search?q=AI&limit=5")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["results"], list)


class TestQueryEndpoints:
    """Test query processing endpoints"""
    
    @pytest.mark.integration
    async def test_create_query_success(self, api_client, sample_query_data):
        """Test successful query creation"""
        response = await api_client.post("/api/v1/queries/", json=sample_query_data)
        assert response.status_code == 201
        data = response.json()
        assert data["user_phone"] == sample_query_data["user_phone"]
        assert data["question_text"] == sample_query_data["question_text"]
        assert data["status"] == "pending"
        assert uuid.UUID(data["id"])  # Valid UUID
    
    @pytest.mark.integration
    async def test_get_query_success(self, api_client, sample_query_data):
        """Test getting query details"""
        # Create query first
        create_response = await api_client.post("/api/v1/queries/", json=sample_query_data)
        query_id = create_response.json()["id"]
        
        # Get query
        response = await api_client.get(f"/api/v1/queries/{query_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["question_text"] == sample_query_data["question_text"]
    
    @pytest.mark.integration
    async def test_get_query_status(self, api_client, sample_query_data):
        """Test getting query status"""
        # Create query first
        create_response = await api_client.post("/api/v1/queries/", json=sample_query_data)
        query_id = create_response.json()["id"]
        
        # Get status
        response = await api_client.get(f"/api/v1/queries/{query_id}/status")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "progress" in data
    
    @pytest.mark.integration
    async def test_list_queries(self, api_client, sample_query_data):
        """Test listing queries"""
        # Create a query first
        await api_client.post("/api/v1/queries/", json=sample_query_data)
        
        # List queries
        response = await api_client.get("/api/v1/queries/")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["queries"], list)
        assert data["total"] >= 1


class TestAgentEndpoints:
    """Test agent and workflow endpoints"""
    
    @pytest.mark.integration
    async def test_agent_health_check(self, api_client):
        """Test agent health check"""
        response = await api_client.get("/api/v1/agent/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["agent_tools"] == "available"
    
    @pytest.mark.integration
    async def test_save_contact_via_agent(self, api_client):
        """Test saving contact through agent tools"""
        contact_data = {
            "name": "Agent Test Contact",
            "phone": "+1555123456",
            "role": "Software Engineer",
            "bio": "Test bio for agent contact",
            "consent": True
        }
        
        response = await api_client.post("/api/v1/agent/tools/save-contact", json=contact_data)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["name"] == contact_data["name"]
    
    @pytest.mark.integration
    async def test_search_contacts_via_agent(self, api_client):
        """Test searching contacts through agent tools"""
        # First create a contact through agent
        contact_data = {
            "name": "AI Expert",
            "phone": "+1555987654",
            "bio": "Expert in artificial intelligence and machine learning",
            "consent": True
        }
        await api_client.post("/api/v1/agent/tools/save-contact", json=contact_data)
        
        # Search for contacts
        response = await api_client.get("/api/v1/agent/tools/search-contacts?query=AI&limit=5")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert isinstance(data["data"]["results"], list)
    
    @pytest.mark.integration
    async def test_create_query_via_agent(self, api_client):
        """Test creating query through agent tools"""
        query_data = {
            "user_phone": "+1555444333",
            "question_text": "What are the best practices for API design?",
            "max_spend_cents": 300
        }
        
        response = await api_client.post("/api/v1/agent/tools/queries", json=query_data)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["user_phone"] == query_data["user_phone"]


class TestLedgerEndpoints:
    """Test ledger and payment endpoints"""
    
    @pytest.mark.integration
    async def test_get_platform_stats(self, api_client):
        """Test getting platform statistics"""
        response = await api_client.get("/api/v1/ledger/stats/platform")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "platform_balance" in data["data"]
        assert "referral_pool_balance" in data["data"]
    
    @pytest.mark.integration
    async def test_get_user_balance(self, api_client):
        """Test getting user balance"""
        response = await api_client.get("/api/v1/ledger/balance/user/+1234567890")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "balance_cents" in data["data"]
        assert "balance_dollars" in data["data"]
    
    @pytest.mark.integration
    async def test_get_transaction_history(self, api_client):
        """Test getting transaction history"""
        response = await api_client.get("/api/v1/ledger/transactions?limit=10")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert isinstance(data["data"]["transactions"], list)


class TestAdminEndpoints:
    """Test admin endpoints"""
    
    @pytest.mark.integration
    async def test_admin_stats(self, api_client):
        """Test admin statistics"""
        response = await api_client.get("/api/v1/admin/stats")
        assert response.status_code == 200
        data = response.json()
        assert "total_contacts" in data
        assert "total_queries" in data
    
    @pytest.mark.integration
    async def test_admin_health(self, api_client):
        """Test admin health check"""
        response = await api_client.get("/api/v1/admin/health")
        assert response.status_code == 200
        data = response.json()
        assert "system" in data
        assert "services" in data


class TestErrorHandling:
    """Test error handling across endpoints"""
    
    @pytest.mark.integration
    async def test_invalid_uuid_handling(self, api_client):
        """Test handling of invalid UUIDs"""
        # Test various endpoints with invalid UUIDs
        endpoints = [
            "/api/v1/contacts/not-a-uuid",
            "/api/v1/queries/not-a-uuid",
            "/api/v1/queries/not-a-uuid/status",
        ]
        
        for endpoint in endpoints:
            response = await api_client.get(endpoint)
            # Should either be 400 (validation error) or 404 (not found)
            assert response.status_code in [400, 404, 422]
    
    @pytest.mark.integration
    async def test_missing_required_fields(self, api_client):
        """Test handling of missing required fields"""
        # Test contact creation without required fields
        response = await api_client.post("/api/v1/contacts/", json={})
        assert response.status_code == 422  # Validation error
        
        # Test query creation without required fields
        response = await api_client.post("/api/v1/queries/", json={})
        assert response.status_code == 422  # Validation error
    
    @pytest.mark.integration
    async def test_content_type_validation(self, api_client):
        """Test content type validation"""
        response = await api_client.post(
            "/api/v1/contacts/", 
            data="not json",  # Send plain text instead of JSON
            headers={"Content-Type": "text/plain"}
        )
        assert response.status_code == 422  # Validation error