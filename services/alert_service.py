#!/usr/bin/env python3
"""
Alert Service - Business logic for weather and flood alerts

Features:
- Background loading with job system (non-blocking)
- DB cache with 1-day expiry
- Global semaphore to prevent server overload when multiple heavy tasks run
"""
from datetime import date, datetime
from typing import Dict, List, Any, Optional, Tuple
import hashlib
import threading
import uuid
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from repositories.alert_repository import AlertRepository
from repositories.combined_alerts_cache_repository import CombinedAlertsCacheRepository
from weather_api import (
    get_all_vietnam_weather,
    analyze_weather_for_alerts
)
from services.request_manager import acquire_heavy_task, release_heavy_task
from services.evn_reservoir_service import EVNReservoirService


class AlertService:
    """Service for alert operations with async support"""

    CACHE_TTL = 86400  # 24 hours

    # Class-level job tracking (shared across instances)
    _alert_jobs: Dict[str, dict] = {}
    _jobs_lock = threading.Lock()

    def __init__(self):
        self.repo = AlertRepository()
        self.alerts_cache_repo = CombinedAlertsCacheRepository()
        self.evn_service = EVNReservoirService()
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

    def _get_evn_discharge_alerts(self) -> List[Dict[str, Any]]:
        """
        Lấy cảnh báo xả lũ từ dữ liệu hồ chứa EVN
        """
        try:
            discharge_alerts = self.evn_service.get_discharge_alerts()
            formatted_alerts = []

            for r in discharge_alerts:
                today = date.today().isoformat()
                reservoir_name = r.get("name", "Unknown")
                severity = r.get("severity", "medium")
                basin = r.get("basin", "UNKNOWN")

                # Map basin to region name
                basin_names = {
                    "HONG": "Bắc Bộ",
                    "CENTRAL": "Trung Bộ",
                    "MEKONG": "Tây Nguyên",
                    "DONGNAI": "Đông Nam Bộ",
                    "UNKNOWN": "Việt Nam"
                }
                region_name = basin_names.get(basin, "Việt Nam")

                # Xác định mức độ nguy hiểm
                has_spillway = (r.get("ncxs") or 0) > 0 or (r.get("ncxm") or 0) > 0
                water_percent = r.get("water_percent", 0)
                total_discharge = r.get("total_qx", 0)

                if has_spillway and water_percent >= 95:
                    danger_level = "Rất nguy hiểm"
                elif has_spillway:
                    danger_level = "Nguy hiểm"
                elif water_percent >= 90:
                    danger_level = "Cần theo dõi"
                else:
                    danger_level = "Bình thường"

                description = f"Hồ chứa {reservoir_name} đang xả lũ. "
                if has_spillway:
                    gates = []
                    if r.get("ncxs"):
                        gates.append(f"{r['ncxs']} cửa xả sâu")
                    if r.get("ncxm"):
                        gates.append(f"{r['ncxm']} cửa xả mặt")
                    description += f"Đang mở {', '.join(gates)}. "
                description += f"Mực nước hiện tại {r.get('htl', 0):.1f}m ({water_percent:.1f}% so với mực nước dâng bình thường)."

                formatted_alerts.append({
                    "id": f"evn_discharge_{reservoir_name.replace(' ', '_')}_{today}",
                    "type": "reservoir_discharge",
                    "category": "Xả lũ hồ chứa",
                    "title": f"Cảnh báo xả lũ - Hồ {reservoir_name}",
                    "severity": severity,
                    "date": today,
                    "region": region_name,
                    "provinces": [region_name],
                    "description": description,
                    "data": {
                        "reservoir_name": reservoir_name,
                        "basin": basin,
                        "water_level_m": r.get("htl"),
                        "normal_level_m": r.get("hdbt"),
                        "dead_level_m": r.get("hc"),
                        "water_percent": water_percent,
                        "inflow_m3s": r.get("qve"),
                        "total_discharge_m3s": r.get("total_qx"),
                        "turbine_discharge_m3s": r.get("qxt"),
                        "spillway_discharge_m3s": r.get("qxm"),
                        "spillway_gates_deep": r.get("ncxs"),
                        "spillway_gates_surface": r.get("ncxm"),
                        "danger_level": danger_level,
                        "alert_reason": r.get("alert_reason"),
                    },
                    "recommendations": [
                        "Theo dõi thông báo từ Ban chỉ huy PCTT địa phương",
                        "Người dân vùng hạ du cần cảnh giác" if has_spillway else "Theo dõi diễn biến mực nước",
                        "Không đánh bắt cá, vớt củi trên sông",
                        "Sẵn sàng sơ tán nếu có thông báo" if severity == "critical" else "Di chuyển tài sản, vật nuôi lên cao",
                        "Tránh xa bờ sông, suối khi có xả lũ"
                    ],
                    "source": "EVN - Hệ thống thủy điện"
                })

            return formatted_alerts

        except Exception as e:
            print(f"[AlertService] Error getting EVN discharge alerts: {e}")
            return []

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

        # Add EVN reservoir discharge alerts
        evn_alerts = self._get_evn_discharge_alerts()
        if evn_alerts:
            print(f"✓ Thêm {len(evn_alerts)} cảnh báo xả lũ từ EVN")
            alerts = alerts + evn_alerts

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
            "data_source": "Open-Meteo API + EVN",
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

    # ==================== ASYNC (NON-BLOCKING) MODE ====================

    def get_realtime_alerts_async(self) -> Tuple[str, Optional[Dict[str, Any]]]:
        """
        Get realtime alerts with async support (non-blocking).

        Returns:
            Tuple of (job_id, cached_result_or_none)
            - If cached: ("cached", alerts_data)
            - If processing: (job_id, None)
        """
        print(f"\n{'='*50}")
        print(f"[Alerts Async] get_realtime_alerts_async() called")

        # Step 1: Check DB cache
        cached = self.alerts_cache_repo.get_cached_alerts("weather", date.today())
        if cached:
            print(f"[Alerts Async] CACHE HIT! Returning from DB immediately")
            # Add by_category if missing
            if "by_category" not in cached or cached.get("by_category") is None:
                by_cat = {}
                for alert in cached.get("alerts", []):
                    cat = alert.get("category", "Khác")
                    by_cat[cat] = by_cat.get(cat, 0) + 1
                cached["by_category"] = by_cat
            return ("cached", cached)

        # Step 2: Check for existing pending/processing job
        with self._jobs_lock:
            for job_id, job in self._alert_jobs.items():
                if job["type"] == "weather" and job["status"] in ["pending", "processing"]:
                    print(f"[Alerts Async] Found existing job: {job_id}")
                    return (job_id, None)

            # Step 3: Create new job
            job_id = f"alert_{uuid.uuid4().hex[:8]}"
            self._alert_jobs[job_id] = {
                "type": "weather",
                "status": "pending",
                "progress": 0,
                "result": None,
                "error": None,
                "created_at": datetime.now()
            }
            print(f"[Alerts Async] Created new job: {job_id}")

        # Step 4: Start background thread
        thread = threading.Thread(
            target=self._run_alerts_job,
            args=(job_id,),
            daemon=True
        )
        thread.start()

        print(f"[Alerts Async] Started background thread for {job_id}")
        print(f"{'='*50}\n")

        return (job_id, None)

    def _run_alerts_job(self, job_id: str):
        """Run alerts fetching in background thread with global semaphore"""
        task_name = f"Alerts_{job_id}"
        semaphore_acquired = False

        try:
            with self._jobs_lock:
                if job_id not in self._alert_jobs:
                    return
                self._alert_jobs[job_id]["status"] = "processing"
                self._alert_jobs[job_id]["progress"] = 10

            print(f"[Alerts Job {job_id}] Starting...")

            # Check cache again (in case another thread completed)
            cached = self.alerts_cache_repo.get_cached_alerts("weather", date.today())
            if cached:
                print(f"[Alerts Job {job_id}] Cache found, skipping fetch")
                with self._jobs_lock:
                    self._alert_jobs[job_id]["status"] = "completed"
                    self._alert_jobs[job_id]["progress"] = 100
                    self._alert_jobs[job_id]["result"] = cached
                return

            # Acquire global semaphore before heavy API calls
            semaphore_acquired = acquire_heavy_task(task_name, timeout=180.0)
            if not semaphore_acquired:
                print(f"[Alerts Job {job_id}] Could not acquire semaphore, failing")
                with self._jobs_lock:
                    self._alert_jobs[job_id]["status"] = "failed"
                    self._alert_jobs[job_id]["error"] = "Server busy, please try again"
                return

            with self._jobs_lock:
                self._alert_jobs[job_id]["progress"] = 30

            # Fetch weather data (this is the heavy call)
            print(f"[Alerts Job {job_id}] Fetching weather data...")
            weather_data, alerts = self._get_cached_weather_and_alerts()

            with self._jobs_lock:
                self._alert_jobs[job_id]["progress"] = 60

            # Add EVN reservoir discharge alerts
            print(f"[Alerts Job {job_id}] Fetching EVN discharge alerts...")
            evn_alerts = self._get_evn_discharge_alerts()
            if evn_alerts:
                print(f"[Alerts Job {job_id}] Added {len(evn_alerts)} EVN alerts")
                alerts = alerts + evn_alerts

            with self._jobs_lock:
                self._alert_jobs[job_id]["progress"] = 80

            # Process alerts
            severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
            alerts.sort(key=lambda x: (severity_order.get(x.get("severity", "low"), 4), x.get("date", "")))

            summary = {
                "critical": len([a for a in alerts if a.get("severity") == "critical"]),
                "high": len([a for a in alerts if a.get("severity") == "high"]),
                "medium": len([a for a in alerts if a.get("severity") == "medium"]),
                "low": len([a for a in alerts if a.get("severity") == "low"])
            }

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
                "data_source": "Open-Meteo API + EVN",
                "cache_duration_seconds": self.CACHE_TTL
            }

            # Save to DB cache
            self.alerts_cache_repo.save_alerts("weather", alerts, summary, date.today())

            with self._jobs_lock:
                self._alert_jobs[job_id]["status"] = "completed"
                self._alert_jobs[job_id]["progress"] = 100
                self._alert_jobs[job_id]["result"] = result

            print(f"[Alerts Job {job_id}] Completed successfully!")

        except Exception as e:
            print(f"[Alerts Job {job_id}] Failed: {e}")
            with self._jobs_lock:
                self._alert_jobs[job_id]["status"] = "failed"
                self._alert_jobs[job_id]["error"] = str(e)

        finally:
            if semaphore_acquired:
                release_heavy_task(task_name)

    def get_alert_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get status of an alerts job.

        Args:
            job_id: Job identifier

        Returns:
            Dict with job status, progress, and result (if completed)
        """
        if job_id == "cached":
            return {"status": "completed", "progress": 100, "from_cache": True}

        with self._jobs_lock:
            job = self._alert_jobs.get(job_id)
            if not job:
                return None

            response = {
                "job_id": job_id,
                "type": job["type"],
                "status": job["status"],
                "progress": job["progress"],
                "created_at": job["created_at"].isoformat()
            }

            if job["status"] == "completed" and job.get("result"):
                response["result"] = job["result"]

            if job["status"] == "failed":
                response["error"] = job.get("error")

            return response

    def cleanup_old_jobs(self, max_age_seconds: int = 3600):
        """Remove old completed/failed jobs"""
        now = datetime.now()
        to_remove = []

        with self._jobs_lock:
            for job_id, job in self._alert_jobs.items():
                if job["status"] in ["completed", "failed"]:
                    age = (now - job["created_at"]).total_seconds()
                    if age > max_age_seconds:
                        to_remove.append(job_id)

            for job_id in to_remove:
                del self._alert_jobs[job_id]

        if to_remove:
            print(f"[AlertService] Cleaned up {len(to_remove)} old jobs")
