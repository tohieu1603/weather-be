#!/usr/bin/env python3
"""
Script cào dữ liệu hồ chứa EVN và lưu vào database.
Chạy script này bằng cron job mỗi ngày hoặc vài giờ một lần.

Yêu cầu:
1. Cài Chrome/Chromium: apt install chromium-browser
2. Cài dependencies: pip install selenium webdriver-manager

Cách chạy:
    python3 scripts/scrape_evn.py

Cron job ví dụ (chạy mỗi 6 giờ):
    0 */6 * * * cd /path/to/backend && /path/to/venv/bin/python scripts/scrape_evn.py >> /var/log/evn_scrape.log 2>&1
"""
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from typing import List, Dict, Any

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
    print("ERROR: Selenium not available. Please install:")
    print("  pip install selenium webdriver-manager")
    sys.exit(1)

from repositories.evn_reservoir_repository import EVNReservoirRepository

EVN_URL = "https://hochuathuydien.evn.com.vn/PageHoChuaThuyDienEmbedEVN.aspx"


def scrape_evn_data() -> List[Dict[str, Any]]:
    """Scrape reservoir data from EVN website using Selenium"""
    print(f"[{datetime.now()}] Starting EVN scrape...")

    # Setup Chrome options for headless mode
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

    try:
        # Try system Chrome first
        service = Service()
        driver = webdriver.Chrome(service=service, options=chrome_options)
    except Exception:
        try:
            # Fallback to ChromeDriverManager
            print("Using ChromeDriverManager to install driver...")
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
        except Exception as e:
            print(f"ERROR: Could not start Chrome: {e}")
            print("Please install Chrome/Chromium: apt install chromium-browser")
            return []

    try:
        # Navigate to EVN page
        driver.get(EVN_URL)
        print(f"Loaded: {EVN_URL}")

        # Wait for table to load
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.TAG_NAME, "table"))
        )

        # Wait a bit more for JavaScript to populate data
        import time
        time.sleep(5)

        # Find all tables
        tables = driver.find_elements(By.TAG_NAME, "table")
        print(f"Found {len(tables)} tables")

        reservoirs = []
        for table in tables:
            rows = table.find_elements(By.TAG_NAME, "tr")

            for row in rows[2:]:  # Skip header rows
                cells = row.find_elements(By.TAG_NAME, "td")
                if len(cells) < 10:
                    continue

                # Parse reservoir name (remove timestamp if present)
                name = cells[0].text.strip()
                if "Đồng bộ lúc:" in name:
                    name = name.split("Đồng bộ lúc:")[0].strip()

                # Skip if name is empty or looks like a summary row
                if not name or "tổng" in name.lower() or "stt" in name.lower():
                    continue

                # Skip if name looks like a number
                if name.replace(".", "").replace(",", "").isdigit():
                    continue

                def parse_num(text):
                    """Parse number from text, return None if invalid"""
                    if not text or text == "-" or text.strip() == "":
                        return None
                    try:
                        return float(text.replace(",", ".").strip())
                    except ValueError:
                        return None

                # EVN table structure:
                # [0] Tên hồ, [1] Ngày, [2] Htl, [3] Hdbt, [4] Hc,
                # [5] Qve, [6] ΣQx, [7] Qxt, [8] Qxm, [9] Ncxs, [10] Ncxm
                reservoirs.append({
                    "name": name,
                    "htl": parse_num(cells[2].text),
                    "hdbt": parse_num(cells[3].text),
                    "hc": parse_num(cells[4].text),
                    "qve": parse_num(cells[5].text),
                    "total_qx": parse_num(cells[6].text),
                    "qxt": parse_num(cells[7].text),
                    "qxm": parse_num(cells[8].text),
                    "ncxs": int(parse_num(cells[9].text) or 0),
                    "ncxm": int(parse_num(cells[10].text) or 0) if len(cells) > 10 else 0,
                })

        print(f"Scraped {len(reservoirs)} reservoirs")
        return reservoirs

    except Exception as e:
        print(f"ERROR scraping EVN: {e}")
        import traceback
        traceback.print_exc()
        return []

    finally:
        driver.quit()


def main():
    """Main function to scrape and save EVN data"""
    print("=" * 60)
    print(f"EVN Reservoir Scraper - {datetime.now()}")
    print("=" * 60)

    # Scrape data
    data = scrape_evn_data()

    if not data:
        print("ERROR: No data scraped!")
        sys.exit(1)

    # Save to database
    repo = EVNReservoirRepository()
    saved_count = repo.save_batch(data)

    print(f"\n✓ Saved {saved_count}/{len(data)} reservoirs to database")
    print(f"Completed at {datetime.now()}")

    # Print sample data
    if data:
        print("\nSample data:")
        for r in data[:3]:
            print(f"  {r['name']}: {r['htl']}m (xả: {r['total_qx']} m³/s)")


if __name__ == "__main__":
    main()
