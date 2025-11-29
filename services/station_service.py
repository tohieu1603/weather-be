#!/usr/bin/env python3
"""
Station Service - Business logic for monitoring stations
"""
from typing import Dict, List, Optional

from data import MAJOR_STATIONS, BASIN_NAMES, BASIN_ID_MAP
from services.forecast_service import ForecastService


class StationService:
    """Service for monitoring station data"""

    def __init__(self):
        self.forecast_service = ForecastService()

    def get_all_stations(self) -> Dict:
        """Get all monitoring stations with risk levels"""
        all_data = self.forecast_service.get_all_forecasts()
        basins = all_data.get("basins", {})

        # Get risk levels for each basin
        basin_risk_levels = self._calculate_basin_risk_levels(basins)

        # Create stations list
        stations = []
        station_id = 1

        for basin_code, station_list in MAJOR_STATIONS.items():
            basin_risk = basin_risk_levels.get(basin_code, "safe")
            basin_forecast = basins.get(basin_code, {})
            current_rain = 0
            if basin_forecast.get("forecast_days"):
                current_rain = basin_forecast["forecast_days"][0].get("daily_rain", 0)

            for station_info in station_list:
                stations.append({
                    "station_id": station_id,
                    "station_name": station_info["name"],
                    "latitude": station_info["lat"],
                    "longitude": station_info["lon"],
                    "basin_id": BASIN_ID_MAP[basin_code],
                    "basin_name": BASIN_NAMES[basin_code],
                    "basin_code": basin_code,
                    "risk_level": basin_risk,
                    "current_rainfall": current_rain,
                })
                station_id += 1

        return {
            "stations": stations,
            "total_stations": len(stations),
            "generated_at": all_data.get("generated_at", "")
        }

    def get_stations_by_basin(self, basin: str) -> Dict:
        """Get stations for a specific basin"""
        basin_upper = basin.upper()
        if basin_upper not in MAJOR_STATIONS:
            return None

        all_data = self.forecast_service.get_all_forecasts()
        basins = all_data.get("basins", {})

        basin_risk_levels = self._calculate_basin_risk_levels(basins)
        basin_risk = basin_risk_levels.get(basin_upper, "safe")
        basin_forecast = basins.get(basin_upper, {})
        current_rain = 0
        if basin_forecast.get("forecast_days"):
            current_rain = basin_forecast["forecast_days"][0].get("daily_rain", 0)

        stations = []
        station_id = 1
        for station_info in MAJOR_STATIONS[basin_upper]:
            stations.append({
                "station_id": station_id,
                "station_name": station_info["name"],
                "latitude": station_info["lat"],
                "longitude": station_info["lon"],
                "basin_id": BASIN_ID_MAP[basin_upper],
                "basin_name": BASIN_NAMES[basin_upper],
                "basin_code": basin_upper,
                "risk_level": basin_risk,
                "current_rainfall": current_rain,
            })
            station_id += 1

        return {
            "basin": basin_upper,
            "stations": stations,
            "total_stations": len(stations),
            "generated_at": all_data.get("generated_at", "")
        }

    def _calculate_basin_risk_levels(self, basins: Dict) -> Dict[str, str]:
        """Calculate risk level for each basin based on forecast"""
        basin_risk_levels = {}

        for basin_code, basin_data in basins.items():
            has_danger = False
            has_warning = False
            has_watch = False

            for day in basin_data.get("forecast_days", []):
                risk = day.get("risk_level", "").upper()
                if "NGUY" in risk or "DANGER" in risk:
                    has_danger = True
                    break
                elif "CẢNH" in risk or "WARNING" in risk:
                    has_warning = True
                elif "THEO" in risk or "WATCH" in risk:
                    has_watch = True

            if has_danger:
                basin_risk_levels[basin_code] = "danger"
            elif has_warning:
                basin_risk_levels[basin_code] = "warning"
            elif has_watch:
                basin_risk_levels[basin_code] = "watch"
            else:
                basin_risk_levels[basin_code] = "safe"

        return basin_risk_levels
