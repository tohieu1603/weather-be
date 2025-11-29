#!/usr/bin/env python3
"""
Forecast Cache Repository - Database operations for weather forecast cache

Caches the processed forecast data (basin rainfall, risk levels) to avoid
re-fetching from Open-Meteo API on every request.
"""
from datetime import date
from typing import Optional, Dict, Any
from psycopg2.extras import Json

from .base import BaseRepository


class ForecastCacheRepository(BaseRepository):
    """Repository for weather forecast cache operations"""

    def get_cached_forecast(
        self,
        forecast_date: date = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached forecast data from database.

        Args:
            forecast_date: Forecast date (defaults to today)

        Returns:
            Dict with all basins forecast data or None if not found
        """
        if forecast_date is None:
            forecast_date = date.today()

        print(f"[Forecast Cache] Đang tìm cache cho ngày {forecast_date}...")

        query = """
            SELECT * FROM forecast_cache
            WHERE forecast_date = %s
            ORDER BY fetched_at DESC
            LIMIT 1
        """

        try:
            row = self.execute_query(query, (forecast_date,), fetch_one=True)

            if row is None:
                print(f"[Forecast Cache] ✗ Không tìm thấy cache cho ngày {forecast_date}")
                return None

            result = dict(row)
            print(f"[Forecast Cache] ✓ Tìm thấy cache từ DB (ngày {forecast_date})")
            return {
                "basins": result.get("basins_data"),
                "generated_at": result.get("fetched_at").isoformat() if result.get("fetched_at") else None,
                "stations_loaded": result.get("stations_loaded"),
                "stations_failed": result.get("stations_failed") or [],
                "from_cache": True
            }
        except Exception as e:
            print(f"[Forecast Cache] ✗ Lỗi khi đọc cache: {e}")
            return None

    def save_forecast(
        self,
        basins_data: Dict[str, Any],
        stations_loaded: int = 0,
        stations_failed: list = None,
        forecast_date: date = None
    ) -> bool:
        """
        Save forecast data to cache

        Args:
            basins_data: Dict with all basins forecast data
            stations_loaded: Number of stations successfully loaded
            stations_failed: List of failed stations
            forecast_date: Forecast date (defaults to today)

        Returns:
            True if saved successfully
        """
        if forecast_date is None:
            forecast_date = date.today()

        query = """
            INSERT INTO forecast_cache (
                forecast_date, basins_data, stations_loaded, stations_failed
            ) VALUES (
                %s, %s, %s, %s
            )
            ON CONFLICT (forecast_date)
            DO UPDATE SET
                basins_data = EXCLUDED.basins_data,
                stations_loaded = EXCLUDED.stations_loaded,
                stations_failed = EXCLUDED.stations_failed,
                fetched_at = CURRENT_TIMESTAMP
        """

        params = (
            forecast_date,
            Json(basins_data),
            stations_loaded,
            Json(stations_failed or [])
        )

        success = self.execute_insert(query, params)
        if success:
            print(f"✓ Cached forecast for {forecast_date}")
        return success

    def invalidate(self, forecast_date: date = None) -> bool:
        """
        Invalidate forecast cache for a specific date

        Args:
            forecast_date: Date to invalidate (defaults to today)

        Returns:
            True if deleted successfully
        """
        if forecast_date is None:
            forecast_date = date.today()

        query = "DELETE FROM forecast_cache WHERE forecast_date = %s"
        return self.execute_insert(query, (forecast_date,))

    def cleanup_old(self, days: int = 7) -> int:
        """
        Delete old cache entries

        Args:
            days: Delete entries older than this many days

        Returns:
            Number of deleted entries
        """
        query = """
            DELETE FROM forecast_cache
            WHERE forecast_date < CURRENT_DATE - %s
        """
        return self.execute_insert(query, (days,))
