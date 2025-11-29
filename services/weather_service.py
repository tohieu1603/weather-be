#!/usr/bin/env python3
"""
Weather Service - Business logic for weather data
"""
from datetime import datetime
from typing import Dict, List, Any, Optional
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from weather_api import (
    VIETNAM_LOCATIONS,
    fetch_forecast_full,
    fetch_flood_forecast,
    fetch_air_quality,
    fetch_marine_forecast,
    get_all_vietnam_weather,
    analyze_weather_for_alerts,
    get_weather_description,
    WEATHER_CODES
)
from repositories.weather_repository import WeatherRepository


class WeatherService:
    """Service for weather operations"""

    def __init__(self):
        self.repo = WeatherRepository()
        self._cache = {}
        self._cache_time = {}
        self._cache_ttl = 86400  # 24 hours

    def _is_cache_valid(self, key: str) -> bool:
        """Check if cache entry is valid"""
        if key not in self._cache or key not in self._cache_time:
            return False
        elapsed = (datetime.now() - self._cache_time[key]).total_seconds()
        return elapsed < self._cache_ttl

    def get_realtime_weather(self) -> Dict[str, Any]:
        """
        Get realtime weather for all Vietnam locations

        Returns:
            Weather data for all regions
        """
        cache_key = "realtime_all"
        if self._is_cache_valid(cache_key):
            return self._cache[cache_key]

        result = get_all_vietnam_weather()

        self._cache[cache_key] = result
        self._cache_time[cache_key] = datetime.now()

        return result

    def get_forecast_by_location(
        self,
        location: str,
        days: int = 7
    ) -> Dict[str, Any]:
        """
        Get weather forecast for a specific location

        Args:
            location: Location code
            days: Number of forecast days

        Returns:
            Forecast data
        """
        cache_key = f"forecast_{location}_{days}"
        if self._is_cache_valid(cache_key):
            return self._cache[cache_key]

        # Find location coordinates
        loc_data = VIETNAM_LOCATIONS.get(location)
        if not loc_data:
            raise ValueError(f"Location not found: {location}")

        forecast = fetch_forecast_full(
            loc_data["lat"],
            loc_data["lon"],
            days=days
        )

        result = {
            "location": location,
            "name": loc_data.get("name", location),
            "forecast": forecast,
            "generated_at": datetime.now().isoformat()
        }

        self._cache[cache_key] = result
        self._cache_time[cache_key] = datetime.now()

        return result

    def get_flood_forecast(self, location: str) -> Dict[str, Any]:
        """
        Get GloFAS flood forecast for a location

        Args:
            location: Location code

        Returns:
            Flood forecast data
        """
        loc_data = VIETNAM_LOCATIONS.get(location)
        if not loc_data:
            raise ValueError(f"Location not found: {location}")

        flood_data = fetch_flood_forecast(
            loc_data["lat"],
            loc_data["lon"]
        )

        return {
            "location": location,
            "name": loc_data.get("name", location),
            "flood_forecast": flood_data,
            "generated_at": datetime.now().isoformat()
        }

    def get_locations(self, region: str = None) -> List[Dict[str, Any]]:
        """
        Get list of locations

        Args:
            region: Optional region filter

        Returns:
            List of locations
        """
        # Try database first
        db_locations = self.repo.get_locations(region)
        if db_locations:
            return [dict(loc) for loc in db_locations]

        # Fall back to VIETNAM_LOCATIONS
        locations = []
        for code, data in VIETNAM_LOCATIONS.items():
            if region and data.get("region") != region:
                continue
            locations.append({
                "code": code,
                "name": data.get("name", code),
                "latitude": data["lat"],
                "longitude": data["lon"],
                "region": data.get("region"),
                "province": data.get("province")
            })
        return locations

    def analyze_for_alerts(self) -> List[Dict[str, Any]]:
        """
        Analyze weather data for potential alerts

        Returns:
            List of weather alerts
        """
        weather_data = self.get_realtime_weather()
        return analyze_weather_for_alerts(weather_data)
