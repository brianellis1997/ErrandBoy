"""Geographic utilities for location-based matching"""

import math
import re
from datetime import datetime, timezone
from typing import Any


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great circle distance between two points on Earth
    Returns distance in kilometers
    """
    R = 6371  # Earth's radius in kilometers
    
    # Convert to radians
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    
    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    
    return R * c


def extract_coordinates(location_data: dict[str, Any] | None) -> tuple[float, float] | None:
    """Extract latitude and longitude from location metadata"""
    if not location_data:
        return None
    
    # Try different common formats
    if "lat" in location_data and "lon" in location_data:
        return float(location_data["lat"]), float(location_data["lon"])
    
    if "latitude" in location_data and "longitude" in location_data:
        return float(location_data["latitude"]), float(location_data["longitude"])
    
    if "coordinates" in location_data:
        coords = location_data["coordinates"]
        if isinstance(coords, list) and len(coords) == 2:
            return float(coords[1]), float(coords[0])  # GeoJSON is [lon, lat]
    
    return None


def is_local_query(query_text: str) -> bool:
    """
    Detect if a query is location-specific and would benefit from geographic matching
    """
    local_keywords = [
        # Weather
        "weather", "temperature", "rain", "snow", "forecast", "climate",
        
        # Events and activities
        "event", "concert", "festival", "market", "meeting", "conference",
        "restaurant", "bar", "cafe", "shop", "store", "mall",
        
        # Services
        "doctor", "dentist", "mechanic", "plumber", "electrician", 
        "lawyer", "hospital", "clinic", "pharmacy",
        
        # Transportation
        "traffic", "parking", "bus", "train", "subway", "taxi", "uber",
        
        # Local references
        "near me", "nearby", "local", "around here", "in my area",
        "best place", "where can i", "how to get to",
        
        # Time-sensitive local
        "open now", "hours", "today", "this weekend", "currently"
    ]
    
    query_lower = query_text.lower()
    
    # Check for explicit local indicators
    if any(keyword in query_lower for keyword in local_keywords):
        return True
    
    # Check for city/location patterns (basic)
    location_patterns = [
        r"\bin\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b",  # "in Chicago", "in New York"
        r"\b[A-Z][a-z]+,\s*[A-Z]{2}\b",              # "Chicago, IL"
        r"\bzip\s*code\s*\d{5}\b",                   # "zip code 60601"
    ]
    
    for pattern in location_patterns:
        if re.search(pattern, query_text):
            return True
    
    return False


def get_timezone_offset(location_data: dict[str, Any] | None) -> int | None:
    """
    Get timezone offset from location data
    Returns offset in hours from UTC (naive implementation)
    """
    if not location_data:
        return None
    
    if "timezone" in location_data:
        tz_name = location_data["timezone"]
        
        # Simple mapping of common US timezones
        timezone_offsets = {
            "America/New_York": -5,     # EST (winter) / -4 EDT (summer)
            "America/Chicago": -6,      # CST (winter) / -5 CDT (summer)
            "America/Denver": -7,       # MST (winter) / -6 MDT (summer)  
            "America/Los_Angeles": -8,  # PST (winter) / -7 PDT (summer)
            "America/Phoenix": -7,      # Arizona (no DST)
            "Pacific/Honolulu": -10,    # Hawaii
            "America/Anchorage": -9,    # Alaska
        }
        
        return timezone_offsets.get(tz_name)
    
    if "utc_offset" in location_data:
        return int(location_data["utc_offset"])
    
    # Rough approximation based on longitude
    coords = extract_coordinates(location_data)
    if coords:
        _, lon = coords
        # Very rough: 15 degrees longitude ≈ 1 hour
        return int(lon / 15)
    
    return None


def is_business_hours(timezone_offset: int | None, current_time: datetime | None = None) -> bool:
    """
    Check if it's business hours in the given timezone
    Business hours: 9 AM - 6 PM local time, Monday-Friday
    """
    if timezone_offset is None:
        return True  # Assume available if timezone unknown
    
    if current_time is None:
        current_time = datetime.now(timezone.utc)
    
    # Calculate local time
    local_time = current_time.replace(tzinfo=timezone.utc)
    local_hour = (local_time.hour + timezone_offset) % 24
    local_weekday = local_time.weekday()  # 0=Monday, 6=Sunday
    
    # Check if it's a weekday (Monday-Friday)
    is_weekday = local_weekday < 5
    
    # Check if it's business hours (9 AM - 6 PM)
    is_business_time = 9 <= local_hour < 18
    
    return is_weekday and is_business_time


def calculate_geographic_boost(
    query_coords: tuple[float, float] | None,
    expert_coords: tuple[float, float] | None,
    max_boost: float = 0.2,
    max_distance_km: float = 100.0
) -> float:
    """
    Calculate geographic proximity boost for local queries
    Returns a value between 0.0 and max_boost
    """
    if not query_coords or not expert_coords:
        return 0.0
    
    distance = haversine_distance(*query_coords, *expert_coords)
    
    # Linear decay: full boost at 0km, no boost at max_distance_km
    if distance >= max_distance_km:
        return 0.0
    
    boost_factor = 1.0 - (distance / max_distance_km)
    return max_boost * boost_factor