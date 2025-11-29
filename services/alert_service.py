#!/usr/bin/env python3
"""
Alert Service - Business logic for weather and flood alerts
"""
from datetime import date, datetime
from typing import Dict, List, Any, Optional
import hashlib
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from repositories.alert_repository import AlertRepository
from repositories.combined_alerts_cache_repository import CombinedAlertsCacheRepository
from weather_api import (
    get_all_vietnam_weather,
    analyze_weather_for_alerts
)


class AlertService:
    """Service for alert operations"""

    CACHE_TTL = 86400  # 24 hours

    def __init__(self):
        self.repo = AlertRepository()
        self.alerts_cache_repo = CombinedAlertsCacheRepository()
        self._weather_cache = None
        self._alerts_cache = None
        self._cache_time = None

    def _is_cache_valid(self) -> bool:
        """Check if cache is valid"""
        if self._weather_cache is None or self._cache_time is None:
            return False
        elapsed = (datetime.now() - self._cache_time).total_seconds()
        return elapsed < self.CACHE_TTL

    def _get_cached_weather_and_alerts(self):
        """Get weather data and alerts with caching"""
        if self._is_cache_valid():
            return self._weather_cache, self._alerts_cache

        print("Fetching real weather data from Open-Meteo...")
        key_locations = [
            "hanoi", "ho_chi_minh", "da_nang", "hai_phong", "can_tho",
            "thua_thien_hue", "khanh_hoa", "quang_ninh", "thanh_hoa", "nghe_an",
            "quang_nam", "binh_dinh", "dak_lak", "lam_dong", "an_giang"
        ]

        weather_data = get_all_vietnam_weather(
            locations=key_locations,
            include_flood=True,
            include_air_quality=False,
            include_marine=False
        )

        alerts = analyze_weather_for_alerts(weather_data)

        self._weather_cache = weather_data
        self._alerts_cache = alerts
        self._cache_time = datetime.now()

        return weather_data, alerts

    def get_realtime_alerts(self) -> Dict[str, Any]:
        """
        Get realtime alerts (today) - format matching main_simple.py

        Returns:
            Dict with alerts, summary, and metadata
        """
        # Check DB cache first (1 day expiry)
        cached = self.alerts_cache_repo.get_cached_alerts("weather", date.today())
        if cached:
            print("✓ Using DB cached weather alerts")
            # Thêm by_category nếu chưa có
            if "by_category" not in cached or cached.get("by_category") is None:
                by_cat = {}
                for alert in cached.get("alerts", []):
                    cat = alert.get("category", "Khác")
                    by_cat[cat] = by_cat.get(cat, 0) + 1
                cached["by_category"] = by_cat
            return cached

        weather_data, alerts = self._get_cached_weather_and_alerts()

        # Sort by severity
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        alerts.sort(key=lambda x: (severity_order.get(x.get("severity", "low"), 4), x.get("date", "")))

        # Calculate summary
        summary = {
            "critical": len([a for a in alerts if a.get("severity") == "critical"]),
            "high": len([a for a in alerts if a.get("severity") == "high"]),
            "medium": len([a for a in alerts if a.get("severity") == "medium"]),
            "low": len([a for a in alerts if a.get("severity") == "low"])
        }

        # Calculate by category
        by_category = {}
        for alert in alerts:
            cat = alert.get("category", "Khác")
            by_category[cat] = by_category.get(cat, 0) + 1

        result = {
            "generated_at": datetime.now().isoformat(),
            "total": len(alerts),
            "alerts": alerts,
            "summary": summary,
            "by_category": by_category,
            "data_source": "Open-Meteo API (Real Data)",
            "cache_duration_seconds": self.CACHE_TTL
        }

        # Save to DB cache
        self.alerts_cache_repo.save_alerts("weather", alerts, summary, date.today())

        return result

    def get_all_alerts(
        self,
        alert_date: date = None,
        severity: str = None
    ) -> Dict[str, Any]:
        """
        Get all alerts for a date

        Args:
            alert_date: Date to get alerts for
            severity: Optional severity filter

        Returns:
            Dict with alerts data
        """
        result = self.get_realtime_alerts()

        # Filter by severity if specified
        if severity:
            result["alerts"] = [a for a in result["alerts"] if a.get("severity") == severity]
            result["total"] = len(result["alerts"])

        return result

    def get_alerts_by_region(self, region: str) -> Dict[str, Any]:
        """Get alerts for a specific region"""
        result = self.get_realtime_alerts()
        result["alerts"] = [a for a in result["alerts"] if a.get("region") == region]
        result["total"] = len(result["alerts"])
        return result

    def _generate_alert_id(self, alert_data: Dict[str, Any]) -> str:
        """Generate unique ID for an alert"""
        key = f"{alert_data.get('type', '')}_{alert_data.get('region', '')}_{date.today()}"
        return hashlib.md5(key.encode()).hexdigest()[:12]

    def save_alert(self, alert_data: Dict[str, Any]) -> bool:
        """Save an alert"""
        if "alert_id" not in alert_data:
            alert_data["alert_id"] = self._generate_alert_id(alert_data)
        return self.repo.save_alert(alert_data)

    def get_combined_alerts(self) -> Dict[str, Any]:
        """
        Get all types of alerts combined

        Returns:
            Dict with weather_alerts and dam_alerts
        """
        # Check DB cache for combined alerts (1 day expiry)
        cached = self.alerts_cache_repo.get_cached_alerts("all", date.today())
        if cached:
            print("✓ Using DB cached combined alerts")
            return cached

        from .dam_service import DamService
        dam_service = DamService()

        weather_alerts = self.get_realtime_alerts()
        dam_alerts = dam_service.get_realtime_dam_alerts()

        # Combine all alerts
        all_alerts = weather_alerts.get("alerts", []) + dam_alerts.get("alerts", [])

        combined_summary = {
            "weather": weather_alerts.get("summary", {}),
            "dam": dam_alerts.get("summary", {}),
            "total_weather": weather_alerts.get("total", 0),
            "total_dam": dam_alerts.get("total", 0)
        }

        result = {
            "weather_alerts": weather_alerts,
            "dam_alerts": dam_alerts,
            "generated_at": datetime.now().isoformat(),
            "total": len(all_alerts),
            "alerts": all_alerts,
            "summary": combined_summary,
            "from_cache": False
        }

        # Save combined alerts to DB cache
        self.alerts_cache_repo.save_alerts("all", all_alerts, combined_summary, date.today())

        return result

    def cleanup_old_alerts(self, days: int = 7) -> int:
        """Delete alerts older than specified days"""
        return self.repo.delete_old_alerts(days)

    def invalidate_cache(self):
        """Force cache refresh on next request"""
        self._weather_cache = None
        self._alerts_cache = None
        self._cache_time = None
        # Also invalidate DB cache
        self.alerts_cache_repo.invalidate_all()
        print("✓ Invalidated all alerts cache (memory + DB)")
