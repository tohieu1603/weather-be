#!/usr/bin/env python3
"""
EVN Reservoir Service - Fetch and process hydropower reservoir data from EVN
"""
import asyncio
import httpx
import re
from datetime import datetime
from typing import Dict, List, Any, Optional
from bs4 import BeautifulSoup

from repositories.evn_reservoir_repository import EVNReservoirRepository

# Playwright imports (preferred - lighter than Selenium)
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

# Selenium imports (fallback - only used for scraping)
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from webdriver_manager.chrome import ChromeDriverManager
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

if not PLAYWRIGHT_AVAILABLE and not SELENIUM_AVAILABLE:
    print("Warning: Neither Playwright nor Selenium available. EVN scraping disabled.")
    print("Install with: pip install playwright && playwright install chromium")
    print("Or: pip install selenium webdriver-manager")


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

    def scrape_evn_playwright(self) -> List[Dict[str, Any]]:
        """
        Scrape EVN reservoir data using Playwright (lighter than Selenium).
        Install: pip install playwright && playwright install chromium
        """
        if not PLAYWRIGHT_AVAILABLE:
            print("[EVN] Playwright not available")
            return []

        reservoirs = []
        try:
            print(f"[EVN Playwright] Loading {self.EVN_URL}...")
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(self.EVN_URL, wait_until="networkidle", timeout=30000)

                # Wait for table to load
                page.wait_for_selector("table", timeout=15000)

                # Additional wait for AJAX data
                page.wait_for_timeout(3000)

                # Get all tables
                tables = page.query_selector_all("table")
                print(f"[EVN Playwright] Found {len(tables)} tables")

                for table in tables:
                    rows = table.query_selector_all("tr")

                    for row in rows[2:]:  # Skip header rows
                        cells = row.query_selector_all("td")
                        if len(cells) < 10:
                            continue

                        # Parse reservoir name
                        name = cells[0].inner_text().strip()
                        if "Đồng bộ lúc:" in name:
                            name = name.split("Đồng bộ lúc:")[0].strip()

                        if not name or "tổng" in name.lower() or "stt" in name.lower():
                            continue

                        if name.replace(".", "").replace(",", "").isdigit():
                            continue

                        # EVN table: [0]Tên, [1]Ngày, [2]Htl, [3]Hdbt, [4]Hc, [5]Qve, [6]ΣQx, [7]Qxt, [8]Qxm, [9]Ncxs, [10]Ncxm
                        reservoirs.append({
                            "name": name,
                            "htl": self._parse_float(cells[2].inner_text()),
                            "hdbt": self._parse_float(cells[3].inner_text()),
                            "hc": self._parse_float(cells[4].inner_text()),
                            "qve": self._parse_float(cells[5].inner_text()),
                            "total_qx": self._parse_float(cells[6].inner_text()),
                            "qxt": self._parse_float(cells[7].inner_text()),
                            "qxm": self._parse_float(cells[8].inner_text()),
                            "ncxs": self._parse_int(cells[9].inner_text()),
                            "ncxm": self._parse_int(cells[10].inner_text()) if len(cells) > 10 else 0,
                        })

                browser.close()

            print(f"[EVN Playwright] Scraped {len(reservoirs)} reservoirs")
            return reservoirs

        except Exception as e:
            print(f"[EVN Playwright] Error: {e}")
            import traceback
            traceback.print_exc()
            return []

    def scrape_evn_selenium(self) -> List[Dict[str, Any]]:
        """
        Scrape EVN reservoir data using Selenium (headless Chrome).
        This works on VPS with Chrome installed.
        """
        if not SELENIUM_AVAILABLE:
            print("Selenium not available, cannot scrape")
            return []

        reservoirs = []
        driver = None

        try:
            # Setup Chrome options for headless mode
            chrome_options = Options()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

            # Initialize driver
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)

            print(f"[EVN Scraper] Loading {self.EVN_URL}...")
            driver.get(self.EVN_URL)

            # Wait for table to load
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, "table"))
            )

            # Additional wait for AJAX data
            import time
            time.sleep(3)

            # Get page source and parse with BeautifulSoup
            soup = BeautifulSoup(driver.page_source, "html.parser")
            tables = soup.find_all("table")

            for table in tables:
                rows = table.find_all("tr")
                for row in rows[2:]:  # Skip header rows
                    cells = row.find_all("td")
                    if len(cells) >= 10:
                        # Get reservoir name (clean timestamp)
                        name = cells[0].get_text(strip=True)
                        name = re.sub(r'Đồng bộ lúc:.*$', '', name, flags=re.IGNORECASE).strip()

                        if not name or name.lower().startswith(("tổng", "stt")) or re.match(r'^\d+\.?\d*$', name):
                            continue

                        # Parse data - EVN table structure:
                        # [0] Name, [1] Day, [2] Htl, [3] Hdbt, [4] Hc, [5] Qve, [6] ΣQx, [7] Qxt, [8] Qxm, [9] Ncxs, [10] Ncxm
                        reservoirs.append({
                            "name": name,
                            "htl": self._parse_float(cells[2].get_text(strip=True)),
                            "hdbt": self._parse_float(cells[3].get_text(strip=True)),
                            "hc": self._parse_float(cells[4].get_text(strip=True)),
                            "qve": self._parse_float(cells[5].get_text(strip=True)),
                            "total_qx": self._parse_float(cells[6].get_text(strip=True)),
                            "qxt": self._parse_float(cells[7].get_text(strip=True)),
                            "qxm": self._parse_float(cells[8].get_text(strip=True)),
                            "ncxs": self._parse_int(cells[9].get_text(strip=True)),
                            "ncxm": self._parse_int(cells[10].get_text(strip=True)) if len(cells) > 10 else None,
                        })

            print(f"[EVN Scraper] Found {len(reservoirs)} reservoirs")

        except Exception as e:
            print(f"[EVN Scraper] Error: {e}")

        finally:
            if driver:
                driver.quit()

        return reservoirs

    def scrape_and_save(self) -> Dict[str, Any]:
        """
        Scrape EVN data and save to database.
        Returns result with count and status.
        """
        reservoirs = self.scrape_evn_selenium()

        if not reservoirs:
            return {
                "success": False,
                "count": 0,
                "message": "No data scraped from EVN"
            }

        # Save to database
        count = self.repo.save_batch(reservoirs)

        # Invalidate cache
        self._cache = None
        self._cache_time = None

        return {
            "success": True,
            "count": count,
            "message": f"Scraped and saved {count} reservoirs from EVN"
        }

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

        # Check if we have today's data
        has_today = self.repo.has_today_data()

        if has_today:
            # Use today's data from DB
            data = self.repo.get_today_data()
            print(f"[EVN] Using today's data from DB: {len(data)} reservoirs")
        else:
            # No data for today - need to scrape
            print("[EVN] No data for today, attempting to scrape from EVN...")
            data = None

            # Try Playwright first (lighter, preferred)
            if PLAYWRIGHT_AVAILABLE and not data:
                try:
                    scraped = self.scrape_evn_playwright()
                    if scraped and len(scraped) > 20:  # Valid data should have 30+ reservoirs
                        self.repo.save_batch(scraped)
                        data = scraped
                        print(f"[EVN] Playwright: Scraped and saved {len(data)} reservoirs")
                except Exception as e:
                    print(f"[EVN] Playwright scraping failed: {e}")

            # Fallback to Selenium if Playwright failed
            if SELENIUM_AVAILABLE and not data:
                try:
                    scraped = self.scrape_evn_selenium()
                    if scraped and len(scraped) > 20:
                        self.repo.save_batch(scraped)
                        data = scraped
                        print(f"[EVN] Selenium: Scraped and saved {len(data)} reservoirs")
                except Exception as e:
                    print(f"[EVN] Selenium scraping failed: {e}")

            # If scraping failed, try to use latest data from DB (even if old)
            if not data:
                data = self.repo.get_latest()
                if data:
                    print(f"[EVN] Using cached data from DB: {len(data)} reservoirs")

            # If still no data, use sample data as fallback
            if not data:
                print("[EVN] WARNING: Using sample data as fallback (no scraper available)")
                print("[EVN] Install: pip install playwright && playwright install chromium")
                data = self._get_sample_data()

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

    def _get_sample_data(self) -> List[Dict[str, Any]]:
        """Return sample reservoir data when DB is empty"""
        # Sample data for major Vietnamese hydropower reservoirs
        return [
            {"name": "Hòa Bình", "htl": 115.5, "hdbt": 117.0, "hc": 80.0, "qve": 850, "total_qx": 720, "qxt": 720, "qxm": 0, "ncxs": 0, "ncxm": 0},
            {"name": "Sơn La", "htl": 213.8, "hdbt": 215.0, "hc": 175.0, "qve": 1200, "total_qx": 980, "qxt": 980, "qxm": 0, "ncxs": 0, "ncxm": 0},
            {"name": "Lai Châu", "htl": 292.5, "hdbt": 295.0, "hc": 255.0, "qve": 450, "total_qx": 380, "qxt": 380, "qxm": 0, "ncxs": 0, "ncxm": 0},
            {"name": "Thác Bà", "htl": 57.2, "hdbt": 58.0, "hc": 46.0, "qve": 120, "total_qx": 95, "qxt": 95, "qxm": 0, "ncxs": 0, "ncxm": 0},
            {"name": "Tuyên Quang", "htl": 119.8, "hdbt": 120.0, "hc": 90.0, "qve": 280, "total_qx": 245, "qxt": 245, "qxm": 0, "ncxs": 0, "ncxm": 0},
            {"name": "Bản Chát", "htl": 472.5, "hdbt": 475.0, "hc": 431.0, "qve": 85, "total_qx": 70, "qxt": 70, "qxm": 0, "ncxs": 0, "ncxm": 0},
            {"name": "Huội Quảng", "htl": 368.2, "hdbt": 370.0, "hc": 340.0, "qve": 65, "total_qx": 55, "qxt": 55, "qxm": 0, "ncxs": 0, "ncxm": 0},
            {"name": "Trị An", "htl": 61.5, "hdbt": 62.0, "hc": 50.0, "qve": 320, "total_qx": 280, "qxt": 280, "qxm": 0, "ncxs": 0, "ncxm": 0},
            {"name": "Thác Mơ", "htl": 216.8, "hdbt": 218.0, "hc": 195.0, "qve": 95, "total_qx": 82, "qxt": 82, "qxm": 0, "ncxs": 0, "ncxm": 0},
            {"name": "Cần Đơn", "htl": 108.2, "hdbt": 110.0, "hc": 95.0, "qve": 78, "total_qx": 65, "qxt": 65, "qxm": 0, "ncxs": 0, "ncxm": 0},
            {"name": "A Vương", "htl": 378.5, "hdbt": 380.0, "hc": 340.0, "qve": 125, "total_qx": 108, "qxt": 108, "qxm": 0, "ncxs": 0, "ncxm": 0},
            {"name": "Sông Tranh 2", "htl": 172.8, "hdbt": 175.0, "hc": 140.0, "qve": 165, "total_qx": 142, "qxt": 142, "qxm": 0, "ncxs": 0, "ncxm": 0},
            {"name": "Đắk Mi 4", "htl": 255.2, "hdbt": 258.0, "hc": 225.0, "qve": 88, "total_qx": 75, "qxt": 75, "qxm": 0, "ncxs": 0, "ncxm": 0},
            {"name": "Bình Điền", "htl": 82.5, "hdbt": 85.0, "hc": 55.0, "qve": 145, "total_qx": 128, "qxt": 128, "qxm": 0, "ncxs": 0, "ncxm": 0},
            {"name": "Buôn Kuốp", "htl": 410.8, "hdbt": 412.0, "hc": 395.0, "qve": 185, "total_qx": 162, "qxt": 162, "qxm": 0, "ncxs": 0, "ncxm": 0},
            {"name": "Buôn Tua Srah", "htl": 492.2, "hdbt": 495.0, "hc": 470.0, "qve": 95, "total_qx": 82, "qxt": 82, "qxm": 0, "ncxs": 0, "ncxm": 0},
            {"name": "Srêpốk 3", "htl": 268.5, "hdbt": 270.0, "hc": 250.0, "qve": 135, "total_qx": 118, "qxt": 118, "qxm": 0, "ncxs": 0, "ncxm": 0},
            {"name": "Ialy", "htl": 512.8, "hdbt": 515.0, "hc": 490.0, "qve": 225, "total_qx": 198, "qxt": 198, "qxm": 0, "ncxs": 0, "ncxm": 0},
            {"name": "Sê San 4", "htl": 212.5, "hdbt": 215.0, "hc": 190.0, "qve": 175, "total_qx": 155, "qxt": 155, "qxm": 0, "ncxs": 0, "ncxm": 0},
            {"name": "Đại Ninh", "htl": 878.2, "hdbt": 880.0, "hc": 860.0, "qve": 45, "total_qx": 38, "qxt": 38, "qxm": 0, "ncxs": 0, "ncxm": 0},
        ]

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
