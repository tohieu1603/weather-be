#!/usr/bin/env python3
"""
EVN Reservoir Service - Fetch and process hydropower reservoir data from EVN
"""
import asyncio
import httpx
from datetime import datetime
from typing import Dict, List, Any, Optional
from bs4 import BeautifulSoup

from repositories.evn_reservoir_repository import EVNReservoirRepository


class EVNReservoirService:
    """Service for EVN reservoir data operations"""

    EVN_URL = "https://hochuathuydien.evn.com.vn/PageHoChuaThuyDienEmbedEVN.aspx"
    CACHE_TTL = 1800  # 30 minutes

    # Mapping tên hồ -> vùng lưu vực
    RESERVOIR_BASINS = {
        # Miền Bắc - HONG basin
        "Tuyên Quang": "HONG",
        "Lai Châu": "HONG",
        "Bản Chát": "HONG",
        "Sơn La": "HONG",
        "Hòa Bình": "HONG",
        "Thác Bà": "HONG",
        "Huội Quảng": "HONG",
        "Nậm Chiến": "HONG",
        # Miền Trung - CENTRAL basin
        "A Vương": "CENTRAL",
        "Sông Tranh 2": "CENTRAL",
        "Đắk Mi 4": "CENTRAL",
        "Sông Bung 4": "CENTRAL",
        "Bình Điền": "CENTRAL",
        "Hương Điền": "CENTRAL",
        "Rào Quán": "CENTRAL",
        "Sông Ba Hạ": "CENTRAL",
        "Krông H'năng": "CENTRAL",
        "Sê San 4": "CENTRAL",
        "Sê San 4A": "CENTRAL",
        "Ialy": "CENTRAL",
        "Plei Krông": "CENTRAL",
        "Kanak": "CENTRAL",
        "Đại Ninh": "CENTRAL",
        "Đồng Nai 3": "CENTRAL",
        "Đồng Nai 4": "CENTRAL",
        # Miền Nam - MEKONG/DONGNAI
        "Trị An": "DONGNAI",
        "Thác Mơ": "DONGNAI",
        "Cần Đơn": "DONGNAI",
        "Srok Phu Miêng": "DONGNAI",
        "Buôn Kuốp": "MEKONG",
        "Buôn Tua Srah": "MEKONG",
        "Srêpốk 3": "MEKONG",
        "Srêpốk 4": "MEKONG",
        "Đrây H'linh": "MEKONG",
    }

    def __init__(self):
        self.repo = EVNReservoirRepository()
        self._cache = None
        self._cache_time = None

    def _is_cache_valid(self) -> bool:
        """Check if cache is valid"""
        if self._cache is None or self._cache_time is None:
            return False
        elapsed = (datetime.now() - self._cache_time).total_seconds()
        return elapsed < self.CACHE_TTL

    async def fetch_from_evn(self) -> List[Dict[str, Any]]:
        """
        Fetch reservoir data from EVN website using httpx
        Note: This may not work perfectly as EVN uses JavaScript to load data
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    self.EVN_URL,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                    }
                )
                response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            reservoirs = []

            # Try to find table data
            tables = soup.find_all("table")
            for table in tables:
                rows = table.find_all("tr")
                for row in rows[2:]:  # Skip header rows
                    cells = row.find_all("td")
                    if len(cells) >= 10:
                        name = cells[0].get_text(strip=True)
                        if name and not name.lower().startswith(("tổng", "stt")):
                            reservoirs.append({
                                "name": name,
                                "htl": self._parse_float(cells[1].get_text(strip=True)),
                                "hdbt": self._parse_float(cells[2].get_text(strip=True)),
                                "hc": self._parse_float(cells[3].get_text(strip=True)),
                                "qve": self._parse_float(cells[4].get_text(strip=True)),
                                "total_qx": self._parse_float(cells[5].get_text(strip=True)),
                                "qxt": self._parse_float(cells[6].get_text(strip=True)),
                                "qxm": self._parse_float(cells[7].get_text(strip=True)),
                                "ncxs": self._parse_int(cells[8].get_text(strip=True)),
                                "ncxm": self._parse_int(cells[9].get_text(strip=True)),
                            })

            return reservoirs

        except Exception as e:
            print(f"Error fetching EVN data: {e}")
            return []

    def _parse_float(self, value: str) -> Optional[float]:
        """Parse float from string"""
        if not value or value == "-":
            return None
        try:
            return float(value.replace(",", "."))
        except ValueError:
            return None

    def _parse_int(self, value: str) -> Optional[int]:
        """Parse int from string"""
        if not value or value == "-":
            return None
        try:
            return int(value)
        except ValueError:
            return None

    def save_from_frontend(self, data: List[Dict[str, Any]]) -> int:
        """
        Save reservoir data received from frontend Puppeteer scraper

        Args:
            data: List of reservoir data from frontend /api/reservoir

        Returns:
            Number of saved records
        """
        count = self.repo.save_batch(data)
        # Invalidate cache
        self._cache = None
        self._cache_time = None
        return count

    def get_all_reservoirs(self) -> List[Dict[str, Any]]:
        """Get all latest reservoir data from database"""
        if self._is_cache_valid():
            return self._cache

        data = self.repo.get_latest()

        # Add basin info
        for item in data:
            item["basin"] = self.RESERVOIR_BASINS.get(item["name"], "UNKNOWN")
            # Calculate water level percent
            if item.get("hdbt") and item.get("htl"):
                item["water_percent"] = round(item["htl"] / item["hdbt"] * 100, 1)
            else:
                item["water_percent"] = None

        self._cache = data
        self._cache_time = datetime.now()
        return data

    def get_by_basin(self, basin: str) -> List[Dict[str, Any]]:
        """Get reservoirs for a specific basin"""
        all_data = self.get_all_reservoirs()
        return [r for r in all_data if r.get("basin") == basin.upper()]

    def get_discharge_alerts(self) -> List[Dict[str, Any]]:
        """
        Get reservoirs with active discharge that may cause flooding

        Returns:
            List of reservoirs with significant discharge
        """
        all_data = self.get_all_reservoirs()
        alerts = []

        for r in all_data:
            # Check if spillway gates are open
            has_spillway = (r.get("ncxs") or 0) > 0 or (r.get("ncxm") or 0) > 0
            # Check if water level is high (>90% of normal)
            high_water = (r.get("water_percent") or 0) >= 90
            # Check if there's significant discharge
            high_discharge = (r.get("total_qx") or 0) > 500

            if has_spillway or (high_water and high_discharge):
                severity = "critical" if has_spillway and high_water else "high" if has_spillway else "medium"
                alerts.append({
                    **r,
                    "severity": severity,
                    "alert_reason": self._get_alert_reason(r, has_spillway, high_water, high_discharge)
                })

        # Sort by severity
        severity_order = {"critical": 0, "high": 1, "medium": 2}
        alerts.sort(key=lambda x: severity_order.get(x["severity"], 3))

        return alerts

    def _get_alert_reason(self, r: Dict, has_spillway: bool, high_water: bool, high_discharge: bool) -> str:
        """Generate alert reason text"""
        reasons = []
        if has_spillway:
            gates = []
            if r.get("ncxs"):
                gates.append(f"{r['ncxs']} cửa xả sâu")
            if r.get("ncxm"):
                gates.append(f"{r['ncxm']} cửa xả mặt")
            reasons.append(f"Đang mở {', '.join(gates)}")
        if high_water:
            reasons.append(f"Mực nước cao ({r.get('water_percent', 0):.1f}%)")
        if high_discharge:
            reasons.append(f"Lưu lượng xả lớn ({r.get('total_qx', 0):.0f} m³/s)")
        return ". ".join(reasons)

    def get_today_cached(self) -> Dict[str, Any]:
        """
        Get reservoir data for today from DB cache.
        Returns empty data if no cache for today.
        """
        today_data = self.repo.get_today_data()

        if today_data:
            # Add basin info
            for item in today_data:
                item["basin"] = self.RESERVOIR_BASINS.get(item["name"], "UNKNOWN")
                if item.get("hdbt") and item.get("htl"):
                    item["water_percent"] = round(item["htl"] / item["hdbt"] * 100, 1)
                else:
                    item["water_percent"] = None

            print(f"✓ Lấy {len(today_data)} hồ chứa từ DB cache (ngày hôm nay)")
            return {
                "data": today_data,
                "cached": True,
                "from_db": True,
                "count": len(today_data),
                "cache_date": str(datetime.now().date()),
                "fetched_at": today_data[0].get("fetched_at").isoformat() if today_data and today_data[0].get("fetched_at") else None
            }

        print("✗ Không có data hồ chứa ngày hôm nay trong DB")
        return {
            "data": [],
            "cached": False,
            "from_db": True,
            "count": 0,
            "cache_date": str(datetime.now().date()),
            "message": "No data for today, please scrape"
        }

    def get_summary(self) -> Dict[str, Any]:
        """Get summary statistics"""
        all_data = self.get_all_reservoirs()

        if not all_data:
            return {
                "total": 0,
                "by_basin": {},
                "high_water_count": 0,
                "spillway_open_count": 0,
                "last_updated": None
            }

        by_basin = {}
        high_water_count = 0
        spillway_open_count = 0

        for r in all_data:
            basin = r.get("basin", "UNKNOWN")
            by_basin[basin] = by_basin.get(basin, 0) + 1

            if (r.get("water_percent") or 0) >= 90:
                high_water_count += 1
            if (r.get("ncxs") or 0) > 0 or (r.get("ncxm") or 0) > 0:
                spillway_open_count += 1

        return {
            "total": len(all_data),
            "by_basin": by_basin,
            "high_water_count": high_water_count,
            "spillway_open_count": spillway_open_count,
            "last_updated": all_data[0].get("fetched_at").isoformat() if all_data and all_data[0].get("fetched_at") else None
        }
