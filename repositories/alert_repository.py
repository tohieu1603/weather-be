#!/usr/bin/env python3
"""
Alert Repository - Database operations for weather alerts
"""
from datetime import date
from typing import Optional, List, Dict, Any
from psycopg2.extras import Json

from .base import BaseRepository


class AlertRepository(BaseRepository):
    """Repository for weather alerts operations"""

    def get_alerts_by_date(
        self,
        alert_date: date = None,
        severity: str = None
    ) -> List[Dict[str, Any]]:
        """Get weather alerts by date and optionally severity"""
        if alert_date is None:
            alert_date = date.today()

        if severity:
            query = """
                SELECT * FROM weather_alerts_cache
                WHERE alert_date = %s AND severity = %s
                ORDER BY
                    CASE severity
                        WHEN 'critical' THEN 1
                        WHEN 'high' THEN 2
                        WHEN 'medium' THEN 3
                        WHEN 'low' THEN 4
                        ELSE 5
                    END
            """
            return self.execute_query(query, (alert_date, severity)) or []
        else:
            query = """
                SELECT * FROM weather_alerts_cache
                WHERE alert_date = %s
                ORDER BY
                    CASE severity
                        WHEN 'critical' THEN 1
                        WHEN 'high' THEN 2
                        WHEN 'medium' THEN 3
                        WHEN 'low' THEN 4
                        ELSE 5
                    END
            """
            return self.execute_query(query, (alert_date,)) or []

    def get_realtime_alerts(self) -> List[Dict[str, Any]]:
        """Get today's weather alerts (realtime)"""
        query = """
            SELECT * FROM weather_alerts_cache
            WHERE fetched_at >= CURRENT_DATE
            ORDER BY
                CASE severity
                    WHEN 'critical' THEN 1
                    WHEN 'high' THEN 2
                    WHEN 'medium' THEN 3
                    WHEN 'low' THEN 4
                    ELSE 5
                END,
                alert_date
        """
        return self.execute_query(query) or []

    def get_alerts_by_region(self, region: str) -> List[Dict[str, Any]]:
        """Get alerts for a specific region"""
        query = """
            SELECT * FROM weather_alerts_cache
            WHERE region = %s AND fetched_at >= CURRENT_DATE
            ORDER BY
                CASE severity
                    WHEN 'critical' THEN 1
                    WHEN 'high' THEN 2
                    WHEN 'medium' THEN 3
                    WHEN 'low' THEN 4
                    ELSE 5
                END
        """
        return self.execute_query(query, (region,)) or []

    def save_alert(self, alert_data: Dict[str, Any]) -> bool:
        """Save or update a weather alert"""
        query = """
            INSERT INTO weather_alerts_cache (
                alert_id, alert_type, category, title, severity,
                alert_date, location_code, region, provinces,
                description, data, recommendations, source
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT (alert_id)
            DO UPDATE SET
                alert_type = EXCLUDED.alert_type,
                category = EXCLUDED.category,
                title = EXCLUDED.title,
                severity = EXCLUDED.severity,
                alert_date = EXCLUDED.alert_date,
                location_code = EXCLUDED.location_code,
                region = EXCLUDED.region,
                provinces = EXCLUDED.provinces,
                description = EXCLUDED.description,
                data = EXCLUDED.data,
                recommendations = EXCLUDED.recommendations,
                source = EXCLUDED.source,
                fetched_at = CURRENT_TIMESTAMP
        """
        params = (
            alert_data.get("alert_id"),
            alert_data.get("alert_type"),
            alert_data.get("category"),
            alert_data.get("title"),
            alert_data.get("severity"),
            alert_data.get("alert_date", date.today()),
            alert_data.get("location_code"),
            alert_data.get("region"),
            alert_data.get("provinces"),
            alert_data.get("description"),
            Json(alert_data.get("data")) if alert_data.get("data") else None,
            alert_data.get("recommendations"),
            alert_data.get("source", "Open-Meteo"),
        )
        return self.execute_insert(query, params)

    def delete_old_alerts(self, days_old: int = 7) -> int:
        """Delete alerts older than specified days"""
        query = """
            DELETE FROM weather_alerts_cache
            WHERE fetched_at < CURRENT_DATE - %s
            RETURNING id
        """
        result = self.execute_query(query, (days_old,))
        return len(result) if result else 0
