#!/usr/bin/env python3
"""
AI Cache Repository - Database operations for AI analysis cache
"""
from datetime import date
from typing import Optional, Dict, Any
from psycopg2.extras import Json

from .base import BaseRepository


class AICacheRepository(BaseRepository):
    """Repository for AI analysis cache operations"""

    def get_cached_analysis(
        self,
        basin_code: str,
        analysis_date: date = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached AI analysis from database.

        Logic đơn giản:
        - Nếu có data của ngày hôm nay -> trả về từ DB
        - Nếu không có hoặc ngày cũ -> return None để service gọi AI mới

        Args:
            basin_code: Basin code (HONG, CENTRAL, MEKONG, DONGNAI)
            analysis_date: Analysis date (defaults to today)

        Returns:
            Dict with analysis data or None if not found for today
        """
        if analysis_date is None:
            analysis_date = date.today()

        print(f"[AI Cache] Đang tìm cache cho {basin_code}, ngày {analysis_date}...")

        # Chỉ lấy data của ngày hôm nay, không cần check expires
        query = """
            SELECT * FROM ai_analysis_cache
            WHERE basin_code = %s
              AND analysis_date = %s
            ORDER BY fetched_at DESC
            LIMIT 1
        """

        try:
            row = self.execute_query(query, (basin_code, analysis_date), fetch_one=True)

            if row is None:
                print(f"[AI Cache] ✗ Không tìm thấy cache cho {basin_code} ngày {analysis_date}")
                return None

            result = dict(row)
            print(f"[AI Cache] ✓ Tìm thấy cache cho {basin_code} từ DB (ngày {analysis_date})")
            return {
                "peak_rain": result.get("peak_rain"),
                "flood_timeline": result.get("flood_timeline"),
                "affected_areas": result.get("affected_areas"),
                "overall_risk": result.get("overall_risk"),
                "recommendations": result.get("recommendations"),
                "summary": result.get("summary"),
                "analysis_date": str(analysis_date),
                "fetched_at": result.get("fetched_at").isoformat() if result.get("fetched_at") else None,
                "from_cache": True
            }
        except Exception as e:
            print(f"[AI Cache] ✗ Lỗi khi đọc cache: {e}")
            return None

    def save_analysis(
        self,
        basin_code: str,
        analysis: Dict[str, Any],
        analysis_date: date = None,
        tokens_used: int = None
    ) -> bool:
        """
        Save AI analysis to cache

        Args:
            basin_code: Basin code
            analysis: Analysis data dict
            analysis_date: Analysis date (defaults to today)
            tokens_used: Number of tokens used in API call

        Returns:
            True if saved successfully
        """
        if analysis_date is None:
            analysis_date = date.today()

        query = """
            INSERT INTO ai_analysis_cache (
                basin_code, analysis_date,
                peak_rain, flood_timeline, affected_areas,
                overall_risk, recommendations, summary,
                raw_response, tokens_used
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT (basin_code, analysis_date)
            DO UPDATE SET
                peak_rain = EXCLUDED.peak_rain,
                flood_timeline = EXCLUDED.flood_timeline,
                affected_areas = EXCLUDED.affected_areas,
                overall_risk = EXCLUDED.overall_risk,
                recommendations = EXCLUDED.recommendations,
                summary = EXCLUDED.summary,
                raw_response = EXCLUDED.raw_response,
                tokens_used = EXCLUDED.tokens_used,
                fetched_at = CURRENT_TIMESTAMP,
                expires_at = CURRENT_TIMESTAMP + INTERVAL '1 day'
        """

        params = (
            basin_code,
            analysis_date,
            Json(analysis.get("peak_rain")),
            Json(analysis.get("flood_timeline")),
            Json(analysis.get("affected_areas")),
            Json(analysis.get("overall_risk")),
            Json(analysis.get("recommendations")),
            analysis.get("summary"),
            Json(analysis),
            tokens_used
        )

        success = self.execute_insert(query, params)
        if success:
            print(f"✓ Cached AI analysis for {basin_code} on {analysis_date}")
        return success

    def cleanup_expired(self) -> int:
        """
        Delete expired cache entries

        Returns:
            Number of deleted entries
        """
        query = "SELECT cleanup_expired_ai_cache()"
        result = self.execute_query(query, fetch_one=True)
        return result[0] if result else 0

    def get_all_valid(self) -> list:
        """Get all valid (non-expired) cache entries"""
        query = """
            SELECT basin_code, analysis_date, summary, fetched_at, expires_at
            FROM ai_analysis_cache
            WHERE expires_at > CURRENT_TIMESTAMP
            ORDER BY fetched_at DESC
        """
        return self.execute_query(query) or []
