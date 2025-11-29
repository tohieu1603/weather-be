#!/usr/bin/env python3
"""
Dam Repository - Database operations for dam data
"""
from datetime import date
from typing import Optional, List, Dict, Any
from psycopg2.extras import Json

from .base import BaseRepository


class DamRepository(BaseRepository):
    """Repository for dam and dam alerts operations"""

    def get_all_dams(self) -> List[Dict[str, Any]]:
        """Get all dams"""
        query = "SELECT * FROM dams ORDER BY name"
        return self.execute_query(query) or []

    def get_dams_by_basin(self, basin: str) -> List[Dict[str, Any]]:
        """Get dams in a specific basin"""
        query = "SELECT * FROM dams WHERE basin = %s ORDER BY name"
        return self.execute_query(query, (basin,)) or []

    def get_dam_by_code(self, code: str) -> Optional[Dict[str, Any]]:
        """Get a single dam by code"""
        query = "SELECT * FROM dams WHERE code = %s"
        return self.execute_query(query, (code,), fetch_one=True)

    def get_dam_alerts(
        self,
        basin: str = None,
        alert_date: date = None
    ) -> List[Dict[str, Any]]:
        """Get dam alerts, optionally filtered by basin and date"""
        if alert_date is None:
            alert_date = date.today()

        if basin:
            query = """
                SELECT d.*, dm.name as dam_name, dm.river, dm.province,
                       dm.max_discharge_m3s, dm.spillway_gates as total_gates,
                       dm.warning_time_hours, dm.downstream_areas
                FROM dam_alerts_cache d
                JOIN dams dm ON d.dam_code = dm.code
                WHERE dm.basin = %s AND d.alert_date = %s
                ORDER BY
                    CASE d.alert_level
                        WHEN 'emergency' THEN 1
                        WHEN 'warning' THEN 2
                        WHEN 'watch' THEN 3
                        ELSE 4
                    END
            """
            return self.execute_query(query, (basin, alert_date)) or []
        else:
            query = """
                SELECT d.*, dm.name as dam_name, dm.river, dm.province,
                       dm.max_discharge_m3s, dm.spillway_gates as total_gates,
                       dm.warning_time_hours, dm.downstream_areas
                FROM dam_alerts_cache d
                JOIN dams dm ON d.dam_code = dm.code
                WHERE d.alert_date = %s
                ORDER BY
                    CASE d.alert_level
                        WHEN 'emergency' THEN 1
                        WHEN 'warning' THEN 2
                        WHEN 'watch' THEN 3
                        ELSE 4
                    END
            """
            return self.execute_query(query, (alert_date,)) or []

    def get_realtime_dam_alerts(self) -> List[Dict[str, Any]]:
        """Get today's dam alerts (realtime)"""
        query = """
            SELECT d.*, dm.name as dam_name, dm.river, dm.province,
                   dm.max_discharge_m3s, dm.spillway_gates as total_gates,
                   dm.warning_time_hours, dm.downstream_areas,
                   dm.latitude, dm.longitude
            FROM dam_alerts_cache d
            JOIN dams dm ON d.dam_code = dm.code
            WHERE d.fetched_at >= CURRENT_DATE
            ORDER BY
                CASE d.alert_level
                    WHEN 'emergency' THEN 1
                    WHEN 'warning' THEN 2
                    WHEN 'watch' THEN 3
                    ELSE 4
                END,
                d.alert_date
        """
        return self.execute_query(query) or []

    def save_dam_alert(
        self,
        dam_code: str,
        alert_data: Dict[str, Any]
    ) -> bool:
        """Save or update a dam alert"""
        query = """
            INSERT INTO dam_alerts_cache (
                dam_code, alert_date, alert_level,
                rainfall_mm, rainfall_accumulated_mm,
                estimated_discharge_m3s, estimated_water_level_m,
                spillway_gates_open, river_discharge_glofas,
                description, recommendations
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT (dam_code, alert_date)
            DO UPDATE SET
                alert_level = EXCLUDED.alert_level,
                rainfall_mm = EXCLUDED.rainfall_mm,
                rainfall_accumulated_mm = EXCLUDED.rainfall_accumulated_mm,
                estimated_discharge_m3s = EXCLUDED.estimated_discharge_m3s,
                estimated_water_level_m = EXCLUDED.estimated_water_level_m,
                spillway_gates_open = EXCLUDED.spillway_gates_open,
                river_discharge_glofas = EXCLUDED.river_discharge_glofas,
                description = EXCLUDED.description,
                recommendations = EXCLUDED.recommendations,
                fetched_at = CURRENT_TIMESTAMP
        """
        params = (
            dam_code,
            alert_data.get("alert_date", date.today()),
            alert_data.get("alert_level"),
            alert_data.get("rainfall_mm"),
            alert_data.get("rainfall_accumulated_mm"),
            alert_data.get("estimated_discharge_m3s"),
            alert_data.get("estimated_water_level_m"),
            alert_data.get("spillway_gates_open"),
            alert_data.get("river_discharge_glofas"),
            alert_data.get("description"),
            alert_data.get("recommendations"),
        )
        return self.execute_insert(query, params)
