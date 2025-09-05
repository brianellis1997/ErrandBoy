"""Tests for contact management endpoints"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from groupchat.db.database import Base, get_db
from groupchat.main import app

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


@pytest.fixture(scope="function")
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def test_create_contact(setup_database):
    """Test creating a new contact"""
    contact_data = {
        "phone_number": "+1234567890",
        "email": "test@example.com",
        "name": "Test User",
        "bio": "Software developer with 5 years experience",
        "expertise_tags": ["python", "fastapi", "postgresql"],
    }

    response = client.post("/api/v1/contacts/", json=contact_data)
    assert response.status_code == 201

    data = response.json()
    assert data["name"] == "Test User"
    assert data["phone_number"] == "+1234567890"
    assert data["email"] == "test@example.com"
    assert data["status"] == "pending"


def test_create_contact_duplicate_phone(setup_database):
    """Test creating contact with duplicate phone number"""
    contact_data = {
        "phone_number": "+1234567890",
        "name": "Test User",
    }

    # Create first contact
    response1 = client.post("/api/v1/contacts/", json=contact_data)
    assert response1.status_code == 201

    # Try to create duplicate
    response2 = client.post("/api/v1/contacts/", json=contact_data)
    assert response2.status_code == 400
    assert "already exists" in response2.json()["detail"]


def test_create_contact_invalid_phone(setup_database):
    """Test creating contact with invalid phone number"""
    contact_data = {
        "phone_number": "invalid",
        "name": "Test User",
    }

    response = client.post("/api/v1/contacts/", json=contact_data)
    assert response.status_code == 422


def test_get_contact(setup_database):
    """Test retrieving a contact by ID"""
    # Create contact first
    contact_data = {
        "phone_number": "+1234567890",
        "name": "Test User",
    }

    create_response = client.post("/api/v1/contacts/", json=contact_data)
    assert create_response.status_code == 201
    contact_id = create_response.json()["id"]

    # Get contact
    response = client.get(f"/api/v1/contacts/{contact_id}")
    assert response.status_code == 200

    data = response.json()
    assert data["id"] == contact_id
    assert data["name"] == "Test User"


def test_get_contact_not_found(setup_database):
    """Test retrieving non-existent contact"""
    fake_id = str(uuid4())
    response = client.get(f"/api/v1/contacts/{fake_id}")
    assert response.status_code == 404


def test_update_contact(setup_database):
    """Test updating a contact"""
    # Create contact first
    contact_data = {
        "phone_number": "+1234567890",
        "name": "Test User",
        "bio": "Original bio",
    }

    create_response = client.post("/api/v1/contacts/", json=contact_data)
    assert create_response.status_code == 201
    contact_id = create_response.json()["id"]

    # Update contact
    update_data = {"name": "Updated User", "bio": "Updated bio with new information"}

    response = client.put(f"/api/v1/contacts/{contact_id}", json=update_data)
    assert response.status_code == 200

    data = response.json()
    assert data["name"] == "Updated User"
    assert data["bio"] == "Updated bio with new information"


def test_update_contact_not_found(setup_database):
    """Test updating non-existent contact"""
    fake_id = str(uuid4())
    update_data = {"name": "Updated User"}

    response = client.put(f"/api/v1/contacts/{fake_id}", json=update_data)
    assert response.status_code == 404


def test_delete_contact(setup_database):
    """Test soft deleting a contact"""
    # Create contact first
    contact_data = {
        "phone_number": "+1234567890",
        "name": "Test User",
    }

    create_response = client.post("/api/v1/contacts/", json=contact_data)
    assert create_response.status_code == 201
    contact_id = create_response.json()["id"]

    # Delete contact
    response = client.delete(f"/api/v1/contacts/{contact_id}")
    assert response.status_code == 204

    # Verify contact is soft deleted (not found in normal queries)
    get_response = client.get(f"/api/v1/contacts/{contact_id}")
    assert get_response.status_code == 404


def test_delete_contact_not_found(setup_database):
    """Test deleting non-existent contact"""
    fake_id = str(uuid4())
    response = client.delete(f"/api/v1/contacts/{fake_id}")
    assert response.status_code == 404


def test_list_contacts(setup_database):
    """Test listing contacts with pagination"""
    # Create multiple contacts
    for i in range(5):
        contact_data = {
            "phone_number": f"+123456789{i}",
            "name": f"Test User {i}",
        }
        response = client.post("/api/v1/contacts/", json=contact_data)
        assert response.status_code == 201

    # List contacts
    response = client.get("/api/v1/contacts/?skip=1&limit=2")
    assert response.status_code == 200

    data = response.json()
    assert data["total"] == 5
    assert data["skip"] == 1
    assert data["limit"] == 2
    assert len(data["contacts"]) == 2


def test_search_contacts_by_text(setup_database):
    """Test searching contacts by text query"""
    # Create contacts with different names/bios
    contacts = [
        {
            "phone_number": "+1234567890",
            "name": "Python Developer",
            "bio": "Expert in Python and Django",
        },
        {
            "phone_number": "+1234567891",
            "name": "JavaScript Developer",
            "bio": "Frontend specialist with React",
        },
    ]

    for contact_data in contacts:
        response = client.post("/api/v1/contacts/", json=contact_data)
        assert response.status_code == 201

    # Search for Python-related contacts
    response = client.get("/api/v1/contacts/search?query=Python")
    assert response.status_code == 200

    data = response.json()
    assert data["total"] == 1
    assert "Python" in data["contacts"][0]["name"]


def test_search_contacts_by_availability(setup_database):
    """Test searching available contacts only"""
    # Create available and unavailable contacts
    contacts = [
        {"phone_number": "+1234567890", "name": "Available User", "is_available": True},
        {
            "phone_number": "+1234567891",
            "name": "Unavailable User",
            "is_available": False,
        },
    ]

    for contact_data in contacts:
        response = client.post("/api/v1/contacts/", json=contact_data)
        assert response.status_code == 201

    # Search for available contacts only
    response = client.get("/api/v1/contacts/search?available_only=true")
    assert response.status_code == 200

    data = response.json()
    assert all(contact["is_available"] for contact in data["contacts"])


def test_add_expertise_to_contact(setup_database):
    """Test adding expertise tags to a contact"""
    # Create contact first
    contact_data = {
        "phone_number": "+1234567890",
        "name": "Test User",
    }

    create_response = client.post("/api/v1/contacts/", json=contact_data)
    assert create_response.status_code == 201
    contact_id = create_response.json()["id"]

    # Add expertise
    expertise_data = {
        "expertise_tags": ["python", "machine-learning", "data-science"],
        "confidence_scores": [0.9, 0.8, 0.7],
    }

    response = client.post(
        f"/api/v1/contacts/{contact_id}/expertise", json=expertise_data
    )
    assert response.status_code == 200

    data = response.json()
    expertise_names = [tag["tag"]["name"] for tag in data["expertise_tags"]]
    assert "python" in expertise_names
    assert "machine-learning" in expertise_names
    assert "data-science" in expertise_names


def test_add_expertise_invalid_confidence_scores(setup_database):
    """Test adding expertise with mismatched confidence scores"""
    # Create contact first
    contact_data = {
        "phone_number": "+1234567890",
        "name": "Test User",
    }

    create_response = client.post("/api/v1/contacts/", json=contact_data)
    assert create_response.status_code == 201
    contact_id = create_response.json()["id"]

    # Add expertise with mismatched confidence scores
    expertise_data = {
        "expertise_tags": ["python", "machine-learning"],
        "confidence_scores": [0.9],  # Only one score for two tags
    }

    response = client.post(
        f"/api/v1/contacts/{contact_id}/expertise", json=expertise_data
    )
    assert response.status_code == 422


def test_add_expertise_contact_not_found(setup_database):
    """Test adding expertise to non-existent contact"""
    fake_id = str(uuid4())
    expertise_data = {"expertise_tags": ["python"]}

    response = client.post(f"/api/v1/contacts/{fake_id}/expertise", json=expertise_data)
    assert response.status_code == 404
