# Hướng dẫn cài đặt EVN Scraper trên VPS

## Cách 1: Dùng Playwright (KHUYẾN NGHỊ - nhẹ hơn)

```bash
cd /path/to/futureweather/backend
source venv/bin/activate

# Cài Playwright
pip install playwright

# Cài Chromium browser (tự động download)
playwright install chromium

# Cài dependencies cho Linux headless
playwright install-deps chromium
```

**Ưu điểm Playwright:**
- Tự động download browser, không cần cài Chrome riêng
- Nhẹ hơn Selenium
- Hoạt động tốt trên VPS

## Cách 2: Dùng Selenium (nếu Playwright không hoạt động)

### Bước 1: Cài đặt Chrome/Chromium

#### Ubuntu/Debian:
```bash
sudo apt update
sudo apt install -y chromium-browser
```

#### CentOS/RHEL:
```bash
sudo yum install -y chromium
```

### Bước 2: Cài đặt Python dependencies

```bash
cd /path/to/futureweather/backend
source venv/bin/activate
pip install selenium webdriver-manager
```

## Bước 3: Test script

```bash
cd /path/to/futureweather/backend
source venv/bin/activate
python scripts/scrape_evn.py
```

## Bước 4: Thiết lập Cron Job (chạy tự động)

```bash
# Mở crontab editor
crontab -e

# Thêm dòng sau (chạy mỗi 6 giờ):
0 */6 * * * cd /path/to/futureweather/backend && /path/to/venv/bin/python scripts/scrape_evn.py >> /var/log/evn_scrape.log 2>&1

# Hoặc chạy 2 lần/ngày (6h sáng và 6h tối):
0 6,18 * * * cd /path/to/futureweather/backend && /path/to/venv/bin/python scripts/scrape_evn.py >> /var/log/evn_scrape.log 2>&1
```

## Bước 5: Kiểm tra kết quả

```bash
# Xem log
tail -f /var/log/evn_scrape.log

# Kiểm tra API
curl http://localhost:8000/api/evn-reservoirs/ | python3 -c "import sys, json; d=json.load(sys.stdin); print(f'Total: {d[\"total\"]}')"
```

## Lựa chọn thay thế: Scrape từ máy local và sync lên VPS

Nếu VPS không thể cài Chrome, bạn có thể:

1. Chạy script scrape trên máy local
2. Gửi dữ liệu lên VPS qua API `/api/evn-reservoirs/sync`

```bash
# Trên máy local (có Chrome)
cd /path/to/futureweather/backend
python scripts/sync_to_vps.py --vps-url https://your-vps-domain.com
```

## Troubleshooting

### Lỗi "Chrome not found":
```bash
which chromium-browser
# hoặc
which google-chrome

# Đảm bảo Chrome có trong PATH
export PATH=$PATH:/usr/bin
```

### Lỗi "DevToolsActivePort file doesn't exist":
Thêm options vào Chrome:
```python
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--remote-debugging-port=9222")
```

### Kiểm tra Chrome headless chạy được không:
```bash
chromium-browser --headless --disable-gpu --dump-dom https://google.com
```
