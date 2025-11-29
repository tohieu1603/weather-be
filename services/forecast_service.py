#!/usr/bin/env python3
"""
Forecast Service - Business logic for flood forecasts
"""
from datetime import datetime
from typing import Dict, List, Any, Optional
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from p import (
    MONITORING_POINTS,
    BASIN_WEIGHTS,
    FLOOD_THRESHOLDS,
    fetch_weather_data,
    calculate_basin_rainfall,
    analyze_basin_forecast
)


class ForecastService:
    """Service for flood forecast operations"""

    def __init__(self):
        self._cache = None
        self._cache_time = None
        self._cache_ttl = 86400  # 24 hours

    def _is_cache_valid(self) -> bool:
        """Check if cache is still valid"""
        if self._cache is None or self._cache_time is None:
            return False
        elapsed = (datetime.now() - self._cache_time).total_seconds()
        return elapsed < self._cache_ttl

    def get_all_forecasts(self) -> Dict[str, Any]:
        """
        Get flood forecasts for all basins

        Returns:
            Dict with basin forecasts and metadata
        """
        if self._is_cache_valid():
            return self._cache

        # Fetch weather data for all monitoring points
        print("Fetching fresh weather data...")
        station_data = {}
        dates_ref = None
        failed_stations = []

        for code, info in MONITORING_POINTS.items():
            try:
                data = fetch_weather_data(info["lat"], info["lon"])
                if dates_ref is None:
                    dates_ref = data["daily"]["time"]
                station_data[code] = data["daily"]["precipitation_sum"]
            except Exception as e:
                failed_stations.append({"station": code, "error": str(e)})
                print(f"Failed to fetch {code}: {e}")

        if not dates_ref:
            raise Exception("Không thể lấy dữ liệu thời tiết")

        # Analyze each basin
        all_analysis = {}
        for basin, weights in BASIN_WEIGHTS.items():
            basin_rainfall = []
            for idx in range(len(dates_ref)):
                day_points = {
                    st: {"precipitation_sum": station_data.get(st, [0] * len(dates_ref))[idx]}
                    for st in weights.keys()
                }
                basin_rain = calculate_basin_rainfall(day_points, weights)
                basin_rainfall.append(basin_rain)

            thresholds = FLOOD_THRESHOLDS.get(basin, FLOOD_THRESHOLDS["CENTRAL"])
            analysis = analyze_basin_forecast(basin, basin_rainfall, dates_ref, thresholds)
            all_analysis[basin] = analysis

        result = {
            "basins": all_analysis,
            "generated_at": datetime.now().isoformat(),
            "stations_loaded": len(station_data),
            "stations_failed": failed_stations
        }

        # Update cache
        self._cache = result
        self._cache_time = datetime.now()

        print(f"✓ Fetched data for {len(all_analysis)} basins")
        return result

    def get_basin_forecast(self, basin_name: str) -> Dict[str, Any]:
        """
        Get forecast for a specific basin

        Args:
            basin_name: Basin code (HONG, CENTRAL, MEKONG, DONGNAI)

        Returns:
            Basin forecast data
        """
        basin_upper = basin_name.upper()
        all_data = self.get_all_forecasts()

        if basin_upper not in all_data["basins"]:
            raise ValueError(f"Basin not found: {basin_name}")

        return {
            "basin": basin_upper,
            "data": all_data["basins"][basin_upper],
            "generated_at": all_data["generated_at"]
        }

    def get_basins_summary(self) -> List[Dict[str, Any]]:
        """
        Get summary of all basins

        Returns:
            List of basin summaries with risk counts
        """
        all_data = self.get_all_forecasts()
        basins = all_data["basins"]

        summary = []
        basin_names = {
            "HONG": "Sông Hồng",
            "MEKONG": "Sông Mekong",
            "DONGNAI": "Sông Đồng Nai",
            "CENTRAL": "Miền Trung"
        }

        for basin_code, basin_data in basins.items():
            danger_count = 0
            warning_count = 0
            watch_count = 0
            safe_count = 0

            for day in basin_data.get("forecast_days", []):
                risk = day.get("risk_level", "").upper()
                if "NGUY" in risk or "DANGER" in risk:
                    danger_count += 1
                elif "CẢNH" in risk or "WARNING" in risk:
                    warning_count += 1
                elif "THEO" in risk or "WATCH" in risk:
                    watch_count += 1
                else:
                    safe_count += 1

            summary.append({
                "basin_id": hash(basin_code) % 1000,
                "basin_name": basin_names.get(basin_code, basin_code),
                "total_stations": len(basin_data.get("forecast_days", [])) + 10,
                "danger_count": danger_count,
                "warning_count": warning_count,
                "watch_count": watch_count,
                "safe_count": safe_count
            })

        return summary

    def invalidate_cache(self):
        """Force cache refresh on next request"""
        self._cache = None
        self._cache_time = None
