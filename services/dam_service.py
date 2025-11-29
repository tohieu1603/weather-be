#!/usr/bin/env python3
"""
Dam Service - Business logic for dam and dam alerts
"""
from datetime import date, datetime
from typing import Dict, List, Any, Optional
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from repositories.dam_repository import DamRepository
from repositories.evn_reservoir_repository import EVNReservoirRepository
from repositories.combined_alerts_cache_repository import CombinedAlertsCacheRepository
from data.constants import VIETNAM_DAMS, VIETNAM_RIVERS
from weather_api import fetch_forecast_full, fetch_flood_forecast


class DamService:
    """Service for dam operations"""

    def __init__(self):
        self.repo = DamRepository()
        self.evn_repo = EVNReservoirRepository()
        self.alerts_cache_repo = CombinedAlertsCacheRepository()

    def get_all_dams(self) -> Dict[str, Any]:
        """Get all dams - format matching main_simple.py"""
        all_dams = []
        for basin, dams in VIETNAM_DAMS.items():
            for dam in dams:
                dam_info = dam.copy()
                dam_info["basin"] = basin
                all_dams.append(dam_info)

        return {
            "total": len(all_dams),
            "dams": all_dams,
            "basins": list(VIETNAM_DAMS.keys())
        }

    def get_dams_by_basin(self, basin: str) -> Optional[Dict[str, Any]]:
        """Get dams in a specific basin - format matching main_simple.py"""
        basin_upper = basin.upper()
        if basin_upper not in VIETNAM_DAMS:
            return None

        return {
            "basin": basin_upper,
            "total": len(VIETNAM_DAMS[basin_upper]),
            "dams": VIETNAM_DAMS[basin_upper]
        }

    def _get_dam_real_weather_data(self, dam: dict) -> dict:
        """Get real weather data from Open-Meteo for dam location"""
        lat = dam["coordinates"]["lat"]
        lon = dam["coordinates"]["lon"]

        forecast = fetch_forecast_full(lat, lon, days=7)
        flood = fetch_flood_forecast(lat, lon)

        return {
            "forecast": forecast,
            "flood": flood,
            "source": "Open-Meteo API + GloFAS (Real Data)"
        }

    def _get_discharge_recommendations(self, level: str, dam: dict, discharge: float) -> list:
        """Generate recommendations based on discharge level"""
        if level == "emergency":
            return [
                f"KHẨN CẤP: Sơ tán người dân trong vòng {dam['warning_time_hours']} giờ tại các vùng trũng hạ du",
                f"Không được đi lại, đánh bắt cá trên sông {dam['river']} và các nhánh",
                "Di chuyển gia súc, tài sản lên vùng cao",
                "Liên hệ ngay chính quyền địa phương để được hỗ trợ sơ tán",
                f"Lưu lượng xả dự kiến: {discharge:,.0f} m³/s - Rất nguy hiểm",
                "Tuyệt đối không băng qua các tràn, đập, cầu ngập nước"
            ]
        elif level == "warning":
            return [
                f"Cảnh báo xả lũ: Chuẩn bị sẵn sàng sơ tán trong vòng {dam['warning_time_hours']} giờ",
                f"Theo dõi mực nước sông {dam['river']} liên tục",
                "Chuẩn bị đồ dùng thiết yếu, đèn pin, nước uống, thực phẩm",
                "Cập nhật thông tin từ chính quyền địa phương và đài truyền thanh",
                "Kiểm tra phương tiện, sẵn sàng di chuyển khi có lệnh sơ tán"
            ]
        else:  # watch
            return [
                f"Theo dõi diễn biến mưa lũ trên sông {dam['river']}",
                "Thường xuyên cập nhật dự báo thời tiết",
                "Kiểm tra hệ thống thoát nước quanh nhà",
                "Lưu số điện thoại khẩn cấp của địa phương"
            ]

    def _generate_dam_alerts_with_real_data(self) -> List[Dict[str, Any]]:
        """Generate dam alerts from real Open-Meteo + GloFAS data"""
        alerts = []

        for basin_name, dams in VIETNAM_DAMS.items():
            rivers = VIETNAM_RIVERS.get(basin_name, [])

            for dam in dams:
                try:
                    real_data = self._get_dam_real_weather_data(dam)
                    forecast = real_data.get("forecast", {})
                    flood = real_data.get("flood", {})

                    if not forecast:
                        continue

                    daily = forecast.get("daily", {})
                    dates = daily.get("time", [])
                    precipitation = daily.get("precipitation_sum", [])
                    rain = daily.get("rain_sum", [])

                    flood_daily = flood.get("daily", {}) if flood else {}
                    river_discharge = flood_daily.get("river_discharge", [])

                    for i, date_str in enumerate(dates[:7]):
                        daily_rain = precipitation[i] if i < len(precipitation) and precipitation[i] else 0
                        discharge_glofas = river_discharge[i] if i < len(river_discharge) and river_discharge[i] else 0

                        accumulated = sum([
                            precipitation[j] if j < len(precipitation) and precipitation[j] else 0
                            for j in range(max(0, i-2), i+1)
                        ])

                        needs_discharge = False
                        discharge_level = "normal"

                        if daily_rain > 100 or accumulated > 200 or discharge_glofas > dam["max_discharge_m3s"] * 0.5:
                            needs_discharge = True
                            discharge_level = "emergency"
                        elif daily_rain > 50 or accumulated > 100 or discharge_glofas > dam["max_discharge_m3s"] * 0.3:
                            needs_discharge = True
                            discharge_level = "warning"
                        elif daily_rain > 30 or accumulated > 60 or discharge_glofas > dam["max_discharge_m3s"] * 0.15:
                            needs_discharge = True
                            discharge_level = "watch"

                        if not needs_discharge:
                            continue

                        # Calculate estimated discharge
                        runoff_coefficient = 0.5
                        catchment_area_km2 = dam["reservoir_volume_million_m3"] * 10
                        inflow_from_rain = (daily_rain * catchment_area_km2 * runoff_coefficient * 1000) / 86400

                        if discharge_level == "emergency":
                            discharge_ratio = min(0.95, 0.6 + (daily_rain / 200) * 0.35)
                            estimated_discharge = max(
                                discharge_glofas * 1.1 if discharge_glofas > 0 else 0,
                                min(dam["max_discharge_m3s"] * discharge_ratio,
                                    inflow_from_rain * 1.2 + dam["max_discharge_m3s"] * 0.3)
                            )
                        elif discharge_level == "warning":
                            discharge_ratio = min(0.6, 0.3 + (daily_rain / 150) * 0.3)
                            estimated_discharge = max(
                                discharge_glofas * 0.9 if discharge_glofas > 0 else 0,
                                min(dam["max_discharge_m3s"] * discharge_ratio,
                                    inflow_from_rain * 1.1 + dam["max_discharge_m3s"] * 0.15)
                            )
                        else:
                            discharge_ratio = min(0.3, 0.1 + (daily_rain / 100) * 0.2)
                            estimated_discharge = max(
                                discharge_glofas * 0.7 if discharge_glofas > 0 else 0,
                                min(dam["max_discharge_m3s"] * discharge_ratio,
                                    inflow_from_rain + dam["max_discharge_m3s"] * 0.05)
                            )

                        water_level = dam["normal_level_m"] + (daily_rain / 100) * (dam["flood_level_m"] - dam["normal_level_m"])
                        water_level = min(water_level, dam["flood_level_m"] + 1)

                        gates_open = min(dam["spillway_gates"], max(1, int(estimated_discharge / dam["max_discharge_m3s"] * dam["spillway_gates"])))

                        time_base = {"emergency": 6, "warning": 8, "watch": 10}.get(discharge_level, 8)
                        time_offset = int((daily_rain % 50) / 10)
                        discharge_hour = time_base + time_offset

                        severity_map = {"emergency": "critical", "warning": "high", "watch": "medium"}

                        alert = {
                            "id": f"{dam['id']}_{date_str}_real",
                            "type": "dam_discharge",
                            "category": "Xả lũ",
                            "title": f"Cảnh báo xả lũ - {dam['name']}",
                            "severity": severity_map.get(discharge_level, "low"),
                            "date": date_str,
                            "region": dam["province"],
                            "provinces": dam["downstream_areas"],
                            "description": f"Dự kiến xả lũ {estimated_discharge:,.0f} m³/s ({estimated_discharge / dam['max_discharge_m3s'] * 100:.0f}% công suất) qua {gates_open} cửa xả. "
                                          f"Mực nước hồ ước tính: {water_level:.1f}m/{dam['flood_level_m']}m. "
                                          f"Lượng mưa thượng nguồn: {daily_rain:.1f}mm. "
                                          f"Thời gian ảnh hưởng đến hạ du: {dam['warning_time_hours']} giờ.",
                            "data": {
                                "dam_name": dam["name"],
                                "river": dam["river"],
                                "discharge_m3s": round(estimated_discharge, 0),
                                "discharge_percent": round(estimated_discharge / dam["max_discharge_m3s"] * 100, 1),
                                "water_level_m": round(water_level, 2),
                                "water_level_percent": round((water_level - dam["dead_level_m"]) / (dam["flood_level_m"] - dam["dead_level_m"]) * 100, 1),
                                "spillway_gates_open": gates_open,
                                "total_gates": dam["spillway_gates"],
                                "warning_time_hours": dam["warning_time_hours"],
                                "estimated_time": f"{discharge_hour}:00",
                                "rainfall_mm": round(daily_rain, 1),
                                "rainfall_accumulated_mm": round(accumulated, 1),
                                "river_discharge_glofas_m3s": round(discharge_glofas, 0) if discharge_glofas else None,
                            },
                            "recommendations": self._get_discharge_recommendations(discharge_level, dam, estimated_discharge),
                            "source": "Open-Meteo + GloFAS (Rainfall: Real, Discharge: Estimated)",
                            "data_note": "Lượng mưa từ Open-Meteo (thật). Lưu lượng sông từ GloFAS (thật). Mực nước hồ và lưu lượng xả là ước tính."
                        }

                        # Add flood zones
                        flood_zones = []
                        for river in rivers:
                            if river["name"] in dam.get("affected_rivers", []) or dam["river"] in river["name"]:
                                for zone in river.get("flood_prone_areas", []):
                                    flood_zones.append({
                                        "province": zone["name"],
                                        "districts": zone["districts"],
                                        "risk": zone["risk"],
                                    })
                        alert["flood_zones"] = flood_zones
                        alerts.append(alert)

                except Exception as e:
                    print(f"Error generating alert for {dam.get('name', 'unknown')}: {e}")
                    continue

        return alerts

    def get_realtime_dam_alerts(self) -> Dict[str, Any]:
        """
        Get realtime dam alerts - format matching main_simple.py

        Logic đơn giản:
        1. Kiểm tra DB có data ngày hôm nay không
        2. Nếu CÓ -> trả về từ DB
        3. Nếu KHÔNG CÓ -> fetch mới và lưu DB
        """
        today = date.today()

        # Bước 1: Kiểm tra DB có data ngày hôm nay không
        cached = self.alerts_cache_repo.get_cached_alerts("dam", today)
        if cached:
            # Thêm by_category nếu chưa có
            if "by_category" not in cached or cached.get("by_category") is None:
                cached["by_category"] = {"Xả lũ": len(cached.get("alerts", []))}
            return cached

        # Bước 2: Không có data ngày hôm nay -> fetch mới
        print(f"Không có dữ liệu dam alerts cho ngày {today}, đang fetch mới...")
        alerts = self._generate_dam_alerts_with_real_data()

        summary = {
            "critical": len([a for a in alerts if a["severity"] == "critical"]),
            "high": len([a for a in alerts if a["severity"] == "high"]),
            "medium": len([a for a in alerts if a["severity"] == "medium"]),
            "low": len([a for a in alerts if a["severity"] == "low"])
        }

        result = {
            "generated_at": datetime.now().isoformat(),
            "total": len(alerts),
            "alerts": alerts,
            "summary": summary,
            "by_category": {"Xả lũ": len(alerts)},
            "source": "Open-Meteo + GloFAS",
            "cache_date": str(today),
            "data_note": "Lượng mưa và lưu lượng sông từ API thực. Mực nước hồ và lưu lượng xả là ước tính do không có API công khai từ EVN."
        }

        # Bước 3: Lưu vào DB
        self.alerts_cache_repo.save_alerts("dam", alerts, summary, today)

        return result

    def get_dam_alerts(self, basin: str = None) -> Dict[str, Any]:
        """Get dam alerts, optionally filtered by basin"""
        result = self.get_realtime_dam_alerts()

        if basin:
            basin_upper = basin.upper()
            result = result.copy()
            result["alerts"] = [a for a in result["alerts"] if any(
                dam["province"] in a.get("region", "") or basin_upper in str(a)
                for dam in VIETNAM_DAMS.get(basin_upper, [])
            )]
            result["total"] = len(result["alerts"])

        return result

    def save_dam_alert(self, dam_code: str, alert_data: Dict[str, Any]) -> bool:
        """Save a dam alert"""
        return self.repo.save_dam_alert(dam_code, alert_data)

    def invalidate_cache(self):
        """Force cache refresh on next request"""
        self.alerts_cache_repo.invalidate_key("dam")
        print("✓ Invalidated dam alerts cache (DB)")

    def _get_evn_reservoir_data(self, dam_name: str) -> Optional[Dict[str, Any]]:
        """
        Get real EVN reservoir data for a dam if available

        Args:
            dam_name: Name of the dam

        Returns:
            EVN data dict or None if not found
        """
        # Mapping từ tên đập trong VIETNAM_DAMS sang tên EVN
        name_mapping = {
            "Hòa Bình": "Hòa Bình",
            "Sơn La": "Sơn La",
            "Lai Châu": "Lai Châu",
            "Tuyên Quang": "Tuyên Quang",
            "Thác Bà": "Thác Bà",
            "Trị An": "Trị An",
            "Ialy": "Ialy",
            "Sông Tranh 2": "Sông Tranh 2",
            "A Vương": "A Vương",
            "Đại Ninh": "Đại Ninh",
            "Đồng Nai 3": "Đồng Nai 3",
            "Đồng Nai 4": "Đồng Nai 4",
        }

        evn_name = name_mapping.get(dam_name, dam_name)
        return self.evn_repo.get_by_name(evn_name)

    def get_evn_alerts(self) -> List[Dict[str, Any]]:
        """
        Get alerts from real EVN reservoir data

        Returns:
            List of alerts based on EVN data
        """
        alerts = []

        # Get reservoirs with spillway open or high water
        high_discharge = self.evn_repo.get_high_discharge(70)
        spillway_open = self.evn_repo.get_spillway_open()

        # Combine both lists, avoid duplicates
        seen_names = set()
        all_alerts = []
        for r in spillway_open + high_discharge:
            if r["name"] not in seen_names:
                seen_names.add(r["name"])
                all_alerts.append(r)

        for r in all_alerts:
            # Determine severity
            has_spillway = (r.get("ncxs") or 0) > 0 or (r.get("ncxm") or 0) > 0
            water_percent = 0
            if r.get("hdbt") and r.get("htl"):
                water_percent = (r["htl"] / r["hdbt"]) * 100
            high_water = water_percent >= 90
            high_discharge_val = (r.get("total_qx") or 0) > 500

            if has_spillway and high_water:
                severity = "critical"
            elif has_spillway:
                severity = "high"
            else:
                severity = "medium"

            # Build alert reason
            reasons = []
            if has_spillway:
                gates = []
                if r.get("ncxs"):
                    gates.append(f"{r['ncxs']} cửa xả sâu")
                if r.get("ncxm"):
                    gates.append(f"{r['ncxm']} cửa xả mặt")
                reasons.append(f"Đang mở {', '.join(gates)}")
            if high_water:
                reasons.append(f"Mực nước cao ({water_percent:.1f}%)")
            if high_discharge_val:
                reasons.append(f"Lưu lượng xả lớn ({r.get('total_qx', 0):.0f} m³/s)")

            alert = {
                "id": f"evn_{r['name']}_{datetime.now().strftime('%Y%m%d')}",
                "type": "dam_discharge",
                "category": "Xả lũ (EVN)",
                "title": f"Cảnh báo xả lũ - {r['name']}",
                "severity": severity,
                "date": datetime.now().strftime("%Y-%m-%d"),
                "region": r["name"],
                "description": ". ".join(reasons),
                "data": {
                    "dam_name": r["name"],
                    "water_level_m": r.get("htl"),
                    "normal_level_m": r.get("hdbt"),
                    "dead_level_m": r.get("hc"),
                    "water_level_percent": round(water_percent, 1) if water_percent else None,
                    "inflow_m3s": r.get("qve"),
                    "total_discharge_m3s": r.get("total_qx"),
                    "turbine_discharge_m3s": r.get("qxt"),
                    "spillway_discharge_m3s": r.get("qxm"),
                    "deep_gates_open": r.get("ncxs"),
                    "surface_gates_open": r.get("ncxm"),
                },
                "recommendations": self._get_evn_recommendations(severity, r),
                "source": "EVN Database (Dữ liệu thực)",
                "fetched_at": r.get("fetched_at").isoformat() if r.get("fetched_at") else None
            }
            alerts.append(alert)

        return alerts

    def _get_evn_recommendations(self, severity: str, r: Dict) -> List[str]:
        """Generate recommendations based on EVN data"""
        if severity == "critical":
            return [
                f"KHẨN CẤP: Hồ {r['name']} đang xả lũ với lưu lượng lớn",
                "Người dân vùng hạ du cần sơ tán ngay lập tức",
                "Không được đi lại, đánh bắt cá trên sông",
                "Di chuyển gia súc, tài sản lên vùng cao",
                "Liên hệ chính quyền địa phương để được hỗ trợ"
            ]
        elif severity == "high":
            return [
                f"Hồ {r['name']} đang xả lũ - chuẩn bị sẵn sàng sơ tán",
                "Theo dõi mực nước sông liên tục",
                "Chuẩn bị đồ dùng thiết yếu",
                "Cập nhật thông tin từ chính quyền địa phương"
            ]
        else:
            return [
                f"Theo dõi tình hình hồ {r['name']}",
                "Cập nhật thông tin thời tiết thường xuyên",
                "Kiểm tra hệ thống thoát nước quanh nhà"
            ]

    def get_combined_dam_alerts(self) -> Dict[str, Any]:
        """
        Get combined alerts from both Open-Meteo forecast and real EVN data

        Logic đơn giản:
        1. Kiểm tra DB có data ngày hôm nay không
        2. Nếu CÓ -> trả về từ DB
        3. Nếu KHÔNG CÓ -> fetch mới và lưu DB
        """
        today = date.today()

        # Bước 1: Kiểm tra DB có data ngày hôm nay không
        cached = self.alerts_cache_repo.get_cached_alerts("dam_combined", today)
        if cached:
            return cached

        # Bước 2: Không có data ngày hôm nay -> fetch mới
        print(f"Không có dữ liệu combined dam alerts cho ngày {today}, đang fetch mới...")

        # Get forecast-based alerts
        forecast_alerts = self._generate_dam_alerts_with_real_data()

        # Get real EVN alerts
        evn_alerts = self.get_evn_alerts()

        # Combine and deduplicate
        all_alerts = forecast_alerts + evn_alerts

        summary = {
            "critical": len([a for a in all_alerts if a["severity"] == "critical"]),
            "high": len([a for a in all_alerts if a["severity"] == "high"]),
            "medium": len([a for a in all_alerts if a["severity"] == "medium"]),
            "low": len([a for a in all_alerts if a["severity"] == "low"])
        }

        result = {
            "generated_at": datetime.now().isoformat(),
            "total": len(all_alerts),
            "alerts": all_alerts,
            "summary": summary,
            "by_source": {
                "forecast": len(forecast_alerts),
                "evn_realtime": len(evn_alerts)
            },
            "source": "Open-Meteo + EVN Database",
            "cache_date": str(today),
            "data_note": "Dữ liệu EVN là thực từ website EVN. Dữ liệu dự báo từ Open-Meteo + GloFAS."
        }

        # Bước 3: Lưu vào DB
        self.alerts_cache_repo.save_alerts("dam_combined", all_alerts, summary, today)

        return result
