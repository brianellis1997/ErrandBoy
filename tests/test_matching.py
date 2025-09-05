"""Tests for expert matching system"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4
from unittest.mock import AsyncMock, patch

from groupchat.db.models import Contact, ContactStatus, Query, QueryStatus, ExpertiseTag
from groupchat.schemas.matching import MatchingRequest
from groupchat.services.matching import ExpertMatchingService
from groupchat.utils.geographic import (
    haversine_distance,
    extract_coordinates,
    is_local_query,
    calculate_geographic_boost
)


class TestGeographicUtils:
    """Test geographic utility functions"""
    
    def test_haversine_distance(self):
        """Test distance calculation between two points"""
        # Chicago to New York (approximately 1145 km)
        chicago_lat, chicago_lon = 41.8781, -87.6298
        ny_lat, ny_lon = 40.7128, -74.0060
        
        distance = haversine_distance(chicago_lat, chicago_lon, ny_lat, ny_lon)
        assert 1100 <= distance <= 1200  # Allow some margin
    
    def test_extract_coordinates(self):
        """Test coordinate extraction from different formats"""
        # Standard lat/lon format
        location1 = {"lat": 40.7128, "lon": -74.0060}
        coords1 = extract_coordinates(location1)
        assert coords1 == (40.7128, -74.0060)
        
        # Latitude/longitude format
        location2 = {"latitude": 40.7128, "longitude": -74.0060}
        coords2 = extract_coordinates(location2)
        assert coords2 == (40.7128, -74.0060)
        
        # GeoJSON format (lon, lat order)
        location3 = {"coordinates": [-74.0060, 40.7128]}
        coords3 = extract_coordinates(location3)
        assert coords3 == (40.7128, -74.0060)
        
        # Invalid format
        location4 = {"city": "New York"}
        coords4 = extract_coordinates(location4)
        assert coords4 is None
    
    def test_is_local_query(self):
        """Test local query detection"""
        # Local queries
        assert is_local_query("What's the weather like today?") == True
        assert is_local_query("Any good restaurants near me?") == True
        assert is_local_query("Traffic on I-95 today") == True
        assert is_local_query("Events in Chicago this weekend") == True
        assert is_local_query("Where can I find a good mechanic?") == True
        
        # Non-local queries
        assert is_local_query("How do I write Python code?") == False
        assert is_local_query("What is machine learning?") == False
        assert is_local_query("Explain quantum physics") == False
    
    def test_calculate_geographic_boost(self):
        """Test geographic proximity boost calculation"""
        # Same location - maximum boost
        boost1 = calculate_geographic_boost(
            (40.7128, -74.0060), (40.7128, -74.0060), max_boost=0.2
        )
        assert boost1 == 0.2
        
        # 50km distance - half boost
        chicago = (41.8781, -87.6298)
        nearby = (41.7781, -87.6298)  # Roughly 11km south
        boost2 = calculate_geographic_boost(chicago, nearby, max_boost=0.2, max_distance_km=100)
        assert 0.15 <= boost2 <= 0.2
        
        # Very far distance - no boost
        ny = (40.7128, -74.0060)
        boost3 = calculate_geographic_boost(chicago, ny, max_boost=0.2, max_distance_km=100)
        assert boost3 == 0.0
        
        # No coordinates - no boost
        boost4 = calculate_geographic_boost(None, chicago, max_boost=0.2)
        assert boost4 == 0.0


@pytest.mark.asyncio
class TestExpertMatchingService:
    """Test the expert matching service"""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return AsyncMock()
    
    @pytest.fixture
    def sample_query(self):
        """Sample query for testing"""
        return Query(
            id=uuid4(),
            user_phone="+15551234567",
            question_text="I need help with Python web development",
            question_embedding=[0.1] * 1536,  # Mock embedding
            status=QueryStatus.PENDING,
            max_experts=5,
            min_experts=3,
            timeout_minutes=30,
            total_cost_cents=500,
            platform_fee_cents=100,
            context={}
        )
    
    @pytest.fixture
    def sample_experts(self):
        """Sample experts for testing"""
        return [
            Contact(
                id=uuid4(),
                phone_number="+15551111111",
                name="Alice Python Expert",
                bio="Senior Python developer with 10 years experience",
                expertise_embedding=[0.2] * 1536,  # Mock embedding
                trust_score=0.9,
                response_rate=0.8,
                is_available=True,
                status=ContactStatus.ACTIVE,
                extra_metadata={"location": {"lat": 40.7128, "lon": -74.0060}}
            ),
            Contact(
                id=uuid4(),
                phone_number="+15552222222",
                name="Bob Web Developer",
                bio="Full-stack web developer specializing in Django",
                expertise_embedding=[0.15] * 1536,  # Mock embedding
                trust_score=0.7,
                response_rate=0.9,
                is_available=True,
                status=ContactStatus.ACTIVE,
                extra_metadata={"location": {"lat": 40.7589, "lon": -73.9851}}
            ),
            Contact(
                id=uuid4(),
                phone_number="+15553333333",
                name="Charlie Data Scientist",
                bio="Data scientist with Python and machine learning expertise",
                expertise_embedding=[0.05] * 1536,  # Lower similarity
                trust_score=0.8,
                response_rate=0.6,
                is_available=False,  # Not available
                status=ContactStatus.ACTIVE,
                extra_metadata={}
            )
        ]
    
    async def test_match_experts_basic(self, mock_db, sample_query, sample_experts):
        """Test basic expert matching functionality"""
        service = ExpertMatchingService(mock_db)
        
        # Mock the database queries
        with patch.object(service, '_get_candidate_experts', return_value=sample_experts):
            with patch.object(service, '_filter_available_experts', return_value=sample_experts[:2]):
                with patch.object(service, '_exclude_recent_contacts', return_value=sample_experts[:2]):
                    with patch.object(service, '_vector_similarity_search') as mock_similarity:
                        mock_similarity.return_value = [
                            (sample_experts[0], 0.85),  # High similarity
                            (sample_experts[1], 0.70),  # Medium similarity
                        ]
                        
                        with patch.object(service, '_extract_query_tags', return_value={"python", "web"}):
                            with patch.object(service, '_calculate_tag_overlap') as mock_overlap:
                                mock_overlap.side_effect = [0.8, 0.6]  # Tag overlaps
                                
                                request = MatchingRequest(query_id=sample_query.id, limit=5)
                                result = await service.match_experts(sample_query, request)
                                
                                # Verify results
                                assert result.query_id == sample_query.id
                                assert len(result.matches) <= 2  # Only available experts
                                assert result.total_candidates == 3
                                assert result.search_time_ms > 0
                                
                                # Check scoring
                                top_match = result.matches[0]
                                assert top_match.contact.name == "Alice Python Expert"
                                assert top_match.scores.final_score > 0.5
                                assert len(top_match.match_reasons) > 0
    
    async def test_vector_similarity_search(self, mock_db, sample_query, sample_experts):
        """Test vector similarity search functionality"""
        service = ExpertMatchingService(mock_db)
        
        # Mock database query for similarity search
        mock_result = AsyncMock()
        mock_result.fetchall.return_value = [
            AsyncMock(id=sample_experts[0].id, similarity=0.85),
            AsyncMock(id=sample_experts[1].id, similarity=0.70),
        ]
        mock_db.execute.return_value = mock_result
        
        # Test similarity search
        matches = await service._vector_similarity_search(sample_query, sample_experts[:2])
        
        assert len(matches) == 2
        assert matches[0][1] == 0.85  # Higher similarity first
        assert matches[1][1] == 0.70
        assert matches[0][0].id == sample_experts[0].id
    
    async def test_tag_overlap_calculation(self, mock_db):
        """Test expertise tag overlap calculation"""
        service = ExpertMatchingService(mock_db)
        
        # Create expert with expertise tags
        expert = Contact(
            id=uuid4(),
            phone_number="+15551111111",
            name="Test Expert",
            status=ContactStatus.ACTIVE,
            expertise_tags=[
                ExpertiseTag(name="Python", category="Programming"),
                ExpertiseTag(name="Django", category="Framework"),
                ExpertiseTag(name="REST API", category="Architecture")
            ]
        )
        
        query_tags = {"python", "django", "web"}
        
        overlap = await service._calculate_tag_overlap(expert, query_tags)
        
        # Should have overlap for python and django
        # Jaccard similarity: intersection/union = 2/4 = 0.5
        assert overlap == 0.5
    
    async def test_geographic_boost_integration(self, mock_db, sample_query):
        """Test geographic boost integration in scoring"""
        service = ExpertMatchingService(mock_db)
        
        # Local query with location
        local_query = Query(
            id=uuid4(),
            user_phone="+15551234567",
            question_text="What's the weather like today?",
            question_embedding=[0.1] * 1536,
            status=QueryStatus.PENDING,
            max_experts=5,
            min_experts=3,
            timeout_minutes=30,
            total_cost_cents=500,
            platform_fee_cents=100,
            context={"location": {"lat": 40.7128, "lon": -74.0060}}  # NYC
        )
        
        # Expert nearby
        nearby_expert = Contact(
            id=uuid4(),
            phone_number="+15551111111",
            name="Local Expert",
            bio="Local NYC expert",
            expertise_embedding=[0.2] * 1536,
            trust_score=0.7,
            response_rate=0.8,
            is_available=True,
            status=ContactStatus.ACTIVE,
            extra_metadata={"location": {"lat": 40.7589, "lon": -73.9851}}  # Manhattan
        )
        
        similarity_matches = [(nearby_expert, 0.6)]
        
        with patch.object(service, '_extract_query_tags', return_value=set()):
            with patch.object(service, '_calculate_tag_overlap', return_value=0.3):
                with patch.object(service, '_get_recent_query_count', return_value=0):
                    
                    request = MatchingRequest(query_id=local_query.id, location_boost=True)
                    matches = await service._calculate_match_scores(
                        local_query, similarity_matches, request
                    )
                    
                    assert len(matches) == 1
                    match = matches[0]
                    
                    # Should have geographic boost
                    assert match.scores.geographic_boost > 0
                    assert match.distance_km is not None
                    assert match.distance_km < 50  # Should be nearby
    
    async def test_diversity_filtering(self, mock_db):
        """Test diversity filtering functionality"""
        service = ExpertMatchingService(mock_db)
        
        # Create multiple experts with similar expertise
        similar_experts = []
        for i in range(5):
            expert = Contact(
                id=uuid4(),
                phone_number=f"+155511111{i}",
                name=f"Python Expert {i}",
                status=ContactStatus.ACTIVE,
                expertise_tags=[
                    ExpertiseTag(name="Python", category="Programming"),
                    ExpertiseTag(name="Django", category="Framework")
                ]
            )
            similar_experts.append(expert)
        
        # Create matches with similar expertise
        from groupchat.schemas.matching import ExpertMatch, ExpertMatchScores
        from groupchat.schemas.contacts import ContactResponse
        
        matches = []
        for expert in similar_experts:
            scores = ExpertMatchScores(
                embedding_similarity=0.8,
                tag_overlap=0.7,
                trust_score=0.8,
                availability_boost=1.0,
                responsiveness_rate=0.8,
                final_score=0.8
            )
            match = ExpertMatch(
                contact=ContactResponse.model_validate(expert),
                scores=scores,
                availability_status="available"
            )
            matches.append(match)
        
        request = MatchingRequest(query_id=uuid4(), limit=10)
        diverse_matches = service._apply_diversity_filter(matches)
        
        # Should reduce similar matches but not eliminate all
        assert len(diverse_matches) < len(matches)
        assert len(diverse_matches) >= 2  # Should keep some variety
    
    async def test_wave_grouping(self, mock_db):
        """Test wave-based grouping functionality"""
        service = ExpertMatchingService(mock_db)
        
        # Create 7 matches to test wave grouping
        from groupchat.schemas.matching import ExpertMatch, ExpertMatchScores
        from groupchat.schemas.contacts import ContactResponse
        
        matches = []
        for i in range(7):
            expert = Contact(
                id=uuid4(),
                phone_number=f"+155511111{i}",
                name=f"Expert {i}",
                status=ContactStatus.ACTIVE
            )
            
            scores = ExpertMatchScores(
                embedding_similarity=0.8,
                tag_overlap=0.7,
                trust_score=0.8,
                availability_boost=1.0,
                responsiveness_rate=0.8,
                final_score=0.8
            )
            
            match = ExpertMatch(
                contact=ContactResponse.model_validate(expert),
                scores=scores,
                availability_status="available"
            )
            matches.append(match)
        
        # Apply wave grouping with wave size 3
        wave_grouped = service._apply_wave_grouping(matches, wave_size=3)
        
        # Check wave assignments
        assert wave_grouped[0].wave_group == 1  # First wave
        assert wave_grouped[1].wave_group == 1
        assert wave_grouped[2].wave_group == 1
        assert wave_grouped[3].wave_group == 2  # Second wave
        assert wave_grouped[4].wave_group == 2
        assert wave_grouped[5].wave_group == 2
        assert wave_grouped[6].wave_group == 3  # Third wave


@pytest.mark.asyncio
class TestMatchingIntegration:
    """Integration tests for the matching system"""
    
    async def test_end_to_end_matching_flow(self):
        """Test the complete matching flow from query to results"""
        # This would be a more comprehensive integration test
        # that tests the full flow with a real or more realistic mock database
        pass
    
    async def test_performance_requirements(self):
        """Test that matching meets the <100ms performance requirement"""
        # This would test with a larger dataset to ensure performance
        pass