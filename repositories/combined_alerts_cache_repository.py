#!/usr/bin/env python3
"""
Combined Alerts Cache Repository - Database operations for alerts cache
"""
from datetime import date
from typing import Optional, Dict, Any, List
from psycopg2.extras import Json

from .base import BaseRepository


class CombinedAlertsCacheRepository(BaseRepository):
    """Repository for combined alerts cache operations"""

    def get_cached_alerts(
        self,
        cache_key: str = "all",
        cache_date: date = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached alerts from database

        Logic đơn giản:
        - Nếu có data của ngày hôm nay -> trả về từ DB
        - Nếu không có hoặc ngày cũ -> return None để service fetch mới

        Args:
            cache_key: Cache key ('all', 'weather', 'dam', 'reservoir_analysis')
            cache_date: Cache date (defaults to today)

        Returns:
            Dict with alerts data or None if not found
        """
        if cache_date is None:
            cache_date = date.today()

        print(f"[Alerts Cache] Đang tìm cache cho '{cache_key}', ngày {cache_date}...")

        # Chỉ lấy data của ngày hôm nay, không cần check expires
        query = """
            SELECT * FROM combined_alerts_cache
            WHERE cache_key = %s
              AND cache_date = %s
            ORDER BY fetched_at DESC
            LIMIT 1
        """

        try:
            row = self.execute_query(query, (cache_key, cache_date), fetch_one=True)

            if row is None:
                print(f"[Alerts Cache] ✗ Không tìm thấy cache cho '{cache_key}' ngày {cache_date}")
                return None

            result = dict(row)
            print(f"[Alerts Cache] ✓ Tìm thấy cache cho '{cache_key}' từ DB (ngày {cache_date})")
            return {
                "alerts": result.get("alerts_data", []),
                "summary": result.get("summary_data", {}),
                "total": result.get("total_count", 0),
                "cached_at": result.get("fetched_at").isoformat() if result.get("fetched_at") else None,
                "cache_date": str(cache_date),
                "from_cache": True
            }
        except Exception as e:
            print(f"[Alerts Cache] ✗ Lỗi khi đọc cache: {e}")
            return None

    def save_alerts(
        self,
        cache_key: str,
        alerts_data: List[Dict[str, Any]],
        summary_data: Dict[str, Any] = None,
        cache_date: date = None
    ) -> bool:
        """
        Save alerts to cache

        Args:
            cache_key: Cache key identifier
            alerts_data: List of alert objects
            summary_data: Summary statistics
            cache_date: Cache date (defaults to today)

        Returns:
            True if saved successfully
        """
        if cache_date is None:
            cache_date = date.today()

        query = """
            INSERT INTO combined_alerts_cache (
                cache_key, cache_date,
                alerts_data, summary_data, total_count
            ) VALUES (
                %s, %s, %s, %s, %s
            )
            ON CONFLICT (cache_key, cache_date)
            DO UPDATE SET
                alerts_data = EXCLUDED.alerts_data,
                summary_data = EXCLUDED.summary_data,
                total_count = EXCLUDED.total_count,
                fetched_at = CURRENT_TIMESTAMP,
                expires_at = CURRENT_TIMESTAMP + INTERVAL '1 day'
        """

        params = (
            cache_key,
            cache_date,
            Json(alerts_data),
            Json(summary_data) if summary_data else None,
            len(alerts_data)
        )

        success = self.execute_insert(query, params)
        if success:
            print(f"✓ Cached {len(alerts_data)} alerts for {cache_key} on {cache_date}")
        return success

    def cleanup_expired(self) -> int:
        """
        Delete expired cache entries

        Returns:
            Number of deleted entries
        """
        query = "SELECT cleanup_expired_combined_alerts_cache()"
        result = self.execute_query(query, fetch_one=True)
        return result[0] if result else 0

    def get_all_valid(self) -> list:
        """Get all valid cache entries for today"""
        query = """
            SELECT cache_key, cache_date, total_count, fetched_at, expires_at
            FROM combined_alerts_cache
            WHERE cache_date = CURRENT_DATE
            ORDER BY fetched_at DESC
        """
        return self.execute_query(query) or []

    def invalidate_key(self, cache_key: str) -> bool:
        """Invalidate cache for a specific key"""
        query = """
            DELETE FROM combined_alerts_cache
            WHERE cache_key = %s
        """
        return self.execute_insert(query, (cache_key,))

    def invalidate_all(self) -> bool:
        """Invalidate all cache entries"""
        query = "DELETE FROM combined_alerts_cache"
        return self.execute_insert(query)
