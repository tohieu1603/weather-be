#!/usr/bin/env python3
"""
Script cào dữ liệu EVN từ máy local và sync lên VPS.
Dùng khi VPS không có Chrome/Selenium.

Cách chạy:
    python scripts/sync_to_vps.py --vps-url https://your-vps.com

Hoặc với URL mặc định:
    python scripts/sync_to_vps.py
"""
import sys
import os
import argparse
import requests
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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

EVN_URL = "https://hochuathuydien.evn.com.vn/PageHoChuaThuyDienEmbedEVN.aspx"


def scrape_evn_data():
    """Scrape reservoir data from EVN website"""
    print(f"[{datetime.now()}] Starting EVN scrape...")

    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")

    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
    except Exception as e:
        print(f"ERROR starting Chrome: {e}")
        return []

    try:
        driver.get(EVN_URL)
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.TAG_NAME, "table"))
        )

        import time
        time.sleep(5)

        tables = driver.find_elements(By.TAG_NAME, "table")
        reservoirs = []

        for table in tables:
            rows = table.find_elements(By.TAG_NAME, "tr")

            for row in rows[2:]:
                cells = row.find_elements(By.TAG_NAME, "td")
                if len(cells) < 10:
                    continue

                name = cells[0].text.strip()
                if "Đồng bộ lúc:" in name:
                    name = name.split("Đồng bộ lúc:")[0].strip()

                if not name or "tổng" in name.lower() or "stt" in name.lower():
                    continue

                if name.replace(".", "").replace(",", "").isdigit():
                    continue

                def parse_num(text):
                    if not text or text == "-" or text.strip() == "":
                        return None
                    try:
                        return float(text.replace(",", ".").strip())
                    except ValueError:
                        return None

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
        print(f"ERROR scraping: {e}")
        return []

    finally:
        driver.quit()


def sync_to_vps(data, vps_url):
    """Sync scraped data to VPS via API"""
    sync_endpoint = f"{vps_url.rstrip('/')}/api/evn-reservoirs/sync"

    print(f"Syncing {len(data)} reservoirs to {sync_endpoint}...")

    try:
        response = requests.post(
            sync_endpoint,
            json=data,
            headers={"Content-Type": "application/json"},
            timeout=30
        )

        if response.ok:
            result = response.json()
            print(f"✓ Sync successful: {result}")
            return True
        else:
            print(f"✗ Sync failed: {response.status_code} - {response.text}")
            return False

    except Exception as e:
        print(f"✗ Sync error: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Scrape EVN and sync to VPS")
    parser.add_argument(
        "--vps-url",
        default="http://localhost:8000",
        help="VPS backend URL (default: http://localhost:8000)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only scrape, don't sync"
    )

    args = parser.parse_args()

    print("=" * 60)
    print(f"EVN Scraper -> VPS Sync - {datetime.now()}")
    print(f"VPS URL: {args.vps_url}")
    print("=" * 60)

    # Scrape data
    data = scrape_evn_data()

    if not data:
        print("ERROR: No data scraped!")
        sys.exit(1)

    # Print sample
    print("\nSample data:")
    for r in data[:3]:
        print(f"  {r['name']}: {r['htl']}m (xả: {r['total_qx']} m³/s)")

    if args.dry_run:
        print("\n[DRY RUN] Skipping sync")
        return

    # Sync to VPS
    if sync_to_vps(data, args.vps_url):
        print(f"\n✓ Done! {len(data)} reservoirs synced to VPS")
    else:
        print("\n✗ Sync failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
