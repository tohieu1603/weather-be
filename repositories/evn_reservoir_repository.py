#!/usr/bin/env python3
"""
EVN Reservoir Repository - Database operations for hydropower reservoir data
"""
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Any, Optional

from .base import BaseRepository


def convert_decimal(obj):
    """Convert Decimal to float for JSON serialization"""
    if isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, dict):
        return {k: convert_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_decimal(item) for item in obj]
    return obj


class EVNReservoirRepository(BaseRepository):
    """Repository for EVN reservoir data operations"""

    def save_reservoir(self, data: Dict[str, Any]) -> bool:
        """
        Save reservoir data to database

        Args:
            data: Reservoir data dict with keys:
                name, htl, hdbt, hc, qve, total_qx, qxt, qxm, ncxs, ncxm

        Returns:
            True if saved successfully
        """
        query = """
            INSERT INTO evn_reservoirs (
                name, htl, hdbt, hc, qve, total_qx, qxt, qxm, ncxs, ncxm
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
        """
        params = (
            data.get("name"),
            data.get("htl"),
            data.get("hdbt"),
            data.get("hc"),
            data.get("qve"),
            data.get("total_qx"),
            data.get("qxt"),
            data.get("qxm"),
            data.get("ncxs"),
            data.get("ncxm"),
        )
        return self.execute_insert(query, params)

    def save_batch(self, reservoirs: List[Dict[str, Any]]) -> int:
        """
        Save multiple reservoirs at once

        Args:
            reservoirs: List of reservoir data dicts

        Returns:
            Number of successfully saved records
        """
        count = 0
        for data in reservoirs:
            if self.save_reservoir(data):
                count += 1
        return count

    def get_latest(self, name: str = None) -> List[Dict[str, Any]]:
        """
        Get latest reservoir data

        Args:
            name: Optional reservoir name filter

        Returns:
            List of reservoir records
        """
        if name:
            query = """
                SELECT DISTINCT ON (name)
                    name, htl, hdbt, hc, qve, total_qx, qxt, qxm, ncxs, ncxm, fetched_at
                FROM evn_reservoirs
                WHERE name = %s
                ORDER BY name, fetched_at DESC
            """
            rows = self.execute_query(query, (name,))
        else:
            query = """
                SELECT DISTINCT ON (name)
                    name, htl, hdbt, hc, qve, total_qx, qxt, qxm, ncxs, ncxm, fetched_at
                FROM evn_reservoirs
                ORDER BY name, fetched_at DESC
            """
            rows = self.execute_query(query)

        if not rows:
            return []

        return [convert_decimal(dict(row)) for row in rows]

    def get_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Get latest data for a specific reservoir"""
        results = self.get_latest(name)
        return results[0] if results else None

    def get_high_discharge(self, threshold_percent: float = 70) -> List[Dict[str, Any]]:
        """
        Get reservoirs with high discharge rate

        Args:
            threshold_percent: Minimum discharge percentage to filter

        Returns:
            List of reservoirs exceeding threshold
        """
        query = """
            SELECT DISTINCT ON (name)
                name, htl, hdbt, hc, qve, total_qx, qxt, qxm, ncxs, ncxm, fetched_at,
                CASE WHEN hdbt > 0 THEN (htl / hdbt * 100) ELSE 0 END as water_percent
            FROM evn_reservoirs
            WHERE total_qx > 0
            ORDER BY name, fetched_at DESC
        """
        rows = self.execute_query(query)

        if not rows:
            return []

        # Filter by water level percent
        results = []
        for row in rows:
            data = convert_decimal(dict(row))
            if data.get("water_percent", 0) >= threshold_percent:
                results.append(data)

        return results

    def get_spillway_open(self) -> List[Dict[str, Any]]:
        """Get reservoirs with spillway gates open"""
        query = """
            SELECT DISTINCT ON (name)
                name, htl, hdbt, hc, qve, total_qx, qxt, qxm, ncxs, ncxm, fetched_at
            FROM evn_reservoirs
            WHERE ncxs > 0 OR ncxm > 0
            ORDER BY name, fetched_at DESC
        """
        rows = self.execute_query(query)
        return [convert_decimal(dict(row)) for row in rows] if rows else []

    def cleanup_old_data(self, days: int = 7) -> int:
        """
        Delete data older than specified days

        Args:
            days: Number of days to keep

        Returns:
            Number of deleted records
        """
        query = """
            DELETE FROM evn_reservoirs
            WHERE fetched_at < CURRENT_TIMESTAMP - INTERVAL '%s days'
            RETURNING id
        """
        result = self.execute_query(query, (days,))
        return len(result) if result else 0

    def get_today_data(self) -> List[Dict[str, Any]]:
        """
        Get reservoir data for today only

        Returns:
            List of reservoir records from today, or empty list if none
        """
        query = """
            SELECT DISTINCT ON (name)
                name, htl, hdbt, hc, qve, total_qx, qxt, qxm, ncxs, ncxm, fetched_at
            FROM evn_reservoirs
            WHERE DATE(fetched_at) = CURRENT_DATE
            ORDER BY name, fetched_at DESC
        """
        rows = self.execute_query(query)
        if not rows:
            return []
        return [convert_decimal(dict(row)) for row in rows]

    def has_today_data(self) -> bool:
        """Check if we have data for today"""
        query = """
            SELECT COUNT(*) as cnt FROM evn_reservoirs
            WHERE DATE(fetched_at) = CURRENT_DATE
        """
        result = self.execute_query(query, fetch_one=True)
        if not result:
            return False
        # Handle both dict and tuple results
        if isinstance(result, dict):
            return result.get('cnt', 0) > 0
        return result[0] > 0
