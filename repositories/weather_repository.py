#!/usr/bin/env python3
"""
Weather Repository - Database operations for weather data
"""
from datetime import date
from typing import Optional, List, Dict, Any

from .base import BaseRepository


class WeatherRepository(BaseRepository):
    """Repository for weather forecast cache operations"""

    def get_forecast_by_location(
        self,
        location_code: str,
        forecast_date: date = None
    ) -> Optional[Dict[str, Any]]:
        """Get weather forecast for a location"""
        if forecast_date is None:
            forecast_date = date.today()

        query = """
            SELECT * FROM weather_forecast_cache
            WHERE location_code = %s AND forecast_date = %s
        """
        return self.execute_query(query, (location_code, forecast_date), fetch_one=True)

    def get_forecasts_by_region(
        self,
        region: str,
        days: int = 7
    ) -> List[Dict[str, Any]]:
        """Get weather forecasts for all locations in a region"""
        query = """
            SELECT w.*, l.name, l.province
            FROM weather_forecast_cache w
            JOIN locations l ON w.location_code = l.code
            WHERE l.region = %s
              AND w.forecast_date >= CURRENT_DATE
              AND w.forecast_date < CURRENT_DATE + %s
            ORDER BY w.forecast_date, l.name
        """
        return self.execute_query(query, (region, days)) or []

    def save_forecast(
        self,
        location_code: str,
        forecast_date: date,
        data: Dict[str, Any]
    ) -> bool:
        """Save weather forecast to cache"""
        query = """
            INSERT INTO weather_forecast_cache (
                location_code, forecast_date,
                temperature_max, temperature_min,
                precipitation_sum, rain_sum,
                precipitation_hours, precipitation_probability_max,
                wind_speed_max, wind_gusts_max,
                uv_index_max, weather_code
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT (location_code, forecast_date)
            DO UPDATE SET
                temperature_max = EXCLUDED.temperature_max,
                temperature_min = EXCLUDED.temperature_min,
                precipitation_sum = EXCLUDED.precipitation_sum,
                rain_sum = EXCLUDED.rain_sum,
                precipitation_hours = EXCLUDED.precipitation_hours,
                precipitation_probability_max = EXCLUDED.precipitation_probability_max,
                wind_speed_max = EXCLUDED.wind_speed_max,
                wind_gusts_max = EXCLUDED.wind_gusts_max,
                uv_index_max = EXCLUDED.uv_index_max,
                weather_code = EXCLUDED.weather_code,
                fetched_at = CURRENT_TIMESTAMP
        """
        params = (
            location_code,
            forecast_date,
            data.get("temperature_max"),
            data.get("temperature_min"),
            data.get("precipitation_sum"),
            data.get("rain_sum"),
            data.get("precipitation_hours"),
            data.get("precipitation_probability_max"),
            data.get("wind_speed_max"),
            data.get("wind_gusts_max"),
            data.get("uv_index_max"),
            data.get("weather_code"),
        )
        return self.execute_insert(query, params)

    def get_locations(self, region: str = None) -> List[Dict[str, Any]]:
        """Get all locations, optionally filtered by region"""
        if region:
            query = """
                SELECT * FROM locations
                WHERE region = %s
                ORDER BY name
            """
            return self.execute_query(query, (region,)) or []
        else:
            query = "SELECT * FROM locations ORDER BY region, name"
            return self.execute_query(query) or []

    def get_location_by_code(self, code: str) -> Optional[Dict[str, Any]]:
        """Get a single location by code"""
        query = "SELECT * FROM locations WHERE code = %s"
        return self.execute_query(query, (code,), fetch_one=True)
