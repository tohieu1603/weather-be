#!/usr/bin/env python3
"""
EVN Analysis Cache Repository - Database operations for EVN reservoir analysis cache
"""
import json
from datetime import date, datetime
from typing import Optional, Dict, Any
from psycopg2.extras import Json

from .base import BaseRepository


def convert_datetime_to_str(obj):
    """Recursively convert datetime objects to ISO strings in dict/list"""
    if isinstance(obj, dict):
        return {k: convert_datetime_to_str(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_datetime_to_str(item) for item in obj]
    elif isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, date):
        return obj.isoformat()
    return obj


class EVNAnalysisCacheRepository(BaseRepository):
    """Repository for EVN reservoir analysis cache operations"""

    def get_cached_analysis(
        self,
        basin_code: str,
        analysis_date: date = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached EVN analysis from database

        Logic đơn giản:
        - Nếu có data của ngày hôm nay -> trả về từ DB
        - Nếu không có hoặc ngày cũ -> return None để service phân tích mới

        Args:
            basin_code: Basin code (HONG, CENTRAL, MEKONG, DONGNAI)
            analysis_date: Analysis date (defaults to today)

        Returns:
            Dict with analysis data or None if not found
        """
        if analysis_date is None:
            analysis_date = date.today()

        # Chỉ lấy data của ngày hôm nay, không cần check expires
        query = """
            SELECT * FROM evn_analysis_cache
            WHERE basin_code = %s
              AND analysis_date = %s
            ORDER BY fetched_at DESC
            LIMIT 1
        """

        row = self.execute_query(query, (basin_code, analysis_date), fetch_one=True)

        if row:
            result = dict(row)
            print(f"✓ Lấy dữ liệu phân tích EVN '{basin_code}' từ DB (ngày {analysis_date})")
            return {
                "basin": result.get("basin_code"),
                "analysis": result.get("analysis_data"),
                "reservoir_status": result.get("reservoir_status"),
                "summary": result.get("summary"),
                "cached_at": result.get("fetched_at").isoformat() if result.get("fetched_at") else None,
                "analysis_date": str(analysis_date),
                "from_cache": True
            }
        return None

    def save_analysis(
        self,
        basin_code: str,
        analysis_data: Dict[str, Any],
        reservoir_status: Dict[str, Any] = None,
        analysis_date: date = None
    ) -> bool:
        """
        Save EVN analysis to cache

        Args:
            basin_code: Basin code
            analysis_data: Full analysis data dict
            reservoir_status: Reservoir status data
            analysis_date: Analysis date (defaults to today)

        Returns:
            True if saved successfully
        """
        if analysis_date is None:
            analysis_date = date.today()

        # Extract key fields for easy querying
        combined_risk = analysis_data.get("combined_risk", {})

        query = """
            INSERT INTO evn_analysis_cache (
                basin_code, analysis_date,
                analysis_data, reservoir_status,
                weather_risk, combined_risk_level, combined_risk_score,
                summary
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT (basin_code, analysis_date)
            DO UPDATE SET
                analysis_data = EXCLUDED.analysis_data,
                reservoir_status = EXCLUDED.reservoir_status,
                weather_risk = EXCLUDED.weather_risk,
                combined_risk_level = EXCLUDED.combined_risk_level,
                combined_risk_score = EXCLUDED.combined_risk_score,
                summary = EXCLUDED.summary,
                fetched_at = CURRENT_TIMESTAMP,
                expires_at = CURRENT_TIMESTAMP + INTERVAL '1 day'
        """

        # Convert datetime objects to strings before JSON serialization
        clean_analysis = convert_datetime_to_str(analysis_data)
        clean_reservoir = convert_datetime_to_str(reservoir_status) if reservoir_status else None

        params = (
            basin_code,
            analysis_date,
            Json(clean_analysis),
            Json(clean_reservoir) if clean_reservoir else None,
            Json(clean_analysis.get("weather_risk")),
            combined_risk.get("level"),
            combined_risk.get("score"),
            clean_analysis.get("summary")
        )

        success = self.execute_insert(query, params)
        if success:
            print(f"✓ Cached EVN analysis for {basin_code} on {analysis_date}")
        return success

    def cleanup_expired(self) -> int:
        """
        Delete expired cache entries

        Returns:
            Number of deleted entries
        """
        query = "SELECT cleanup_expired_evn_analysis_cache()"
        result = self.execute_query(query, fetch_one=True)
        return result[0] if result else 0

    def get_all_valid(self) -> list:
        """Get all valid cache entries for today"""
        query = """
            SELECT basin_code, analysis_date, summary, combined_risk_level,
                   combined_risk_score, fetched_at, expires_at
            FROM evn_analysis_cache
            WHERE analysis_date = CURRENT_DATE
            ORDER BY fetched_at DESC
        """
        return self.execute_query(query) or []

    def invalidate_basin(self, basin_code: str) -> bool:
        """Invalidate cache for a specific basin"""
        query = """
            DELETE FROM evn_analysis_cache
            WHERE basin_code = %s
        """
        return self.execute_insert(query, (basin_code,))

    def invalidate_all(self) -> bool:
        """Invalidate all cache entries"""
        query = "DELETE FROM evn_analysis_cache"
        return self.execute_insert(query)
