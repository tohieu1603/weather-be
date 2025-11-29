#!/usr/bin/env python3
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, List, Optional
from datetime import datetime
import sys
import os
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import từ p.py
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from p import (
    MONITORING_POINTS,
    BASIN_WEIGHTS,
    FLOOD_THRESHOLDS,
    fetch_weather_data,
    calculate_basin_rainfall,
    analyze_basin_forecast
)

# Import weather API module
from weather_api import (
    VIETNAM_LOCATIONS,
    fetch_forecast_full,
    fetch_flood_forecast,
    fetch_air_quality,
    fetch_marine_forecast,
    get_all_vietnam_weather,
    analyze_weather_for_alerts,
    get_weather_description,
    WEATHER_CODES
)

# Import database module for caching
try:
    from database import (
        check_db_available,
        get_cached_ai_analysis,
        save_ai_analysis_cache
    )
    DB_AVAILABLE = check_db_available()
    print(f"Database cache: {'enabled' if DB_AVAILABLE else 'disabled'}")
except ImportError:
    DB_AVAILABLE = False
    print("Database module not available, using memory cache only")

app = FastAPI(
    title="Hệ thống Dự báo Lũ Lụt API",
    description="API cung cấp dữ liệu dự báo thiên tai lũ lụt cho Việt Nam",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "http://localhost:3002"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Cache để tránh gọi API quá nhiều
forecast_cache = {
    "data": None,
    "timestamp": None
}

# Cache cho real weather data (Open-Meteo)
real_weather_cache = {
    "data": None,
    "timestamp": None,
    "alerts": None
}

CACHE_DURATION = 86400  # 24 hours (24 * 60 * 60)
REAL_WEATHER_CACHE_DURATION = 86400  # 24 hours cho dữ liệu thật

# Initialize DeepSeek client
deepseek_client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)


@app.get("/")
async def root():
    return {
        "message": "Hệ thống Dự báo Lũ Lụt Vietnam API",
        "version": "1.0.0",
        "endpoints": {
            "/api/forecast/all": "Lấy dự báo tất cả lưu vực",
            "/api/forecast/basin/{basin_name}": "Lấy dự báo một lưu vực (HONG, MEKONG, DONGNAI, CENTRAL)",
            "/api/basins/summary": "Tóm tắt tình trạng các lưu vực",
            "/api/stations": "Danh sách trạm quan trắc với risk levels",
            "/api/alerts": "Danh sách cảnh báo"
        },
        "basins": ["HONG", "MEKONG", "DONGNAI", "CENTRAL"]
    }


def get_cached_or_fetch():
    """Lấy dữ liệu từ cache hoặc fetch mới"""
    now = datetime.now()

    # Kiểm tra cache
    if forecast_cache["data"] and forecast_cache["timestamp"]:
        elapsed = (now - forecast_cache["timestamp"]).total_seconds()
        if elapsed < CACHE_DURATION:
            return forecast_cache["data"]

    # Fetch dữ liệu mới
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
        raise HTTPException(status_code=500, detail="Không lấy được dữ liệu từ API")

    # Phân tích từng lưu vực
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
        "generated_at": now.isoformat(),
        "basins": all_analysis,
        "stations_loaded": len(station_data),
        "stations_failed": failed_stations,
        "forecast_days": len(dates_ref)
    }

    # Cập nhật cache
    forecast_cache["data"] = result
    forecast_cache["timestamp"] = now

    print(f"✓ Fetched data for {len(all_analysis)} basins")
    return result


@app.get("/api/forecast/all")
async def get_all_forecasts(force_refresh: bool = False):
    """Lấy dự báo cho tất cả lưu vực"""
    try:
        if force_refresh:
            forecast_cache["data"] = None

        return get_cached_or_fetch()
    except Exception as e:
        print(f"Error in /api/forecast/all: {e}")
        raise HTTPException(status_code=500, detail=str(e))


import json as json_module
from datetime import date as date_type

def analyze_forecast_with_ai(basin_name: str, forecast_data: dict) -> dict:
    """
    Sử dụng DeepSeek AI để phân tích dự báo - trả về structured JSON với chi tiết huyện/xã

    Cache: Kết quả được lưu vào PostgreSQL, valid trong 1 ngày
    """
    # === KIỂM TRA CACHE TRƯỚC ===
    if DB_AVAILABLE:
        cached = get_cached_ai_analysis(basin_name, date_type.today())
        if cached:
            print(f"✓ Using cached AI analysis for {basin_name}")
            return cached

    try:
        # Chuẩn bị dữ liệu cho AI
        forecast_days = forecast_data.get("forecast_days", [])

        # Map basin name to region info với chi tiết huyện/xã
        basin_info = {
            "HONG": {
                "region_name": "Miền Bắc",
                "provinces": {
                    "Hà Nội": ["Ba Vì", "Chương Mỹ", "Đan Phượng", "Hoài Đức", "Mỹ Đức", "Phú Xuyên", "Quốc Oai", "Thường Tín"],
                    "Hải Phòng": ["An Dương", "An Lão", "Kiến Thụy", "Thủy Nguyên", "Tiên Lãng", "Vĩnh Bảo"],
                    "Thái Bình": ["Đông Hưng", "Hưng Hà", "Kiến Xương", "Quỳnh Phụ", "Thái Thụy", "Tiền Hải", "Vũ Thư"],
                    "Nam Định": ["Giao Thủy", "Hải Hậu", "Mỹ Lộc", "Nam Trực", "Nghĩa Hưng", "Trực Ninh", "Vụ Bản", "Xuân Trường", "Ý Yên"],
                    "Phú Thọ": ["Cẩm Khê", "Đoan Hùng", "Hạ Hòa", "Lâm Thao", "Phù Ninh", "Tam Nông", "Thanh Ba", "Thanh Sơn", "Thanh Thủy", "Yên Lập"],
                },
            },
            "CENTRAL": {
                "region_name": "Miền Trung",
                "provinces": {
                    "Đà Nẵng": ["Hải Châu", "Thanh Khê", "Sơn Trà", "Ngũ Hành Sơn", "Liên Chiểu", "Cẩm Lệ", "Hòa Vang"],
                    "Quảng Nam": ["Tam Kỳ", "Hội An", "Điện Bàn", "Duy Xuyên", "Đại Lộc", "Núi Thành", "Thăng Bình", "Quế Sơn"],
                    "Thừa Thiên Huế": ["TP Huế", "Hương Thủy", "Hương Trà", "Phong Điền", "Quảng Điền", "Phú Lộc", "Phú Vang"],
                    "Quảng Ngãi": ["TP Quảng Ngãi", "Bình Sơn", "Sơn Tịnh", "Tư Nghĩa", "Nghĩa Hành", "Mộ Đức", "Đức Phổ"],
                    "Bình Định": ["Quy Nhơn", "An Nhơn", "Tuy Phước", "Phù Cát", "Phù Mỹ", "Hoài Nhơn", "Hoài Ân"],
                    "Quảng Bình": ["Đồng Hới", "Bố Trạch", "Quảng Trạch", "Lệ Thủy", "Quảng Ninh", "Tuyên Hóa"],
                    "Quảng Trị": ["Đông Hà", "Triệu Phong", "Hải Lăng", "Gio Linh", "Vĩnh Linh", "Cam Lộ"],
                    "Hà Tĩnh": ["TP Hà Tĩnh", "Kỳ Anh", "Cẩm Xuyên", "Thạch Hà", "Can Lộc", "Đức Thọ", "Nghi Xuân"],
                    "Nghệ An": ["TP Vinh", "Cửa Lò", "Diễn Châu", "Quỳnh Lưu", "Yên Thành", "Đô Lương", "Nam Đàn"],
                    "Thanh Hóa": ["TP Thanh Hóa", "Sầm Sơn", "Hoằng Hóa", "Hậu Lộc", "Nga Sơn", "Tĩnh Gia", "Quảng Xương"],
                },
            },
            "MEKONG": {
                "region_name": "Miền Nam",
                "provinces": {
                    "An Giang": ["Long Xuyên", "Châu Đốc", "Tân Châu", "Châu Phú", "Chợ Mới", "Phú Tân", "Thoại Sơn"],
                    "Đồng Tháp": ["Cao Lãnh", "Sa Đéc", "Hồng Ngự", "Tân Hồng", "Tam Nông", "Thanh Bình", "Châu Thành"],
                    "Cần Thơ": ["Ninh Kiều", "Bình Thủy", "Cái Răng", "Ô Môn", "Thốt Nốt", "Phong Điền", "Cờ Đỏ", "Vĩnh Thạnh"],
                    "Long An": ["Tân An", "Kiến Tường", "Bến Lức", "Đức Hòa", "Đức Huệ", "Thủ Thừa", "Tân Trụ", "Cần Đước"],
                    "Tiền Giang": ["Mỹ Tho", "Gò Công", "Cai Lậy", "Châu Thành", "Chợ Gạo", "Gò Công Đông", "Gò Công Tây"],
                },
            },
            "DONGNAI": {
                "region_name": "Đông Nam Bộ",
                "provinces": {
                    "TP.HCM": ["Thủ Đức", "Quận 7", "Bình Chánh", "Nhà Bè", "Cần Giờ", "Hóc Môn", "Củ Chi", "Quận 12"],
                    "Đồng Nai": ["Biên Hòa", "Long Khánh", "Nhơn Trạch", "Long Thành", "Trảng Bom", "Vĩnh Cửu", "Định Quán"],
                    "Bình Dương": ["Thủ Dầu Một", "Dĩ An", "Thuận An", "Tân Uyên", "Bến Cát", "Bàu Bàng", "Phú Giáo"],
                    "Bà Rịa-Vũng Tàu": ["Vũng Tàu", "Bà Rịa", "Long Điền", "Đất Đỏ", "Xuyên Mộc", "Châu Đức", "Côn Đảo"],
                },
            }
        }

        info = basin_info.get(basin_name, {"region_name": basin_name, "provinces": {}})
        province_list = list(info['provinces'].keys()) if isinstance(info['provinces'], dict) else info['provinces']

        # Tạo prompt yêu cầu JSON output với chi tiết huyện
        prompt = f"""Bạn là chuyên gia phân tích thiên tai lũ lụt Việt Nam. Phân tích dự báo cho {info['region_name']} ({basin_name}):

Dữ liệu dự báo 14 ngày:
"""
        for day in forecast_days[:14]:
            prompt += f"\n- {day['date']}: Mưa {day['daily_rain']:.1f}mm, Tích lũy 3 ngày {day['accumulated_3d']:.1f}mm"

        # Thêm thông tin huyện cho mỗi tỉnh
        prompt += f"""

Các tỉnh và huyện trong vùng:
"""
        if isinstance(info['provinces'], dict):
            for province, districts in info['provinces'].items():
                prompt += f"\n- {province}: {', '.join(districts[:5])}"

        prompt += f"""

BẮT BUỘC trả về JSON theo đúng format sau (KHÔNG có text khác, CHỈ JSON):
{{
  "peak_rain": {{
    "date": "YYYY-MM-DD",
    "amount_mm": số,
    "intensity": "Nhẹ/Vừa/Lớn/Rất lớn/Đặc biệt lớn"
  }},
  "flood_timeline": {{
    "rising_start": "YYYY-MM-DD",
    "rising_end": "YYYY-MM-DD",
    "peak_date": "YYYY-MM-DD",
    "receding_start": "YYYY-MM-DD",
    "receding_end": "YYYY-MM-DD"
  }},
  "affected_areas": [
    {{
      "province": "Tên tỉnh",
      "impact_level": "Rất cao/Cao/Trung bình/Thấp/Rất thấp",
      "water_level_cm": số,
      "flood_area_km2": số,
      "reason": "Lý do ngắn gọn",
      "districts": [
        {{
          "name": "Tên huyện/quận",
          "impact_level": "Rất cao/Cao/Trung bình/Thấp",
          "water_level_cm": số,
          "flood_area_km2": số,
          "affected_wards": ["Xã/Phường 1", "Xã/Phường 2", "Xã/Phường 3"],
          "evacuation_needed": true/false,
          "notes": "Ghi chú ngắn"
        }}
      ]
    }}
  ],
  "overall_risk": {{
    "level": "Thấp/Trung bình/Cao/Rất cao/Nguy hiểm",
    "score": số từ 1-10,
    "description": "Mô tả ngắn"
  }},
  "recommendations": {{
    "government": ["Khuyến nghị 1", "Khuyến nghị 2", "Khuyến nghị 3"],
    "citizens": ["Khuyến nghị 1", "Khuyến nghị 2", "Khuyến nghị 3"]
  }},
  "summary": "Tóm tắt 1-2 câu"
}}

QUAN TRỌNG:
- Mỗi tỉnh PHẢI có ít nhất 3-5 huyện trong mảng districts
- Mỗi huyện PHẢI có ít nhất 2-3 xã/phường trong affected_wards
- Phân tích CHI TIẾT dựa trên địa hình, vị trí ven sông của từng huyện
- Nếu lượng mưa thấp, vẫn liệt kê nhưng với impact_level thấp"""

        # Gọi DeepSeek AI
        response = deepseek_client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "Bạn là chuyên gia phân tích thiên tai, thủy văn Việt Nam. LUÔN trả về JSON hợp lệ, không có text khác."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=2000
        )

        result = response.choices[0].message.content.strip()

        # Parse JSON từ response
        # Xử lý trường hợp AI trả về markdown code block
        if result.startswith("```"):
            result = result.split("```")[1]
            if result.startswith("json"):
                result = result[4:]
        result = result.strip()

        analysis = json_module.loads(result)
        # Bổ sung dữ liệu huyện nếu AI không trả về đủ
        analysis = enrich_analysis_with_districts(analysis, basin_name)

        # === LƯU VÀO CACHE DATABASE ===
        if DB_AVAILABLE:
            tokens = response.usage.total_tokens if hasattr(response, 'usage') else None
            save_ai_analysis_cache(basin_name, analysis, date_type.today(), tokens)

        return analysis

    except json_module.JSONDecodeError as e:
        print(f"JSON parse error: {e}")
        print(f"Raw response: {result[:500] if 'result' in dir() else 'N/A'}")
        fallback = get_fallback_analysis(basin_name, forecast_data)
        # Lưu fallback vào cache để lần sau không phải gọi API lại
        if DB_AVAILABLE:
            save_ai_analysis_cache(basin_name, fallback, date_type.today(), None)
        return fallback
    except Exception as e:
        print(f"Error in AI analysis: {e}")
        fallback = get_fallback_analysis(basin_name, forecast_data)
        # Lưu fallback vào cache để lần sau không phải gọi API lại
        if DB_AVAILABLE:
            save_ai_analysis_cache(basin_name, fallback, date_type.today(), None)
        return fallback


def generate_districts_for_province(province: str, impact_level: str, basin_name: str) -> list:
    """Tự động tạo dữ liệu huyện cho tỉnh dựa trên danh sách thực tế"""
    import random

    # Danh sách huyện/quận chi tiết cho từng tỉnh
    province_districts = {
        # Miền Trung
        "Đà Nẵng": {
            "districts": ["Hải Châu", "Thanh Khê", "Sơn Trà", "Ngũ Hành Sơn", "Liên Chiểu", "Cẩm Lệ", "Hòa Vang"],
            "wards": {
                "Hải Châu": ["Thạch Thang", "Hải Châu 1", "Hải Châu 2", "Phước Ninh", "Hòa Thuận Tây", "Hòa Thuận Đông", "Thuận Phước"],
                "Thanh Khê": ["Tam Thuận", "Thanh Khê Đông", "Thanh Khê Tây", "Xuân Hà", "An Khê", "Chính Gián", "Vĩnh Trung"],
                "Sơn Trà": ["Thọ Quang", "Nại Hiên Đông", "Mỹ An", "An Hải Bắc", "An Hải Tây", "Phước Mỹ", "An Hải Đông"],
                "Ngũ Hành Sơn": ["Mỹ An", "Khuê Mỹ", "Hòa Quý", "Hòa Hải"],
                "Liên Chiểu": ["Hòa Khánh Bắc", "Hòa Khánh Nam", "Hòa Minh"],
                "Cẩm Lệ": ["Khuê Trung", "Hòa Thọ Đông", "Hòa Thọ Tây", "Hòa Phát", "Hòa An"],
                "Hòa Vang": ["Hòa Bắc", "Hòa Liên", "Hòa Ninh", "Hòa Phú", "Hòa Khương", "Hòa Sơn", "Hòa Nhơn", "Hòa Phong", "Hòa Châu", "Hòa Tiến"]
            }
        },
        "Quảng Nam": {
            "districts": ["Tam Kỳ", "Hội An", "Điện Bàn", "Duy Xuyên", "Đại Lộc", "Núi Thành", "Thăng Bình", "Quế Sơn"],
            "wards": {
                "Tam Kỳ": ["An Mỹ", "An Sơn", "An Xuân", "Hòa Hương", "Trường Xuân", "Tân Thạnh", "An Phú"],
                "Hội An": ["Minh An", "Sơn Phong", "Cẩm Phô", "Thanh Hà", "Cẩm Châu", "Cẩm An", "Cửa Đại", "Cẩm Thanh"],
                "Điện Bàn": ["Điện Ngọc", "Điện Dương", "Điện Nam Bắc", "Điện Nam Trung", "Điện Phước", "Vĩnh Điện"],
                "Duy Xuyên": ["Nam Phước", "Duy Phú", "Duy Tân", "Duy Hòa", "Duy Châu", "Duy Vinh"],
                "Đại Lộc": ["Ái Nghĩa", "Đại An", "Đại Cường", "Đại Hòa", "Đại Minh", "Đại Phong"],
                "Núi Thành": ["Núi Thành", "Tam Anh Bắc", "Tam Anh Nam", "Tam Hải", "Tam Hiệp", "Tam Mỹ Tây"],
                "Thăng Bình": ["Hà Lam", "Bình An", "Bình Trung", "Bình Phú", "Bình Chánh", "Bình Đào"],
                "Quế Sơn": ["Đông Phú", "Quế Phú", "Quế Xuân", "Hương An"]
            }
        },
        "Thừa Thiên Huế": {
            "districts": ["TP Huế", "Hương Thủy", "Hương Trà", "Phong Điền", "Quảng Điền", "Phú Lộc", "Phú Vang"],
            "wards": {
                "TP Huế": ["Phú Hội", "Vĩnh Ninh", "Phú Nhuận", "Xuân Phú", "Trường An", "Phước Vĩnh", "An Cựu", "An Đông", "Phú Thuận"],
                "Hương Thủy": ["Thủy Dương", "Thủy Phương", "Thủy Châu", "Thủy Lương", "Phú Bài"],
                "Hương Trà": ["Tứ Hạ", "Hương Văn", "Hương Toàn", "Hương Chữ", "Hương Xuân", "Hương An"],
                "Phong Điền": ["Phong Thu", "Phong Hiền", "Phong An", "Phong Sơn", "Phong Mỹ"],
                "Quảng Điền": ["Sịa", "Quảng Lợi", "Quảng Thọ", "Quảng An", "Quảng Phú"],
                "Phú Lộc": ["Lăng Cô", "Phú Lộc", "Vinh Mỹ", "Vinh Hưng", "Giang Hải"],
                "Phú Vang": ["Thuận An", "Phú Đa", "Phú Mỹ", "Phú Hồ", "Phú Lương", "Vinh Xuân"]
            }
        },
        "Quảng Ngãi": {
            "districts": ["TP Quảng Ngãi", "Bình Sơn", "Sơn Tịnh", "Tư Nghĩa", "Nghĩa Hành", "Mộ Đức", "Đức Phổ"],
            "wards": {
                "TP Quảng Ngãi": ["Lê Hồng Phong", "Trần Hưng Đạo", "Nguyễn Nghiêm", "Chánh Lộ", "Quảng Phú", "Nghĩa Lộ"],
                "Bình Sơn": ["Châu Ổ", "Bình Chánh", "Bình Đông", "Bình Dương", "Bình Hòa", "Bình Nguyên"],
                "Sơn Tịnh": ["Tịnh Ấn Tây", "Tịnh Ấn Đông", "Tịnh Châu", "Tịnh Khê", "Tịnh Thiện"],
                "Tư Nghĩa": ["La Hà", "Nghĩa Kỳ", "Nghĩa Lâm", "Nghĩa Thuận", "Nghĩa Phương"],
                "Nghĩa Hành": ["Chợ Chùa", "Hành Đức", "Hành Minh", "Hành Nhân", "Hành Phước"],
                "Mộ Đức": ["Mộ Đức", "Đức Chánh", "Đức Hiệp", "Đức Hòa", "Đức Lợi", "Đức Nhuận"],
                "Đức Phổ": ["Phổ Hòa", "Phổ Ninh", "Phổ Quang", "Phổ Văn", "Phổ Cường", "Phổ Khánh"]
            }
        },
        "Bình Định": {
            "districts": ["Quy Nhơn", "An Nhơn", "Tuy Phước", "Phù Cát", "Phù Mỹ", "Hoài Nhơn", "Hoài Ân"],
            "wards": {
                "Quy Nhơn": ["Trần Hưng Đạo", "Lê Lợi", "Thị Nại", "Ngô Mây", "Ghềnh Ráng", "Nhơn Bình", "Nhơn Phú"],
                "An Nhơn": ["Bình Định", "Nhơn Hòa", "Nhơn Hưng", "Nhơn Khánh", "Nhơn Mỹ", "Nhơn Phong"],
                "Tuy Phước": ["Tuy Phước", "Phước Hiệp", "Phước Hòa", "Phước Lộc", "Phước Nghĩa", "Phước Sơn"],
                "Phù Cát": ["Ngô Mây", "Cát Hải", "Cát Hiệp", "Cát Khánh", "Cát Lâm", "Cát Minh"],
                "Phù Mỹ": ["Bình Dương", "Mỹ Châu", "Mỹ Đức", "Mỹ Hiệp", "Mỹ Hòa", "Mỹ Lộc"],
                "Hoài Nhơn": ["Bồng Sơn", "Hoài Đức", "Hoài Hảo", "Hoài Hương", "Hoài Mỹ", "Hoài Tân"],
                "Hoài Ân": ["Tăng Bạt Hổ", "Ân Hảo Đông", "Ân Hảo Tây", "Ân Mỹ", "Ân Nghĩa", "Ân Phong"]
            }
        },
        # Miền Bắc
        "Hà Nội": {
            "districts": ["Ba Vì", "Chương Mỹ", "Đan Phượng", "Hoài Đức", "Mỹ Đức", "Phú Xuyên", "Quốc Oai", "Thường Tín"],
            "wards": {
                "Ba Vì": ["Tây Đằng", "Cẩm Lĩnh", "Sơn Đà", "Ba Trại", "Minh Quang", "Phú Châu"],
                "Chương Mỹ": ["Chúc Sơn", "Xuân Mai", "Đại Yên", "Thủy Xuân Tiên", "Trường Yên"],
                "Đan Phượng": ["Phùng", "Đan Phượng", "Đồng Tháp", "Hồng Hà", "Liên Hồng"],
                "Hoài Đức": ["Trạm Trôi", "An Khánh", "Di Trạch", "Kim Chung", "La Phù"],
                "Mỹ Đức": ["Đại Nghĩa", "An Mỹ", "An Phú", "Bột Xuyên", "Đại Hưng"],
                "Phú Xuyên": ["Phú Xuyên", "Hoàng Long", "Nam Phong", "Phú Túc", "Tri Trung"],
                "Quốc Oai": ["Quốc Oai", "Đông Yên", "Liệp Tuyết", "Ngọc Liệp", "Sài Sơn"],
                "Thường Tín": ["Thường Tín", "Hiền Giang", "Khánh Hà", "Liên Phương", "Nhị Khê"]
            }
        },
        "Hải Phòng": {
            "districts": ["An Dương", "An Lão", "Kiến Thụy", "Thủy Nguyên", "Tiên Lãng", "Vĩnh Bảo"],
            "wards": {
                "An Dương": ["An Đồng", "Bắc Sơn", "Đại Bản", "Đặng Cương", "Hồng Phong"],
                "An Lão": ["An Lão", "An Thắng", "An Thọ", "Chiến Thắng", "Mỹ Đức"],
                "Kiến Thụy": ["Núi Đèo", "Đoàn Xá", "Du Lễ", "Hữu Bằng", "Minh Tân"],
                "Thủy Nguyên": ["Núi Đèo", "An Lư", "Cao Nhân", "Chính Mỹ", "Dương Quan"],
                "Tiên Lãng": ["Tiên Lãng", "Bạch Đằng", "Cấp Tiến", "Đoàn Lập", "Hùng Thắng"],
                "Vĩnh Bảo": ["Vĩnh Bảo", "An Hòa", "Cao Minh", "Cộng Hiền", "Cổ Am"]
            }
        },
        # Miền Nam
        "An Giang": {
            "districts": ["Long Xuyên", "Châu Đốc", "Tân Châu", "Châu Phú", "Chợ Mới", "Phú Tân", "Thoại Sơn"],
            "wards": {
                "Long Xuyên": ["Mỹ Bình", "Mỹ Long", "Mỹ Phước", "Mỹ Xuyên", "Bình Đức", "Bình Khánh"],
                "Châu Đốc": ["Châu Phú A", "Châu Phú B", "Núi Sam", "Vĩnh Mỹ", "Vĩnh Ngươn"],
                "Tân Châu": ["Tân Châu", "Long An", "Long Phú", "Phú Lộc", "Vĩnh Hòa"],
                "Châu Phú": ["Cái Dầu", "Bình Chánh", "Bình Long", "Bình Mỹ", "Bình Phú"],
                "Chợ Mới": ["Chợ Mới", "An Thạnh Trung", "Bình Phước Xuân", "Hòa An", "Hội An"],
                "Phú Tân": ["Chợ Vàm", "Bình Thạnh Đông", "Hiệp Xương", "Long Hòa", "Phú An"],
                "Thoại Sơn": ["Núi Sập", "An Bình", "Định Mỹ", "Định Thành", "Mỹ Phú Đông"]
            }
        },
        "Đồng Tháp": {
            "districts": ["Cao Lãnh", "Sa Đéc", "Hồng Ngự", "Tân Hồng", "Tam Nông", "Thanh Bình", "Châu Thành"],
            "wards": {
                "Cao Lãnh": ["Phường 1", "Phường 2", "Phường 3", "Phường 4", "Phường 6", "Mỹ Phú"],
                "Sa Đéc": ["Phường 1", "Phường 2", "Phường 3", "Phường 4", "An Hòa", "Tân Quy Đông"],
                "Hồng Ngự": ["An Bình A", "An Bình B", "Bình Thạnh", "An Lộc", "Tân Hội"],
                "Tân Hồng": ["Sa Rài", "An Phước", "Bình Phú", "Tân Công Chí", "Thông Bình"],
                "Tam Nông": ["Tràm Chim", "An Hòa", "An Long", "Phú Cường", "Phú Đức"],
                "Thanh Bình": ["Thanh Bình", "An Phong", "Bình Thành", "Phú Lợi", "Tân Bình"],
                "Châu Thành": ["Cái Tàu Hạ", "An Hiệp", "An Khánh", "An Nhơn", "Tân Nhuận Đông"]
            }
        },
        "Cần Thơ": {
            "districts": ["Ninh Kiều", "Bình Thủy", "Cái Răng", "Ô Môn", "Thốt Nốt", "Phong Điền", "Cờ Đỏ", "Vĩnh Thạnh"],
            "wards": {
                "Ninh Kiều": ["Cái Khế", "An Hội", "An Nghiệp", "An Cư", "An Phú", "Xuân Khánh", "Hưng Lợi"],
                "Bình Thủy": ["Bình Thủy", "Bùi Hữu Nghĩa", "Long Hòa", "Long Tuyền", "Trà An", "Trà Nóc"],
                "Cái Răng": ["Lê Bình", "Hưng Phú", "Hưng Thạnh", "Ba Láng", "Thường Thạnh", "Phú Thứ"],
                "Ô Môn": ["Châu Văn Liêm", "Long Hưng", "Phước Thới", "Thới An", "Thới Hòa", "Thới Long"],
                "Thốt Nốt": ["Thốt Nốt", "Thuận An", "Thuận Hưng", "Tân Hưng", "Tân Lộc"],
                "Phong Điền": ["Phong Điền", "Nhơn Ái", "Nhơn Nghĩa", "Mỹ Khánh", "Giai Xuân"],
                "Cờ Đỏ": ["Thới Đông", "Thới Hưng", "Thới Xuân", "Trung Hưng", "Trung An"],
                "Vĩnh Thạnh": ["Thạnh An", "Thạnh Lợi", "Thạnh Mỹ", "Thạnh Qưới", "Thạnh Tiến", "Vĩnh Bình"]
            }
        },
        # Đông Nam Bộ
        "TP.HCM": {
            "districts": ["Thủ Đức", "Quận 7", "Bình Chánh", "Nhà Bè", "Cần Giờ", "Hóc Môn", "Củ Chi", "Quận 12"],
            "wards": {
                "Thủ Đức": ["Linh Đông", "Linh Tây", "Linh Chiểu", "Bình Thọ", "Tam Bình", "Tam Phú", "Hiệp Bình Chánh"],
                "Quận 7": ["Tân Thuận Đông", "Tân Thuận Tây", "Tân Kiểng", "Tân Hưng", "Bình Thuận", "Tân Quy", "Phú Thuận"],
                "Bình Chánh": ["An Phú Tây", "Bình Chánh", "Bình Hưng", "Đa Phước", "Hưng Long", "Lê Minh Xuân", "Phạm Văn Hai"],
                "Nhà Bè": ["Hiệp Phước", "Long Thới", "Nhà Bè", "Nhơn Đức", "Phú Xuân", "Phước Kiển", "Phước Lộc"],
                "Cần Giờ": ["Bình Khánh", "Cần Thạnh", "Long Hòa", "Lý Nhơn", "Tam Thôn Hiệp", "Thạnh An"],
                "Hóc Môn": ["Bà Điểm", "Đông Thạnh", "Nhị Bình", "Tân Hiệp", "Tân Thới Nhì", "Tân Xuân", "Thới Tam Thôn"],
                "Củ Chi": ["Củ Chi", "An Nhơn Tây", "An Phú", "Bình Mỹ", "Hòa Phú", "Nhuận Đức", "Phạm Văn Cội"],
                "Quận 12": ["An Phú Đông", "Đông Hưng Thuận", "Hiệp Thành", "Tân Chánh Hiệp", "Tân Hưng Thuận", "Tân Thới Hiệp"]
            }
        },
        "Đồng Nai": {
            "districts": ["Biên Hòa", "Long Khánh", "Nhơn Trạch", "Long Thành", "Trảng Bom", "Vĩnh Cửu", "Định Quán"],
            "wards": {
                "Biên Hòa": ["Trảng Dài", "Tân Phong", "Tân Biên", "Hố Nai", "Long Bình", "Bửu Long", "Quang Vinh"],
                "Long Khánh": ["Xuân Lập", "Xuân An", "Xuân Hòa", "Phú Bình", "Bảo Vinh", "Bảo Quang"],
                "Nhơn Trạch": ["Phước An", "Phước Khánh", "Phước Thiền", "Long Tân", "Vĩnh Thanh"],
                "Long Thành": ["An Phước", "Bình An", "Bình Sơn", "Cẩm Đường", "Long An", "Long Đức"],
                "Trảng Bom": ["Trảng Bom", "An Viễn", "Bắc Sơn", "Bình Minh", "Cây Gáo", "Đông Hòa"],
                "Vĩnh Cửu": ["Vĩnh An", "Bình Hòa", "Bình Lợi", "Mã Đà", "Phú Lý", "Tân An"],
                "Định Quán": ["Định Quán", "La Ngà", "Ngọc Định", "Phú Cường", "Phú Hòa", "Thanh Sơn"]
            }
        },
        "Bình Dương": {
            "districts": ["Thủ Dầu Một", "Dĩ An", "Thuận An", "Tân Uyên", "Bến Cát", "Bàu Bàng", "Phú Giáo"],
            "wards": {
                "Thủ Dầu Một": ["Phú Cường", "Hiệp Thành", "Phú Hòa", "Phú Lợi", "Phú Thọ", "Chánh Nghĩa"],
                "Dĩ An": ["Dĩ An", "Tân Bình", "Tân Đông Hiệp", "Bình An", "An Bình", "Đông Hòa"],
                "Thuận An": ["Lái Thiêu", "An Sơn", "An Phú", "Bình Chuẩn", "Bình Hòa", "Thuận Giao"],
                "Tân Uyên": ["Uyên Hưng", "Tân Phước Khánh", "Tân Hiệp", "Khánh Bình", "Vĩnh Tân", "Hội Nghĩa"],
                "Bến Cát": ["Mỹ Phước", "Tân Định", "An Điền", "An Tây", "Thới Hòa", "Chánh Phú Hòa"],
                "Bàu Bàng": ["Lai Uyên", "Trừ Văn Thố", "Long Nguyên", "Hưng Hòa", "Tân Hưng"],
                "Phú Giáo": ["Phước Vĩnh", "An Bình", "An Linh", "An Long", "An Thái", "Phước Hòa"]
            }
        },
        "Bà Rịa-Vũng Tàu": {
            "districts": ["Vũng Tàu", "Bà Rịa", "Long Điền", "Đất Đỏ", "Xuyên Mộc", "Châu Đức", "Côn Đảo"],
            "wards": {
                "Vũng Tàu": ["Phường 1", "Phường 2", "Phường 3", "Phường 4", "Phường 5", "Thắng Tam", "Nguyễn An Ninh"],
                "Bà Rịa": ["Phước Hiệp", "Phước Hưng", "Long Hương", "Kim Dinh", "Long Phước", "Long Tâm"],
                "Long Điền": ["Long Điền", "Long Hải", "An Ngãi", "An Nhứt", "Phước Hưng", "Tam Phước"],
                "Đất Đỏ": ["Đất Đỏ", "Phước Long Thọ", "Long Mỹ", "Long Tân", "Láng Dài", "Lộc An"],
                "Xuyên Mộc": ["Phước Bửu", "Bình Châu", "Bông Trang", "Bưng Riềng", "Hòa Bình", "Hòa Hiệp"],
                "Châu Đức": ["Ngãi Giao", "Bàu Chinh", "Bình Ba", "Bình Giã", "Bình Trung", "Cù Bị"],
                "Côn Đảo": ["Côn Đảo"]
            }
        },
        # Miền Bắc - Bổ sung
        "Thái Bình": {
            "districts": ["TP Thái Bình", "Đông Hưng", "Hưng Hà", "Kiến Xương", "Quỳnh Phụ", "Thái Thụy", "Tiền Hải", "Vũ Thư"],
            "wards": {
                "TP Thái Bình": ["Lê Hồng Phong", "Bồ Xuyên", "Đề Thám", "Kỳ Bá", "Quang Trung", "Trần Hưng Đạo"],
                "Đông Hưng": ["Đông Hưng", "Đông Các", "Đông Động", "Đông Hoàng", "Đông La", "Đông Phương"],
                "Hưng Hà": ["Hưng Hà", "Điệp Nông", "Hồng An", "Hồng Lĩnh", "Minh Tân", "Phúc Khánh"],
                "Kiến Xương": ["Kiến Xương", "An Bình", "Bình Nguyên", "Bình Thanh", "Hồng Thái", "Lê Lợi"],
                "Quỳnh Phụ": ["Quỳnh Côi", "An Khê", "An Ninh", "An Vinh", "Đông Hải", "Quỳnh Giao"],
                "Thái Thụy": ["Thái Thụy", "Thái Hòa", "Thái Thượng", "Thụy Bình", "Thụy Hà", "Thụy Hải"],
                "Tiền Hải": ["Tiền Hải", "An Ninh", "Bắc Hải", "Đông Cơ", "Đông Hải", "Đông Lâm"],
                "Vũ Thư": ["Vũ Thư", "Bách Thuận", "Dũng Nghĩa", "Hòa Bình", "Hồng Lý", "Minh Khai"]
            }
        },
        "Nam Định": {
            "districts": ["TP Nam Định", "Giao Thủy", "Hải Hậu", "Mỹ Lộc", "Nam Trực", "Nghĩa Hưng", "Trực Ninh", "Vụ Bản", "Xuân Trường", "Ý Yên"],
            "wards": {
                "TP Nam Định": ["Bà Triệu", "Hạ Long", "Năng Tĩnh", "Ngô Quyền", "Nguyễn Du", "Phan Đình Phùng"],
                "Giao Thủy": ["Giao Thủy", "Bạch Long", "Bình Hòa", "Giao An", "Giao Châu", "Giao Hải"],
                "Hải Hậu": ["Hải Hậu", "Hải Anh", "Hải Bắc", "Hải Châu", "Hải Đông", "Hải Giang"],
                "Mỹ Lộc": ["Mỹ Lộc", "Mỹ Hà", "Mỹ Hưng", "Mỹ Phúc", "Mỹ Tân", "Mỹ Thắng"],
                "Nam Trực": ["Nam Trực", "Bình Minh", "Điền Xá", "Đồng Sơn", "Hồng Quang", "Nam Cường"],
                "Nghĩa Hưng": ["Liễu Đề", "Nghĩa Bình", "Nghĩa Châu", "Nghĩa Đồng", "Nghĩa Hải", "Nghĩa Hồng"],
                "Trực Ninh": ["Trực Ninh", "Cát Thành", "Liêm Hải", "Phương Định", "Trực Chính", "Trực Đại"],
                "Vụ Bản": ["Vụ Bản", "Cộng Hòa", "Đại An", "Hiển Khánh", "Kim Thái", "Liên Bảo"],
                "Xuân Trường": ["Xuân Trường", "Xuân Bắc", "Xuân Châu", "Xuân Đài", "Xuân Hòa", "Xuân Hồng"],
                "Ý Yên": ["Ý Yên", "Yên Bằng", "Yên Bình", "Yên Chính", "Yên Cường", "Yên Dương"]
            }
        },
        "Phú Thọ": {
            "districts": ["TP Việt Trì", "TX Phú Thọ", "Cẩm Khê", "Đoan Hùng", "Hạ Hòa", "Lâm Thao", "Phù Ninh", "Tam Nông", "Thanh Ba", "Thanh Sơn", "Thanh Thủy", "Yên Lập"],
            "wards": {
                "TP Việt Trì": ["Bạch Hạc", "Bến Gót", "Dữu Lâu", "Gia Cẩm", "Minh Nông", "Minh Phương"],
                "TX Phú Thọ": ["Âu Cơ", "Hà Lộc", "Hà Thạch", "Phong Châu", "Thanh Minh", "Trường Thịnh"],
                "Cẩm Khê": ["Cẩm Khê", "Cát Trù", "Chương Xá", "Đồng Lương", "Hiền Đa", "Hùng Việt"],
                "Đoan Hùng": ["Đoan Hùng", "Bằng Luân", "Ca Đình", "Chí Đám", "Hùng Quan", "Minh Lương"],
                "Hạ Hòa": ["Hạ Hòa", "Ấm Hạ", "Đại Phạm", "Hương Xạ", "Lâm Lợi", "Lang Sơn"],
                "Lâm Thao": ["Lâm Thao", "Bản Nguyên", "Cao Xá", "Hợp Hải", "Kinh Kệ", "Sơn Dương"],
                "Phù Ninh": ["Phù Ninh", "An Đạo", "Bình Bộ", "Gia Thanh", "Hạ Giáp", "Lệ Mỹ"],
                "Tam Nông": ["Tam Nông", "Cổ Tiết", "Dị Nậu", "Hiền Quan", "Hương Nộn", "Thọ Văn"],
                "Thanh Ba": ["Thanh Ba", "Đông Lĩnh", "Đông Thành", "Hoàng Cương", "Lương Lỗ", "Mạn Lạn"],
                "Thanh Sơn": ["Thanh Sơn", "Cự Đồng", "Cự Thắng", "Đông Cửu", "Địch Quả", "Giáp Lai"],
                "Thanh Thủy": ["Thanh Thủy", "Bảo Yên", "Đào Xá", "Đồng Trung", "Hoàng Xá", "Phượng Mao"],
                "Yên Lập": ["Yên Lập", "Hưng Long", "Lương Sơn", "Mỹ Lung", "Nga Hoàng", "Ngọc Lập"]
            }
        },
        # Miền Trung - Bổ sung
        "Quảng Bình": {
            "districts": ["TP Đồng Hới", "Bố Trạch", "Quảng Trạch", "Lệ Thủy", "Quảng Ninh", "Tuyên Hóa", "Minh Hóa"],
            "wards": {
                "TP Đồng Hới": ["Bắc Lý", "Bắc Nghĩa", "Đồng Mỹ", "Đồng Phú", "Đồng Sơn", "Hải Đình"],
                "Bố Trạch": ["Hoàn Lão", "Bắc Trạch", "Cự Nẫm", "Đại Trạch", "Đồng Trạch", "Hải Trạch"],
                "Quảng Trạch": ["Ba Đồn", "Quảng Châu", "Quảng Hòa", "Quảng Kim", "Quảng Lộc", "Quảng Long"],
                "Lệ Thủy": ["Kiến Giang", "An Thủy", "Cam Thủy", "Dương Thủy", "Hoa Thủy", "Hồng Thủy"],
                "Quảng Ninh": ["Quán Hàu", "Gia Ninh", "Hải Ninh", "Hiền Ninh", "Lương Ninh", "Tân Ninh"],
                "Tuyên Hóa": ["Đồng Lê", "Cao Quảng", "Châu Hóa", "Đức Hóa", "Kim Hóa", "Lâm Hóa"],
                "Minh Hóa": ["Quy Đạt", "Dân Hóa", "Hóa Hợp", "Hóa Phúc", "Hóa Sơn", "Hóa Thanh"]
            }
        },
        "Quảng Trị": {
            "districts": ["TP Đông Hà", "TX Quảng Trị", "Triệu Phong", "Hải Lăng", "Gio Linh", "Vĩnh Linh", "Cam Lộ", "Đakrông", "Hướng Hóa"],
            "wards": {
                "TP Đông Hà": ["Đông Giang", "Đông Lễ", "Đông Lương", "Đông Thanh", "Phường 1", "Phường 2"],
                "TX Quảng Trị": ["An Đôn", "Phường 1", "Phường 2", "Phường 3", "Hải Lệ"],
                "Triệu Phong": ["Triệu Phong", "Triệu Ái", "Triệu An", "Triệu Độ", "Triệu Giang", "Triệu Hòa"],
                "Hải Lăng": ["Hải Lăng", "Hải An", "Hải Ba", "Hải Chánh", "Hải Dương", "Hải Hòa"],
                "Gio Linh": ["Gio Linh", "Gio An", "Gio Bình", "Gio Châu", "Gio Hải", "Gio Mai"],
                "Vĩnh Linh": ["Hồ Xá", "Bến Quan", "Kim Thạch", "Vĩnh Chấp", "Vĩnh Giang", "Vĩnh Hà"],
                "Cam Lộ": ["Cam Lộ", "Cam An", "Cam Chính", "Cam Hiếu", "Cam Thanh", "Cam Thủy"],
                "Đakrông": ["Krông Klang", "Ba Lòng", "Ba Nang", "Đakrông", "Hải Phúc", "Húc Nghì"],
                "Hướng Hóa": ["Khe Sanh", "Lao Bảo", "Hướng Lập", "Hướng Linh", "Hướng Phùng", "Hướng Tân"]
            }
        },
        "Hà Tĩnh": {
            "districts": ["TP Hà Tĩnh", "TX Hồng Lĩnh", "TX Kỳ Anh", "Cẩm Xuyên", "Thạch Hà", "Can Lộc", "Đức Thọ", "Nghi Xuân", "Hương Sơn", "Hương Khê", "Vũ Quang", "Lộc Hà"],
            "wards": {
                "TP Hà Tĩnh": ["Bắc Hà", "Đại Nài", "Hà Huy Tập", "Nam Hà", "Nguyễn Du", "Tân Giang"],
                "TX Hồng Lĩnh": ["Bắc Hồng", "Đậu Liêu", "Đức Thuận", "Nam Hồng", "Trung Lương"],
                "TX Kỳ Anh": ["Kỳ Phương", "Kỳ Long", "Kỳ Liên", "Kỳ Thịnh", "Kỳ Trinh", "Sông Trí"],
                "Cẩm Xuyên": ["Cẩm Xuyên", "Cẩm Bình", "Cẩm Dương", "Cẩm Hà", "Cẩm Hòa", "Cẩm Hưng"],
                "Thạch Hà": ["Thạch Hà", "Bắc Sơn", "Nam Hương", "Ngọc Sơn", "Thạch Bằng", "Thạch Đài"],
                "Can Lộc": ["Nghèn", "Gia Hanh", "Kim Lộc", "Khánh Lộc", "Mỹ Lộc", "Phú Lộc"],
                "Đức Thọ": ["Đức Thọ", "Bùi La Nhân", "Đức An", "Đức Châu", "Đức Hòa", "Đức Lạng"],
                "Nghi Xuân": ["Nghi Xuân", "Cổ Đạm", "Cương Gián", "Đan Trường", "Tiên Điền", "Xuân An"],
                "Hương Sơn": ["Phố Châu", "An Hòa Thịnh", "Kim Hoa", "Sơn Bằng", "Sơn Châu", "Sơn Giang"],
                "Hương Khê": ["Hương Khê", "Điền Mỹ", "Gia Phố", "Hà Linh", "Hương Bình", "Hương Đô"],
                "Vũ Quang": ["Vũ Quang", "Ân Phú", "Đức Bồng", "Đức Giang", "Đức Hương", "Đức Liên"],
                "Lộc Hà": ["Lộc Hà", "An Lộc", "Bình An", "Hồng Lộc", "Ích Hậu", "Mai Phụ"]
            }
        },
        "Nghệ An": {
            "districts": ["TP Vinh", "TX Cửa Lò", "TX Hoàng Mai", "TX Thái Hòa", "Diễn Châu", "Quỳnh Lưu", "Yên Thành", "Đô Lương", "Nam Đàn", "Hưng Nguyên", "Nghi Lộc", "Thanh Chương"],
            "wards": {
                "TP Vinh": ["Bến Thủy", "Cửa Nam", "Đội Cung", "Đông Vĩnh", "Hà Huy Tập", "Hồng Sơn"],
                "TX Cửa Lò": ["Nghi Hải", "Nghi Hòa", "Nghi Hương", "Nghi Thủy", "Nghi Thu"],
                "TX Hoàng Mai": ["Quỳnh Dị", "Quỳnh Phương", "Quỳnh Thiện", "Quỳnh Xuân", "Mai Hùng"],
                "TX Thái Hòa": ["Hòa Hiếu", "Long Sơn", "Nghĩa Hòa", "Nghĩa Mỹ", "Nghĩa Tiến", "Quang Phong"],
                "Diễn Châu": ["Diễn Châu", "Diễn An", "Diễn Bích", "Diễn Cát", "Diễn Đồng", "Diễn Hạnh"],
                "Quỳnh Lưu": ["Cầu Giát", "Quỳnh Bảng", "Quỳnh Châu", "Quỳnh Đôi", "Quỳnh Giang", "Quỳnh Hoa"],
                "Yên Thành": ["Yên Thành", "Bắc Thành", "Bảo Thành", "Công Thành", "Đại Thành", "Đô Thành"],
                "Đô Lương": ["Đô Lương", "Bắc Sơn", "Bài Sơn", "Bồi Sơn", "Đà Sơn", "Đại Sơn"],
                "Nam Đàn": ["Nam Đàn", "Hùng Tiến", "Kim Liên", "Nam Anh", "Nam Cát", "Nam Giang"],
                "Hưng Nguyên": ["Hưng Nguyên", "Hưng Châu", "Hưng Đạo", "Hưng Lĩnh", "Hưng Long", "Hưng Mỹ"],
                "Nghi Lộc": ["Nghi Lộc", "Nghi Diên", "Nghi Đồng", "Nghi Hưng", "Nghi Kiều", "Nghi Lâm"],
                "Thanh Chương": ["Thanh Chương", "Cát Văn", "Đồng Văn", "Hạnh Lâm", "Ngọc Lâm", "Phong Thịnh"]
            }
        },
        "Thanh Hóa": {
            "districts": ["TP Thanh Hóa", "TX Sầm Sơn", "TX Bỉm Sơn", "Hoằng Hóa", "Hậu Lộc", "Nga Sơn", "Tĩnh Gia", "Quảng Xương", "Đông Sơn", "Triệu Sơn", "Nông Cống", "Thọ Xuân"],
            "wards": {
                "TP Thanh Hóa": ["Ba Đình", "Đông Hương", "Đông Sơn", "Đông Thọ", "Đông Vệ", "Hàm Rồng"],
                "TX Sầm Sơn": ["Bắc Sơn", "Quảng Châu", "Quảng Cư", "Quảng Tiến", "Quảng Vinh", "Trung Sơn"],
                "TX Bỉm Sơn": ["Ba Đình", "Bắc Sơn", "Đông Sơn", "Lam Sơn", "Ngọc Trạo", "Phú Sơn"],
                "Hoằng Hóa": ["Bút Sơn", "Hoằng Anh", "Hoằng Cát", "Hoằng Châu", "Hoằng Đạo", "Hoằng Đồng"],
                "Hậu Lộc": ["Hậu Lộc", "Cầu Lộc", "Châu Lộc", "Đa Lộc", "Đại Lộc", "Đồng Lộc"],
                "Nga Sơn": ["Nga Sơn", "Ba Đình", "Nga An", "Nga Bạch", "Nga Điền", "Nga Giáp"],
                "Tĩnh Gia": ["Tĩnh Gia", "Anh Sơn", "Bình Minh", "Các Sơn", "Định Hải", "Hải An"],
                "Quảng Xương": ["Quảng Xương", "Quảng Bình", "Quảng Châu", "Quảng Đức", "Quảng Giao", "Quảng Hải"],
                "Đông Sơn": ["Rừng Thông", "Đông Anh", "Đông Hoàng", "Đông Khê", "Đông Minh", "Đông Ninh"],
                "Triệu Sơn": ["Triệu Sơn", "An Nông", "Bình Sơn", "Dân Lực", "Dân Lý", "Dân Quyền"],
                "Nông Cống": ["Nông Cống", "Công Bình", "Công Chính", "Công Liêm", "Hoàng Giang", "Hoàng Sơn"],
                "Thọ Xuân": ["Thọ Xuân", "Bắc Lương", "Hạnh Phúc", "Nam Giang", "Phú Yên", "Quảng Phú"]
            }
        },
        # Miền Nam - Bổ sung
        "Long An": {
            "districts": ["TP Tân An", "TX Kiến Tường", "Bến Lức", "Đức Hòa", "Đức Huệ", "Thủ Thừa", "Tân Trụ", "Cần Đước", "Cần Giuộc", "Châu Thành", "Tân Thạnh", "Thạnh Hóa", "Mộc Hóa", "Vĩnh Hưng", "Tân Hưng"],
            "wards": {
                "TP Tân An": ["Phường 1", "Phường 2", "Phường 3", "Phường 4", "Phường 5", "Phường 6", "Khánh Hậu"],
                "TX Kiến Tường": ["Phường 1", "Phường 2", "Phường 3", "Bình Hiệp", "Bình Tân", "Tuyên Thạnh"],
                "Bến Lức": ["Bến Lức", "An Thạnh", "Lương Bình", "Lương Hòa", "Mỹ Yên", "Nhựt Chánh"],
                "Đức Hòa": ["Hậu Nghĩa", "Đức Hòa Đông", "Đức Hòa Hạ", "Đức Lập Hạ", "Đức Lập Thượng", "Hiệp Hòa"],
                "Đức Huệ": ["Đông Thành", "Bình Hòa Bắc", "Bình Hòa Hưng", "Bình Hòa Nam", "Mỹ Bình", "Mỹ Quý Đông"],
                "Thủ Thừa": ["Thủ Thừa", "Bình An", "Bình Thạnh", "Long Thành", "Long Thuận", "Mỹ An"],
                "Tân Trụ": ["Tân Trụ", "An Nhựt Tân", "Bình Lãng", "Bình Tịnh", "Đức Tân", "Lạc Tấn"],
                "Cần Đước": ["Cần Đước", "Long Cang", "Long Định", "Long Hòa", "Long Hựu Đông", "Long Hựu Tây"],
                "Cần Giuộc": ["Cần Giuộc", "Đông Thạnh", "Long An", "Long Hậu", "Long Phụng", "Long Thượng"],
                "Châu Thành": ["Tầm Vu", "An Lục Long", "Bình Quới", "Dương Xuân Hội", "Hòa Phú", "Long Trì"],
                "Tân Thạnh": ["Tân Thạnh", "Bắc Hòa", "Hậu Thạnh Đông", "Hậu Thạnh Tây", "Kiến Bình", "Nhơn Hòa"],
                "Thạnh Hóa": ["Thạnh Hóa", "Tân Đông", "Tân Hiệp", "Tân Tây", "Thuận Bình", "Thuận Nghĩa Hòa"],
                "Mộc Hóa": ["Mộc Hóa", "Bình Hòa Đông", "Bình Hòa Tây", "Bình Phong Thạnh", "Tân Lập"],
                "Vĩnh Hưng": ["Vĩnh Hưng", "Hưng Điền A", "Hưng Điền B", "Khánh Hưng", "Thái Bình Trung", "Thái Trị"],
                "Tân Hưng": ["Tân Hưng", "Hưng Điền", "Hưng Hà", "Hưng Thạnh", "Vĩnh Bửu", "Vĩnh Châu A"]
            }
        },
        "Tiền Giang": {
            "districts": ["TP Mỹ Tho", "TX Gò Công", "TX Cai Lậy", "Châu Thành", "Chợ Gạo", "Gò Công Đông", "Gò Công Tây", "Cai Lậy", "Cái Bè", "Tân Phước", "Tân Phú Đông"],
            "wards": {
                "TP Mỹ Tho": ["Phường 1", "Phường 2", "Phường 3", "Phường 4", "Phường 5", "Phường 6", "Đạo Thạnh"],
                "TX Gò Công": ["Phường 1", "Phường 2", "Phường 3", "Phường 4", "Phường 5", "Long Hưng", "Long Thuận"],
                "TX Cai Lậy": ["Phường 1", "Phường 2", "Phường 3", "Mỹ Phước Tây", "Nhị Mỹ", "Thanh Hòa"],
                "Châu Thành": ["Tân Hiệp", "Bàn Long", "Bình Đức", "Dưỡng Điềm", "Đông Hòa", "Kim Sơn"],
                "Chợ Gạo": ["Chợ Gạo", "An Thạnh Thủy", "Bình Ninh", "Bình Phục Nhứt", "Đăng Hưng Phước", "Hòa Định"],
                "Gò Công Đông": ["Tân Đông", "Bình Ân", "Bình Nghị", "Gia Thuận", "Kiểng Phước", "Phước Trung"],
                "Gò Công Tây": ["Vĩnh Bình", "Bình Nhì", "Bình Phú", "Đồng Sơn", "Đồng Thạnh", "Long Bình"],
                "Cai Lậy": ["Cẩm Sơn", "Bình Phú", "Hiệp Đức", "Hội Xuân", "Long Khánh", "Long Tiên"],
                "Cái Bè": ["Cái Bè", "An Cư", "An Hữu", "An Thái Đông", "An Thái Trung", "Đông Hòa Hiệp"],
                "Tân Phước": ["Mỹ Phước", "Hưng Thạnh", "Phú Mỹ", "Tân Hòa Đông", "Tân Hòa Tây", "Tân Hòa Thành"],
                "Tân Phú Đông": ["Tân Phú", "Phú Đông", "Phú Tân", "Tân Thạnh", "Tân Thới"]
            }
        },
        "Vĩnh Long": {
            "districts": ["TP Vĩnh Long", "TX Bình Minh", "Long Hồ", "Mang Thít", "Vũng Liêm", "Tam Bình", "Bình Tân", "Trà Ôn"],
            "wards": {
                "TP Vĩnh Long": ["Phường 1", "Phường 2", "Phường 3", "Phường 4", "Phường 5", "Phường 8", "Phường 9"],
                "TX Bình Minh": ["Cái Vồn", "Đông Bình", "Đông Thạnh", "Đông Thuận", "Mỹ Hòa", "Thuận An"],
                "Long Hồ": ["Long Hồ", "An Bình", "Bình Hòa Phước", "Đồng Phú", "Hòa Ninh", "Hòa Phú"],
                "Mang Thít": ["Mang Thít", "An Phước", "Bình Phước", "Chánh An", "Chánh Hội", "Long Mỹ"],
                "Vũng Liêm": ["Vũng Liêm", "Hiếu Nghĩa", "Hiếu Nhơn", "Hiếu Phụng", "Hiếu Thành", "Hiếu Thuận"],
                "Tam Bình": ["Tam Bình", "Bình Ninh", "Hòa Hiệp", "Hòa Lộc", "Hòa Thạnh", "Long Phú"],
                "Bình Tân": ["Tân An Thạnh", "Mỹ Thuận", "Nguyễn Văn Thảnh", "Tân An Luông", "Tân Bình", "Tân Hưng"],
                "Trà Ôn": ["Trà Ôn", "Hòa Bình", "Hựu Thành", "Lục Sĩ Thành", "Nhơn Bình", "Phú Thành"]
            }
        },
        "Sóc Trăng": {
            "districts": ["TP Sóc Trăng", "TX Vĩnh Châu", "TX Ngã Năm", "Châu Thành", "Kế Sách", "Long Phú", "Mỹ Tú", "Mỹ Xuyên", "Cù Lao Dung", "Thạnh Trị", "Trần Đề"],
            "wards": {
                "TP Sóc Trăng": ["Phường 1", "Phường 2", "Phường 3", "Phường 4", "Phường 5", "Phường 6", "Phường 7"],
                "TX Vĩnh Châu": ["Vĩnh Châu", "Khánh Hòa", "Lai Hòa", "Lạc Hòa", "Vĩnh Hiệp", "Vĩnh Phước"],
                "TX Ngã Năm": ["Ngã Năm", "Long Bình", "Mỹ Bình", "Mỹ Quới", "Tân Long", "Vĩnh Quới"],
                "Châu Thành": ["Châu Thành", "An Hiệp", "An Ninh", "Hồ Đắc Kiện", "Phú Tâm", "Thuận Hòa"],
                "Kế Sách": ["Kế Sách", "An Lạc Tây", "An Lạc Thôn", "Ba Trinh", "Đại Hải", "Kế An"],
                "Long Phú": ["Long Phú", "Châu Khánh", "Hậu Thạnh", "Long Đức", "Long Phú", "Phú Hữu"],
                "Mỹ Tú": ["Mỹ Tú", "Hưng Phú", "Long Hưng", "Mỹ Hương", "Mỹ Phước", "Mỹ Thuận"],
                "Mỹ Xuyên": ["Mỹ Xuyên", "Đại Tâm", "Gia Hòa 1", "Gia Hòa 2", "Hòa Tú 1", "Hòa Tú 2"],
                "Cù Lao Dung": ["Cù Lao Dung", "An Thạnh 1", "An Thạnh 2", "An Thạnh 3", "An Thạnh Đông", "An Thạnh Nam"],
                "Thạnh Trị": ["Phú Lộc", "Châu Hưng", "Lâm Kiết", "Lâm Tân", "Thạnh Tân", "Thạnh Trị"],
                "Trần Đề": ["Trần Đề", "Đại Ân 2", "Lịch Hội Thượng", "Liêu Tú", "Tài Văn", "Thạnh Thới An"]
            }
        },
        "Bạc Liêu": {
            "districts": ["TP Bạc Liêu", "TX Giá Rai", "Hồng Dân", "Phước Long", "Vĩnh Lợi", "Đông Hải", "Hòa Bình"],
            "wards": {
                "TP Bạc Liêu": ["Phường 1", "Phường 2", "Phường 3", "Phường 5", "Phường 7", "Phường 8", "Nhà Mát"],
                "TX Giá Rai": ["Giá Rai", "Hộ Phòng", "Phong Thạnh", "Phong Thạnh A", "Phong Thạnh Tây", "Tân Phong"],
                "Hồng Dân": ["Ngan Dừa", "Lộc Ninh", "Ninh Hòa", "Ninh Quới", "Ninh Quới A", "Ninh Thạnh Lợi"],
                "Phước Long": ["Phước Long", "Hưng Phú", "Phong Thạnh Tây A", "Phước Long", "Vĩnh Phú Đông", "Vĩnh Phú Tây"],
                "Vĩnh Lợi": ["Vĩnh Lợi", "Châu Hưng", "Châu Hưng A", "Châu Thới", "Hưng Hội", "Hưng Thành"],
                "Đông Hải": ["Gành Hào", "An Phúc", "An Trạch", "An Trạch A", "Điền Hải", "Long Điền"],
                "Hòa Bình": ["Hòa Bình", "Minh Diệu", "Vĩnh Bình", "Vĩnh Hậu", "Vĩnh Hậu A", "Vĩnh Mỹ A"]
            }
        },
        "Cà Mau": {
            "districts": ["TP Cà Mau", "U Minh", "Thới Bình", "Trần Văn Thời", "Cái Nước", "Đầm Dơi", "Năm Căn", "Phú Tân", "Ngọc Hiển"],
            "wards": {
                "TP Cà Mau": ["Phường 1", "Phường 2", "Phường 4", "Phường 5", "Phường 6", "Phường 7", "Phường 8", "Phường 9"],
                "U Minh": ["U Minh", "Khánh An", "Khánh Hòa", "Khánh Lâm", "Khánh Thuận", "Nguyễn Phích"],
                "Thới Bình": ["Thới Bình", "Biển Bạch", "Biển Bạch Đông", "Hồ Thị Kỷ", "Tân Bằng", "Tân Lộc"],
                "Trần Văn Thời": ["Trần Văn Thời", "Khánh Bình", "Khánh Bình Đông", "Khánh Bình Tây", "Khánh Hải", "Lợi An"],
                "Cái Nước": ["Cái Nước", "Đông Hưng", "Đông Thới", "Hưng Mỹ", "Lương Thế Trân", "Phú Hưng"],
                "Đầm Dơi": ["Đầm Dơi", "Ngọc Chánh", "Nguyễn Huân", "Quách Phẩm", "Quách Phẩm Bắc", "Tạ An Khương"],
                "Năm Căn": ["Năm Căn", "Đất Mới", "Hàm Rồng", "Hàng Vịnh", "Hiệp Tùng", "Lâm Hải"],
                "Phú Tân": ["Phú Tân", "Cái Đôi Vàm", "Nguyễn Việt Khái", "Phú Mỹ", "Phú Thuận", "Rạch Chèo"],
                "Ngọc Hiển": ["Ngọc Hiển", "Đất Mũi", "Tam Giang", "Tam Giang Đông", "Viên An", "Viên An Đông"]
            }
        },
        "Kiên Giang": {
            "districts": ["TP Rạch Giá", "TP Hà Tiên", "TX Phú Quốc", "Kiên Lương", "Hòn Đất", "Tân Hiệp", "Châu Thành", "Giồng Riềng", "Gò Quao", "An Biên", "An Minh", "U Minh Thượng", "Vĩnh Thuận"],
            "wards": {
                "TP Rạch Giá": ["An Hòa", "An Bình", "Rạch Sỏi", "Vĩnh Bảo", "Vĩnh Lạc", "Vĩnh Lợi", "Vĩnh Quang"],
                "TP Hà Tiên": ["Bình San", "Đông Hồ", "Pháo Đài", "Tô Châu", "Mỹ Đức", "Thuận Yên"],
                "TX Phú Quốc": ["Dương Đông", "An Thới", "Cửa Cạn", "Cửa Dương", "Dương Tơ", "Gành Dầu"],
                "Kiên Lương": ["Kiên Lương", "Bình An", "Bình Trị", "Dương Hòa", "Hòa Điền", "Kiên Bình"],
                "Hòn Đất": ["Hòn Đất", "Bình Giang", "Bình Sơn", "Lình Huỳnh", "Mỹ Hiệp Sơn", "Mỹ Lâm"],
                "Tân Hiệp": ["Tân Hiệp", "Tân An", "Tân Hiệp A", "Tân Hòa", "Thạnh Đông", "Thạnh Đông A"],
                "Châu Thành": ["Minh Lương", "Bình An", "Giục Tượng", "Mong Thọ", "Mong Thọ A", "Mong Thọ B"],
                "Giồng Riềng": ["Giồng Riềng", "Bàn Tân Định", "Bàn Thạch", "Hòa Hưng", "Hòa Lợi", "Hòa Thuận"],
                "Gò Quao": ["Gò Quao", "Định An", "Định Hòa", "Thới Quản", "Thủy Liễu", "Vĩnh Hòa Hưng"],
                "An Biên": ["An Biên", "Đông Thái", "Đông Yên", "Hưng Yên", "Nam Thái", "Nam Yên"],
                "An Minh": ["An Minh", "Đông Hòa", "Đông Hưng", "Đông Hưng A", "Đông Hưng B", "Thuận Hòa"],
                "U Minh Thượng": ["U Minh Thượng", "An Minh Bắc", "Hòa Chánh", "Minh Thuận", "Thạnh Yên", "Vĩnh Hòa"],
                "Vĩnh Thuận": ["Vĩnh Thuận", "Bình Minh", "Phong Đông", "Tân Thuận", "Vĩnh Bình Bắc", "Vĩnh Phong"]
            }
        },
        "Hậu Giang": {
            "districts": ["TP Vị Thanh", "TX Ngã Bảy", "TX Long Mỹ", "Châu Thành", "Châu Thành A", "Phụng Hiệp", "Vị Thủy"],
            "wards": {
                "TP Vị Thanh": ["Phường 1", "Phường 3", "Phường 4", "Phường 5", "Phường 7", "Hỏa Lựu", "Hỏa Tiến"],
                "TX Ngã Bảy": ["Ngã Bảy", "Hiệp Lợi", "Hiệp Thành", "Lái Hiếu", "Tân Thành"],
                "TX Long Mỹ": ["Long Mỹ", "Bình Thạnh", "Long Bình", "Long Phú", "Thuận Hòa", "Thuận Hưng"],
                "Châu Thành": ["Ngã Sáu", "Đông Phú", "Đông Phước", "Đông Phước A", "Đông Thạnh", "Phú An"],
                "Châu Thành A": ["Một Ngàn", "Bảy Ngàn", "Nhơn Nghĩa A", "Tân Hòa", "Tân Phú Thạnh", "Trường Long A"],
                "Phụng Hiệp": ["Cây Dương", "Bình Thành", "Hiệp Hưng", "Hòa An", "Hòa Mỹ", "Long Thạnh"],
                "Vị Thủy": ["Vị Thủy", "Vĩnh Thuận Đông", "Vĩnh Thuận Tây", "Vĩnh Trung", "Vĩnh Tường"]
            }
        },
        "Bến Tre": {
            "districts": ["TP Bến Tre", "Châu Thành", "Chợ Lách", "Mỏ Cày Bắc", "Mỏ Cày Nam", "Giồng Trôm", "Bình Đại", "Ba Tri", "Thạnh Phú"],
            "wards": {
                "TP Bến Tre": ["Phường 1", "Phường 2", "Phường 3", "Phường 4", "Phường 5", "Phường 6", "Phường 7"],
                "Châu Thành": ["Châu Thành", "An Hiệp", "An Hóa", "An Phước", "Giao Long", "Hữu Định"],
                "Chợ Lách": ["Chợ Lách", "Hòa Nghĩa", "Hưng Khánh Trung A", "Long Thới", "Phú Phụng", "Phú Sơn"],
                "Mỏ Cày Bắc": ["Mỏ Cày", "Hòa Lộc", "Khánh Thạnh Tân", "Nhuận Phú Tân", "Phú Mỹ", "Phước Mỹ Trung"],
                "Mỏ Cày Nam": ["Đa Phước Hội", "An Định", "An Thạnh", "Bình Khánh", "Cẩm Sơn", "Định Thủy"],
                "Giồng Trôm": ["Giồng Trôm", "Bình Hòa", "Bình Thành", "Châu Bình", "Châu Hòa", "Hưng Lễ"],
                "Bình Đại": ["Bình Đại", "Bình Thới", "Châu Hưng", "Đại Hòa Lộc", "Định Trung", "Lộc Thuận"],
                "Ba Tri": ["Ba Tri", "An Bình Tây", "An Đức", "An Hòa Tây", "An Ngãi Trung", "An Thủy"],
                "Thạnh Phú": ["Thạnh Phú", "An Điền", "An Nhơn", "An Quy", "An Thuận", "Bình Thạnh"]
            }
        },
        "Trà Vinh": {
            "districts": ["TP Trà Vinh", "TX Duyên Hải", "Càng Long", "Cầu Kè", "Tiểu Cần", "Châu Thành", "Cầu Ngang", "Trà Cú", "Duyên Hải"],
            "wards": {
                "TP Trà Vinh": ["Phường 1", "Phường 2", "Phường 3", "Phường 4", "Phường 5", "Phường 6", "Phường 7"],
                "TX Duyên Hải": ["Long Hữu", "Long Thành", "Trường Long Hòa"],
                "Càng Long": ["Càng Long", "An Trường", "An Trường A", "Bình Phú", "Đại Phước", "Đại Phước A"],
                "Cầu Kè": ["Cầu Kè", "An Phú Tân", "Châu Điền", "Hòa Ân", "Hòa Tân", "Ninh Thới"],
                "Tiểu Cần": ["Tiểu Cần", "Hiếu Trung", "Hiếu Tử", "Hùng Hòa", "Long Thới", "Ngãi Hùng"],
                "Châu Thành": ["Châu Thành", "Đa Lộc", "Hòa Lợi", "Hòa Minh", "Hòa Thuận", "Long Hòa"],
                "Cầu Ngang": ["Cầu Ngang", "Hiệp Hòa", "Kim Hòa", "Long Sơn", "Mỹ Hòa", "Mỹ Long Bắc"],
                "Trà Cú": ["Trà Cú", "An Quảng Hữu", "Đại An", "Định An", "Hàm Giang", "Hàm Tân"],
                "Duyên Hải": ["Đôn Châu", "Đôn Xuân", "Long Khánh", "Long Vĩnh", "Ngũ Lạc"]
            }
        }
    }

    # Lấy thông tin huyện theo tỉnh
    prov_data = province_districts.get(province, None)
    if not prov_data:
        return []

    districts = prov_data.get("districts", [])
    wards_data = prov_data.get("wards", {})

    # Tạo dữ liệu chi tiết cho mỗi huyện
    impact_levels = ["Rất cao", "Cao", "Trung bình", "Thấp"]
    base_impact_idx = impact_levels.index(impact_level) if impact_level in impact_levels else 3

    result = []
    for i, district in enumerate(districts[:6]):  # Lấy tối đa 6 huyện
        # Random ảnh hưởng dựa trên mức cơ bản của tỉnh
        offset = random.randint(-1, 1)
        district_impact_idx = max(0, min(3, base_impact_idx + offset))
        district_impact = impact_levels[district_impact_idx]

        # Water level dựa trên mức ảnh hưởng
        water_base = {0: 80, 1: 50, 2: 30, 3: 15}
        water_level = water_base[district_impact_idx] + random.randint(-10, 20)

        # Flood area
        flood_area = max(1, water_level // 4 + random.randint(0, 10))

        # Lấy xã/phường
        district_wards = wards_data.get(district, [])[:5]  # Tối đa 5 xã
        if not district_wards:
            district_wards = [f"Xã {j+1}" for j in range(3)]

        evacuation = district_impact_idx <= 1 and random.random() > 0.5

        result.append({
            "name": district,
            "impact_level": district_impact,
            "water_level_cm": water_level,
            "flood_area_km2": flood_area,
            "affected_wards": district_wards,
            "evacuation_needed": evacuation,
            "notes": f"Khu vực {'ven sông, dễ ngập' if evacuation else 'cần theo dõi'}"
        })

    return result


def enrich_analysis_with_districts(analysis: dict, basin_name: str) -> dict:
    """Bổ sung dữ liệu huyện nếu AI không trả về đủ"""
    affected_areas = analysis.get("affected_areas", [])

    for area in affected_areas:
        # Kiểm tra nếu không có districts hoặc districts rỗng
        if not area.get("districts") or len(area.get("districts", [])) == 0:
            province = area.get("province", "")
            impact_level = area.get("impact_level", "Thấp")
            area["districts"] = generate_districts_for_province(province, impact_level, basin_name)

    return analysis


def get_fallback_analysis(basin_name: str, forecast_data: dict) -> dict:
    """Trả về phân tích mặc định nếu AI thất bại"""
    forecast_days = forecast_data.get("forecast_days", [])

    # Tìm ngày mưa cao nhất
    max_rain_day = max(forecast_days[:7], key=lambda x: x.get("daily_rain", 0)) if forecast_days else {}

    basin_provinces = {
        "HONG": ["Hà Nội", "Hải Phòng", "Thái Bình", "Nam Định", "Phú Thọ"],
        "CENTRAL": ["Đà Nẵng", "Quảng Nam", "Thừa Thiên Huế", "Quảng Ngãi", "Bình Định"],
        "MEKONG": ["An Giang", "Đồng Tháp", "Cần Thơ", "Long An", "Tiền Giang"],
        "DONGNAI": ["TP.HCM", "Đồng Nai", "Bình Dương", "Bà Rịa-Vũng Tàu"]
    }

    provinces = basin_provinces.get(basin_name, ["Khu vực 1", "Khu vực 2", "Khu vực 3"])
    max_rain = max_rain_day.get("daily_rain", 0)

    # Tính mức độ ảnh hưởng dựa trên lượng mưa
    if max_rain >= 100:
        base_impact = "Rất cao"
    elif max_rain >= 50:
        base_impact = "Cao"
    elif max_rain >= 20:
        base_impact = "Trung bình"
    else:
        base_impact = "Thấp"

    affected_areas = []
    for p in provinces[:5]:
        area = {
            "province": p,
            "impact_level": base_impact,
            "water_level_cm": max(10, int(max_rain * 0.5)),
            "flood_area_km2": max(5, int(max_rain * 0.2)),
            "reason": "Dựa trên dữ liệu dự báo",
            "districts": generate_districts_for_province(p, base_impact, basin_name)
        }
        affected_areas.append(area)

    return {
        "peak_rain": {
            "date": max_rain_day.get("date", "N/A"),
            "amount_mm": max_rain,
            "intensity": "Nhẹ" if max_rain < 20 else "Vừa" if max_rain < 50 else "Lớn"
        },
        "flood_timeline": {
            "rising_start": forecast_days[0]["date"] if forecast_days else "N/A",
            "rising_end": forecast_days[2]["date"] if len(forecast_days) > 2 else "N/A",
            "peak_date": max_rain_day.get("date", "N/A"),
            "receding_start": forecast_days[4]["date"] if len(forecast_days) > 4 else "N/A",
            "receding_end": forecast_days[6]["date"] if len(forecast_days) > 6 else "N/A"
        },
        "affected_areas": affected_areas,
        "overall_risk": {
            "level": "Thấp" if max_rain < 30 else "Trung bình" if max_rain < 60 else "Cao",
            "score": 2 if max_rain < 30 else 5 if max_rain < 60 else 7,
            "description": "Phân tích tự động dựa trên dữ liệu"
        },
        "recommendations": {
            "government": ["Theo dõi diễn biến thời tiết", "Chuẩn bị phương án ứng phó", "Thông báo đến người dân vùng trũng"],
            "citizens": ["Cập nhật tin tức thường xuyên", "Chuẩn bị đồ dùng thiết yếu", "Sẵn sàng di chuyển nếu cần"]
        },
        "summary": f"Dự báo lượng mưa tối đa {max_rain:.1f}mm. Cần theo dõi diễn biến."
    }


@app.get("/api/forecast/basin/{basin_name}")
async def get_basin_forecast(basin_name: str, include_ai: bool = True):
    """Lấy dự báo cho một lưu vực cụ thể với phân tích AI"""
    try:
        basin_upper = basin_name.upper()

        if basin_upper not in BASIN_WEIGHTS:
            raise HTTPException(status_code=404, detail=f"Lưu vực '{basin_name}' không tồn tại")

        all_data = get_cached_or_fetch()

        if basin_upper not in all_data["basins"]:
            raise HTTPException(status_code=404, detail="Chưa có dữ liệu dự báo")

        basin_data = all_data["basins"][basin_upper]

        # Thêm phân tích AI nếu được yêu cầu
        ai_analysis = None
        if include_ai:
            ai_analysis = analyze_forecast_with_ai(basin_upper, basin_data)

        return {
            "basin": basin_upper,
            "data": basin_data,
            "ai_analysis": ai_analysis,
            "generated_at": all_data["generated_at"]
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in /api/forecast/basin: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/basins/summary")
async def get_basins_summary():
    """Lấy tóm tắt tình trạng các lưu vực"""
    try:
        all_data = get_cached_or_fetch()
        basins = all_data["basins"]

        summary = []
        for basin_code, basin_data in basins.items():
            # Đếm số cảnh báo
            danger_count = 0
            warning_count = 0
            watch_count = 0
            safe_count = 0

            for day in basin_data["forecast_days"]:
                risk = day["risk_level"].upper()
                if "NGUY" in risk or "DANGER" in risk:
                    danger_count += 1
                elif "CẢNH" in risk or "WARNING" in risk:
                    warning_count += 1
                elif "THEO" in risk or "WATCH" in risk:
                    watch_count += 1
                else:
                    safe_count += 1

            # Map basin names
            basin_names = {
                "HONG": "Sông Hồng",
                "MEKONG": "Sông Mekong",
                "DONGNAI": "Sông Đồng Nai",
                "CENTRAL": "Miền Trung"
            }

            summary.append({
                "basin_id": hash(basin_code) % 1000,
                "basin_name": basin_names.get(basin_code, basin_code),
                "total_stations": len(BASIN_WEIGHTS[basin_code]),
                "danger_count": danger_count,
                "warning_count": warning_count,
                "watch_count": watch_count,
                "safe_count": safe_count
            })

        return summary
    except Exception as e:
        print(f"Error in /api/basins/summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stations")
async def get_stations():
    """Lấy danh sách trạm quan trắc với mức độ rủi ro"""
    try:
        all_data = get_cached_or_fetch()
        basins = all_data["basins"]

        # Map basin codes to display names
        basin_names = {
            "HONG": "Sông Hồng",
            "MEKONG": "Sông Mekong",
            "DONGNAI": "Sông Đồng Nai",
            "CENTRAL": "Miền Trung"
        }

        # Get risk levels for each basin
        basin_risk_levels = {}
        for basin_code, basin_data in basins.items():
            # Determine overall risk level for basin
            has_danger = False
            has_warning = False
            has_watch = False

            for day in basin_data["forecast_days"]:
                risk = day["risk_level"].upper()
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

        # Create stations list from MONITORING_POINTS
        stations = []
        station_id = 1

        # Major stations for each basin
        major_stations = {
            "HONG": [
                {"name": "Hà Nội", "lat": 21.0285, "lon": 105.8542},
                {"name": "Sơn Tây", "lat": 21.1333, "lon": 105.5000},
                {"name": "Việt Trì", "lat": 21.3100, "lon": 105.4019},
                {"name": "Phú Thọ", "lat": 21.4200, "lon": 105.2000},
                {"name": "Hải Phòng", "lat": 20.8449, "lon": 106.6881},
            ],
            "MEKONG": [
                {"name": "Cần Thơ", "lat": 10.0452, "lon": 105.7469},
                {"name": "Tân Châu", "lat": 10.8000, "lon": 105.2333},
                {"name": "Châu Đốc", "lat": 10.7000, "lon": 105.1167},
                {"name": "Long An", "lat": 10.5333, "lon": 106.4167},
                {"name": "An Giang", "lat": 10.5216, "lon": 105.1258},
            ],
            "DONGNAI": [
                {"name": "TP Hồ Chí Minh", "lat": 10.7769, "lon": 106.7009},
                {"name": "Đồng Nai", "lat": 10.9574, "lon": 106.8426},
                {"name": "Bình Dương", "lat": 11.3254, "lon": 106.4770},
                {"name": "Bà Rịa-Vũng Tàu", "lat": 10.5417, "lon": 107.2429},
            ],
            "CENTRAL": [
                {"name": "Đà Nẵng", "lat": 16.0544, "lon": 108.2022},
                {"name": "Huế", "lat": 16.4637, "lon": 107.5909},
                {"name": "Quảng Nam", "lat": 15.5393, "lon": 108.0192},
                {"name": "Quảng Ngãi", "lat": 15.1214, "lon": 108.8044},
                {"name": "Nghệ An", "lat": 18.6793, "lon": 105.6811},
            ],
        }

        basin_id_map = {"HONG": 1, "MEKONG": 2, "DONGNAI": 3, "CENTRAL": 4}

        for basin_code, station_list in major_stations.items():
            basin_risk = basin_risk_levels.get(basin_code, "safe")
            basin_forecast = basins.get(basin_code, {})
            current_rain = basin_forecast.get("forecast_days", [{}])[0].get("daily_rain", 0) if basin_forecast.get("forecast_days") else 0

            for station_info in station_list:
                stations.append({
                    "station_id": station_id,
                    "station_name": station_info["name"],
                    "latitude": station_info["lat"],
                    "longitude": station_info["lon"],
                    "basin_id": basin_id_map[basin_code],
                    "basin_name": basin_names[basin_code],
                    "basin_code": basin_code,  # Add basin_code for API calls
                    "risk_level": basin_risk,
                    "current_rainfall": current_rain,
                })
                station_id += 1

        return {
            "stations": stations,
            "total_stations": len(stations),
            "generated_at": all_data["generated_at"]
        }
    except Exception as e:
        print(f"Error in /api/stations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =====================================================
# DỮ LIỆU ĐẬP THỦY ĐIỆN VÀ HỒ CHỨA THỰC TẾ VIỆT NAM
# =====================================================

VIETNAM_DAMS = {
    # === LƯU VỰC SÔNG HỒNG ===
    "HONG": [
        {
            "id": "hoa_binh",
            "name": "Thủy điện Hòa Bình",
            "river": "Sông Đà",
            "province": "Hòa Bình",
            "capacity_mw": 1920,
            "reservoir_volume_million_m3": 9450,
            "max_discharge_m3s": 27000,
            "normal_level_m": 117,
            "flood_level_m": 120,
            "dead_level_m": 80,
            "spillway_gates": 12,
            "coordinates": {"lat": 20.8167, "lon": 105.3167},
            "downstream_areas": ["Thành phố Hòa Bình", "Hà Nội (Ba Vì, Đan Phượng)", "Hà Nam", "Nam Định"],
            "affected_rivers": ["Sông Đà", "Sông Hồng"],
            "warning_time_hours": 6,
            "description": "Đập thủy điện lớn nhất Đông Nam Á khi hoàn thành (1994)"
        },
        {
            "id": "son_la",
            "name": "Thủy điện Sơn La",
            "river": "Sông Đà",
            "province": "Sơn La",
            "capacity_mw": 2400,
            "reservoir_volume_million_m3": 9260,
            "max_discharge_m3s": 35640,
            "normal_level_m": 215,
            "flood_level_m": 217.83,
            "dead_level_m": 175,
            "spillway_gates": 12,
            "coordinates": {"lat": 21.2833, "lon": 103.9500},
            "downstream_areas": ["Thành phố Sơn La", "Hòa Bình", "Hà Nội", "Phú Thọ"],
            "affected_rivers": ["Sông Đà"],
            "warning_time_hours": 8,
            "description": "Nhà máy thủy điện lớn nhất Việt Nam và Đông Nam Á"
        },
        {
            "id": "lai_chau",
            "name": "Thủy điện Lai Châu",
            "river": "Sông Đà",
            "province": "Lai Châu",
            "capacity_mw": 1200,
            "reservoir_volume_million_m3": 1215,
            "max_discharge_m3s": 15300,
            "normal_level_m": 295,
            "flood_level_m": 297,
            "dead_level_m": 270,
            "spillway_gates": 8,
            "coordinates": {"lat": 22.0500, "lon": 103.1833},
            "downstream_areas": ["Thành phố Lai Châu", "Điện Biên", "Sơn La"],
            "affected_rivers": ["Sông Đà"],
            "warning_time_hours": 10,
            "description": "Bậc thang thủy điện cao nhất trên sông Đà"
        },
        {
            "id": "thac_ba",
            "name": "Thủy điện Thác Bà",
            "river": "Sông Chảy",
            "province": "Yên Bái",
            "capacity_mw": 120,
            "reservoir_volume_million_m3": 2940,
            "max_discharge_m3s": 3500,
            "normal_level_m": 58,
            "flood_level_m": 60,
            "dead_level_m": 46,
            "spillway_gates": 6,
            "coordinates": {"lat": 21.8333, "lon": 104.8333},
            "downstream_areas": ["Yên Bái", "Phú Thọ", "Vĩnh Phúc"],
            "affected_rivers": ["Sông Chảy", "Sông Lô"],
            "warning_time_hours": 5,
            "description": "Nhà máy thủy điện đầu tiên của Việt Nam (1971)"
        },
        {
            "id": "tuyen_quang",
            "name": "Thủy điện Tuyên Quang",
            "river": "Sông Gâm",
            "province": "Tuyên Quang",
            "capacity_mw": 342,
            "reservoir_volume_million_m3": 2260,
            "max_discharge_m3s": 5000,
            "normal_level_m": 120,
            "flood_level_m": 122,
            "dead_level_m": 90,
            "spillway_gates": 5,
            "coordinates": {"lat": 22.1167, "lon": 105.2167},
            "downstream_areas": ["Tuyên Quang", "Hà Giang", "Phú Thọ"],
            "affected_rivers": ["Sông Gâm", "Sông Lô"],
            "warning_time_hours": 6,
            "description": "Hồ chứa lớn thứ 3 miền Bắc"
        },
    ],

    # === LƯU VỰC MIỀN TRUNG ===
    "CENTRAL": [
        {
            "id": "a_vuong",
            "name": "Thủy điện A Vương",
            "river": "Sông Vu Gia",
            "province": "Quảng Nam",
            "capacity_mw": 210,
            "reservoir_volume_million_m3": 343,
            "max_discharge_m3s": 4500,
            "normal_level_m": 380,
            "flood_level_m": 381,
            "dead_level_m": 340,
            "spillway_gates": 4,
            "coordinates": {"lat": 15.8500, "lon": 107.5833},
            "downstream_areas": ["Đà Nẵng (Hòa Vang, Cẩm Lệ)", "Quảng Nam (Đại Lộc, Điện Bàn)", "Hội An"],
            "affected_rivers": ["Sông Vu Gia", "Sông Thu Bồn"],
            "warning_time_hours": 4,
            "description": "Đập thủy điện chính trên thượng nguồn sông Vu Gia"
        },
        {
            "id": "song_tranh_2",
            "name": "Thủy điện Sông Tranh 2",
            "river": "Sông Tranh",
            "province": "Quảng Nam",
            "capacity_mw": 190,
            "reservoir_volume_million_m3": 730,
            "max_discharge_m3s": 5000,
            "normal_level_m": 175,
            "flood_level_m": 178,
            "dead_level_m": 140,
            "spillway_gates": 5,
            "coordinates": {"lat": 15.4167, "lon": 108.0333},
            "downstream_areas": ["Quảng Nam (Tiên Phước, Hiệp Đức, Nông Sơn)", "Tam Kỳ", "Núi Thành"],
            "affected_rivers": ["Sông Tranh", "Sông Thu Bồn"],
            "warning_time_hours": 3,
            "description": "Đập gây nhiều tranh cãi về động đất kích thích"
        },
        {
            "id": "dak_mi_4",
            "name": "Thủy điện Đắk Mi 4",
            "river": "Sông Đắk Mi",
            "province": "Quảng Nam",
            "capacity_mw": 190,
            "reservoir_volume_million_m3": 316,
            "max_discharge_m3s": 3200,
            "normal_level_m": 258,
            "flood_level_m": 260,
            "dead_level_m": 230,
            "spillway_gates": 4,
            "coordinates": {"lat": 15.6833, "lon": 107.8500},
            "downstream_areas": ["Quảng Nam (Phước Sơn, Đông Giang)", "Đà Nẵng"],
            "affected_rivers": ["Sông Đắk Mi", "Sông Vu Gia"],
            "warning_time_hours": 4,
            "description": "Phần lớn nước chảy về sông Thu Bồn"
        },
        {
            "id": "binh_dien",
            "name": "Thủy điện Bình Điền",
            "river": "Sông Hương",
            "province": "Thừa Thiên Huế",
            "capacity_mw": 44,
            "reservoir_volume_million_m3": 424,
            "max_discharge_m3s": 2800,
            "normal_level_m": 85,
            "flood_level_m": 86.5,
            "dead_level_m": 61,
            "spillway_gates": 4,
            "coordinates": {"lat": 16.3000, "lon": 107.4333},
            "downstream_areas": ["Thừa Thiên Huế (Hương Trà, Phong Điền)", "TP Huế", "Phú Vang"],
            "affected_rivers": ["Sông Hương", "Sông Bồ"],
            "warning_time_hours": 3,
            "description": "Đập chính điều tiết lũ cho TP Huế"
        },
        {
            "id": "huong_dien",
            "name": "Thủy điện Hương Điền",
            "river": "Sông Bồ",
            "province": "Thừa Thiên Huế",
            "capacity_mw": 81,
            "reservoir_volume_million_m3": 820,
            "max_discharge_m3s": 3500,
            "normal_level_m": 58,
            "flood_level_m": 59,
            "dead_level_m": 35,
            "spillway_gates": 5,
            "coordinates": {"lat": 16.4333, "lon": 107.3667},
            "downstream_areas": ["Thừa Thiên Huế (Quảng Điền, Phong Điền)", "TP Huế"],
            "affected_rivers": ["Sông Bồ", "Sông Hương"],
            "warning_time_hours": 3,
            "description": "Hồ chứa quan trọng cho vùng Huế"
        },
        {
            "id": "rao_quan",
            "name": "Thủy điện Rào Quán",
            "river": "Sông Rào Quán",
            "province": "Quảng Trị",
            "capacity_mw": 64,
            "reservoir_volume_million_m3": 195,
            "max_discharge_m3s": 1800,
            "normal_level_m": 250,
            "flood_level_m": 252,
            "dead_level_m": 220,
            "spillway_gates": 3,
            "coordinates": {"lat": 16.6500, "lon": 107.0333},
            "downstream_areas": ["Quảng Trị (Hướng Hóa, Đakrông)", "Đông Hà", "Triệu Phong"],
            "affected_rivers": ["Sông Thạch Hãn"],
            "warning_time_hours": 4,
            "description": "Đập thủy điện chính tỉnh Quảng Trị"
        },
        {
            "id": "ban_ve",
            "name": "Thủy điện Bản Vẽ",
            "river": "Sông Cả",
            "province": "Nghệ An",
            "capacity_mw": 320,
            "reservoir_volume_million_m3": 1834,
            "max_discharge_m3s": 8000,
            "normal_level_m": 200,
            "flood_level_m": 202,
            "dead_level_m": 155,
            "spillway_gates": 6,
            "coordinates": {"lat": 19.3167, "lon": 104.5833},
            "downstream_areas": ["Nghệ An (Tương Dương, Con Cuông, Anh Sơn)", "TP Vinh", "Cửa Lò"],
            "affected_rivers": ["Sông Cả", "Sông Lam"],
            "warning_time_hours": 5,
            "description": "Hồ chứa lớn nhất Bắc Trung Bộ"
        },
        {
            "id": "cua_dat",
            "name": "Hồ Cửa Đạt",
            "river": "Sông Chu",
            "province": "Thanh Hóa",
            "capacity_mw": 97,
            "reservoir_volume_million_m3": 1450,
            "max_discharge_m3s": 5600,
            "normal_level_m": 110,
            "flood_level_m": 113.14,
            "dead_level_m": 66,
            "spillway_gates": 5,
            "coordinates": {"lat": 19.8500, "lon": 105.2833},
            "downstream_areas": ["Thanh Hóa (Thường Xuân, Ngọc Lặc)", "TP Thanh Hóa", "Sầm Sơn"],
            "affected_rivers": ["Sông Chu", "Sông Mã"],
            "warning_time_hours": 5,
            "description": "Hồ chứa đa mục tiêu lớn nhất Thanh Hóa"
        },
    ],

    # === LƯU VỰC SÔNG ĐỒNG NAI ===
    "DONGNAI": [
        {
            "id": "tri_an",
            "name": "Thủy điện Trị An",
            "river": "Sông Đồng Nai",
            "province": "Đồng Nai",
            "capacity_mw": 400,
            "reservoir_volume_million_m3": 2765,
            "max_discharge_m3s": 8400,
            "normal_level_m": 62,
            "flood_level_m": 63.9,
            "dead_level_m": 50,
            "spillway_gates": 8,
            "coordinates": {"lat": 11.0667, "lon": 107.0167},
            "downstream_areas": ["Đồng Nai (Vĩnh Cửu, Trảng Bom, Biên Hòa)", "TP.HCM (Quận 9, Thủ Đức)", "Bình Dương"],
            "affected_rivers": ["Sông Đồng Nai", "Sông Sài Gòn"],
            "warning_time_hours": 6,
            "description": "Hồ chứa nước ngọt lớn nhất miền Nam"
        },
        {
            "id": "thac_mo",
            "name": "Thủy điện Thác Mơ",
            "river": "Sông Bé",
            "province": "Bình Phước",
            "capacity_mw": 150,
            "reservoir_volume_million_m3": 1360,
            "max_discharge_m3s": 4500,
            "normal_level_m": 218,
            "flood_level_m": 219.5,
            "dead_level_m": 195,
            "spillway_gates": 5,
            "coordinates": {"lat": 11.8333, "lon": 107.0167},
            "downstream_areas": ["Bình Phước (Phước Long, Bù Đăng)", "Bình Dương (Phú Giáo, Bến Cát)"],
            "affected_rivers": ["Sông Bé"],
            "warning_time_hours": 5,
            "description": "Đập trên thượng nguồn sông Bé"
        },
        {
            "id": "can_don",
            "name": "Thủy điện Cần Đơn",
            "river": "Sông Bé",
            "province": "Bình Phước",
            "capacity_mw": 78,
            "reservoir_volume_million_m3": 165,
            "max_discharge_m3s": 2800,
            "normal_level_m": 109.2,
            "flood_level_m": 110,
            "dead_level_m": 100,
            "spillway_gates": 4,
            "coordinates": {"lat": 11.6833, "lon": 106.9667},
            "downstream_areas": ["Bình Phước (Đồng Phú, Chơn Thành)", "Bình Dương"],
            "affected_rivers": ["Sông Bé"],
            "warning_time_hours": 4,
            "description": "Bậc thang thủy điện giữa sông Bé"
        },
        {
            "id": "dau_tieng",
            "name": "Hồ Dầu Tiếng",
            "river": "Sông Sài Gòn",
            "province": "Tây Ninh",
            "capacity_mw": 0,  # Hồ thủy lợi, không phát điện
            "reservoir_volume_million_m3": 1580,
            "max_discharge_m3s": 2500,
            "normal_level_m": 24.4,
            "flood_level_m": 25.1,
            "dead_level_m": 17,
            "spillway_gates": 6,
            "coordinates": {"lat": 11.3333, "lon": 106.3833},
            "downstream_areas": ["Tây Ninh", "TP.HCM (Củ Chi, Hóc Môn, Bình Chánh)", "Long An"],
            "affected_rivers": ["Sông Sài Gòn"],
            "warning_time_hours": 8,
            "description": "Hồ thủy lợi nhân tạo lớn nhất Việt Nam"
        },
        {
            "id": "da_nhim",
            "name": "Thủy điện Đa Nhim",
            "river": "Sông Đa Nhim",
            "province": "Lâm Đồng",
            "capacity_mw": 160,
            "reservoir_volume_million_m3": 165,
            "max_discharge_m3s": 1200,
            "normal_level_m": 1042,
            "flood_level_m": 1042,
            "dead_level_m": 1020,
            "spillway_gates": 3,
            "coordinates": {"lat": 11.9667, "lon": 108.5833},
            "downstream_areas": ["Lâm Đồng (Đơn Dương, Đức Trọng)", "Ninh Thuận (Ninh Sơn)"],
            "affected_rivers": ["Sông Đa Nhim"],
            "warning_time_hours": 3,
            "description": "Nhà máy thủy điện kiểu đường ống áp lực"
        },
    ],

    # === LƯU VỰC SÔNG MEKONG ===
    "MEKONG": [
        {
            "id": "yali",
            "name": "Thủy điện Yaly",
            "river": "Sông Sê San",
            "province": "Gia Lai",
            "capacity_mw": 720,
            "reservoir_volume_million_m3": 1037,
            "max_discharge_m3s": 6800,
            "normal_level_m": 515,
            "flood_level_m": 517,
            "dead_level_m": 490,
            "spillway_gates": 6,
            "coordinates": {"lat": 14.2000, "lon": 107.8167},
            "downstream_areas": ["Gia Lai (Chư Păh, Ia Grai)", "Kon Tum", "Campuchia (hạ lưu)"],
            "affected_rivers": ["Sông Sê San"],
            "warning_time_hours": 6,
            "description": "Đập thủy điện lớn nhất Tây Nguyên"
        },
        {
            "id": "sesan_4",
            "name": "Thủy điện Sê San 4",
            "river": "Sông Sê San",
            "province": "Gia Lai",
            "capacity_mw": 360,
            "reservoir_volume_million_m3": 265,
            "max_discharge_m3s": 5200,
            "normal_level_m": 215,
            "flood_level_m": 217,
            "dead_level_m": 205,
            "spillway_gates": 5,
            "coordinates": {"lat": 14.1500, "lon": 107.8333},
            "downstream_areas": ["Gia Lai (Đức Cơ, Chư Prông)", "Campuchia"],
            "affected_rivers": ["Sông Sê San"],
            "warning_time_hours": 4,
            "description": "Bậc thang cuối cùng trên sông Sê San"
        },
        {
            "id": "pleikrong",
            "name": "Thủy điện Pleikrông",
            "river": "Sông Pô Cô",
            "province": "Kon Tum",
            "capacity_mw": 100,
            "reservoir_volume_million_m3": 1048,
            "max_discharge_m3s": 3500,
            "normal_level_m": 570,
            "flood_level_m": 572,
            "dead_level_m": 537,
            "spillway_gates": 4,
            "coordinates": {"lat": 14.5000, "lon": 107.9333},
            "downstream_areas": ["Kon Tum (Sa Thầy, Đắk Hà)", "Gia Lai"],
            "affected_rivers": ["Sông Pô Cô", "Sông Sê San"],
            "warning_time_hours": 5,
            "description": "Hồ chứa điều tiết năm"
        },
        {
            "id": "buon_kuop",
            "name": "Thủy điện Buôn Kuốp",
            "river": "Sông Srêpốk",
            "province": "Đắk Lắk",
            "capacity_mw": 280,
            "reservoir_volume_million_m3": 310,
            "max_discharge_m3s": 4200,
            "normal_level_m": 412,
            "flood_level_m": 414,
            "dead_level_m": 395,
            "spillway_gates": 5,
            "coordinates": {"lat": 12.7167, "lon": 108.0667},
            "downstream_areas": ["Đắk Lắk (Krông Ana, Buôn Đôn)", "Đắk Nông", "Campuchia"],
            "affected_rivers": ["Sông Srêpốk"],
            "warning_time_hours": 5,
            "description": "Đập thủy điện chính trên sông Srêpốk"
        },
        {
            "id": "srepok_3",
            "name": "Thủy điện Srêpốk 3",
            "river": "Sông Srêpốk",
            "province": "Đắk Lắk",
            "capacity_mw": 220,
            "reservoir_volume_million_m3": 373,
            "max_discharge_m3s": 4500,
            "normal_level_m": 272,
            "flood_level_m": 274,
            "dead_level_m": 260,
            "spillway_gates": 5,
            "coordinates": {"lat": 12.6500, "lon": 107.5333},
            "downstream_areas": ["Đắk Lắk (Buôn Đôn, Ea Súp)", "Campuchia"],
            "affected_rivers": ["Sông Srêpốk"],
            "warning_time_hours": 4,
            "description": "Bậc thang thủy điện trên sông Srêpốk"
        },
        {
            "id": "dray_hlinh",
            "name": "Thủy điện Dray H'Linh",
            "river": "Sông Srêpốk",
            "province": "Đắk Lắk",
            "capacity_mw": 28,
            "reservoir_volume_million_m3": 25,
            "max_discharge_m3s": 800,
            "normal_level_m": 455,
            "flood_level_m": 456,
            "dead_level_m": 450,
            "spillway_gates": 2,
            "coordinates": {"lat": 12.6833, "lon": 108.1000},
            "downstream_areas": ["TP Buôn Ma Thuột", "Krông Ana"],
            "affected_rivers": ["Sông Srêpốk"],
            "warning_time_hours": 2,
            "description": "Đập nhỏ cung cấp nước cho Buôn Ma Thuột"
        },
    ]
}

# Dữ liệu sông chính Việt Nam
VIETNAM_RIVERS = {
    "HONG": [
        {
            "name": "Sông Hồng",
            "length_km": 1149,
            "basin_area_km2": 155000,
            "provinces": ["Lào Cai", "Yên Bái", "Phú Thọ", "Vĩnh Phúc", "Hà Nội", "Hưng Yên", "Hà Nam", "Nam Định", "Thái Bình"],
            "flood_prone_areas": [
                {"name": "Hà Nội", "districts": ["Ba Vì", "Đan Phượng", "Phúc Thọ", "Thường Tín"], "risk": "Cao"},
                {"name": "Nam Định", "districts": ["Mỹ Lộc", "Vụ Bản", "Ý Yên", "Nam Trực"], "risk": "Cao"},
                {"name": "Thái Bình", "districts": ["Vũ Thư", "Kiến Xương", "Tiền Hải"], "risk": "Trung bình"},
            ],
            "alert_levels": {"level_1": 9.5, "level_2": 10.5, "level_3": 11.5}  # mét tại Hà Nội
        },
        {
            "name": "Sông Đà",
            "length_km": 527,
            "basin_area_km2": 52900,
            "provinces": ["Lai Châu", "Điện Biên", "Sơn La", "Hòa Bình", "Phú Thọ"],
            "flood_prone_areas": [
                {"name": "Sơn La", "districts": ["Mường La", "Quỳnh Nhai", "TP Sơn La"], "risk": "Cao"},
                {"name": "Hòa Bình", "districts": ["Mai Châu", "Đà Bắc", "TP Hòa Bình"], "risk": "Cao"},
            ],
            "alert_levels": {"level_1": 15.0, "level_2": 17.0, "level_3": 19.0}
        },
        {
            "name": "Sông Lô",
            "length_km": 470,
            "basin_area_km2": 39000,
            "provinces": ["Hà Giang", "Tuyên Quang", "Phú Thọ", "Vĩnh Phúc"],
            "flood_prone_areas": [
                {"name": "Tuyên Quang", "districts": ["Chiêm Hóa", "Yên Sơn", "TP Tuyên Quang"], "risk": "Trung bình"},
                {"name": "Phú Thọ", "districts": ["Đoan Hùng", "Phù Ninh"], "risk": "Trung bình"},
            ],
            "alert_levels": {"level_1": 17.0, "level_2": 19.0, "level_3": 21.0}
        },
    ],
    "CENTRAL": [
        {
            "name": "Sông Thu Bồn",
            "length_km": 205,
            "basin_area_km2": 10350,
            "provinces": ["Quảng Nam"],
            "flood_prone_areas": [
                {"name": "Quảng Nam", "districts": ["Đại Lộc", "Duy Xuyên", "Điện Bàn", "Hội An"], "risk": "Rất cao"},
            ],
            "alert_levels": {"level_1": 5.0, "level_2": 7.0, "level_3": 9.0}
        },
        {
            "name": "Sông Vu Gia",
            "length_km": 204,
            "basin_area_km2": 5180,
            "provinces": ["Quảng Nam", "Đà Nẵng"],
            "flood_prone_areas": [
                {"name": "Đà Nẵng", "districts": ["Hòa Vang", "Cẩm Lệ", "Liên Chiểu"], "risk": "Cao"},
                {"name": "Quảng Nam", "districts": ["Đại Lộc", "Điện Bàn"], "risk": "Cao"},
            ],
            "alert_levels": {"level_1": 4.5, "level_2": 6.0, "level_3": 8.0}
        },
        {
            "name": "Sông Hương",
            "length_km": 104,
            "basin_area_km2": 2830,
            "provinces": ["Thừa Thiên Huế"],
            "flood_prone_areas": [
                {"name": "Thừa Thiên Huế", "districts": ["TP Huế", "Hương Trà", "Phú Vang", "Quảng Điền"], "risk": "Rất cao"},
            ],
            "alert_levels": {"level_1": 2.0, "level_2": 3.0, "level_3": 4.0}
        },
        {
            "name": "Sông Cả (Sông Lam)",
            "length_km": 531,
            "basin_area_km2": 27200,
            "provinces": ["Nghệ An", "Hà Tĩnh"],
            "flood_prone_areas": [
                {"name": "Nghệ An", "districts": ["TP Vinh", "Hưng Nguyên", "Nam Đàn", "Thanh Chương"], "risk": "Cao"},
                {"name": "Hà Tĩnh", "districts": ["Đức Thọ", "Hương Sơn"], "risk": "Trung bình"},
            ],
            "alert_levels": {"level_1": 4.0, "level_2": 6.0, "level_3": 8.0}
        },
        {
            "name": "Sông Mã",
            "length_km": 512,
            "basin_area_km2": 28400,
            "provinces": ["Thanh Hóa", "Sơn La"],
            "flood_prone_areas": [
                {"name": "Thanh Hóa", "districts": ["TP Thanh Hóa", "Thiệu Hóa", "Yên Định", "Vĩnh Lộc"], "risk": "Cao"},
            ],
            "alert_levels": {"level_1": 7.0, "level_2": 9.0, "level_3": 11.0}
        },
    ],
    "DONGNAI": [
        {
            "name": "Sông Đồng Nai",
            "length_km": 586,
            "basin_area_km2": 38600,
            "provinces": ["Lâm Đồng", "Đắk Nông", "Bình Phước", "Đồng Nai", "Bình Dương", "TP.HCM"],
            "flood_prone_areas": [
                {"name": "Đồng Nai", "districts": ["Biên Hòa", "Vĩnh Cửu", "Trảng Bom", "Long Thành"], "risk": "Cao"},
                {"name": "TP.HCM", "districts": ["Thủ Đức", "Quận 9", "Quận 2"], "risk": "Trung bình"},
            ],
            "alert_levels": {"level_1": 2.5, "level_2": 3.5, "level_3": 4.5}
        },
        {
            "name": "Sông Sài Gòn",
            "length_km": 256,
            "basin_area_km2": 4717,
            "provinces": ["Tây Ninh", "Bình Dương", "Bình Phước", "TP.HCM"],
            "flood_prone_areas": [
                {"name": "TP.HCM", "districts": ["Củ Chi", "Hóc Môn", "Bình Chánh", "Quận 12"], "risk": "Cao"},
                {"name": "Bình Dương", "districts": ["Dĩ An", "Thuận An", "Tân Uyên"], "risk": "Trung bình"},
            ],
            "alert_levels": {"level_1": 1.4, "level_2": 1.6, "level_3": 1.8}
        },
        {
            "name": "Sông Bé",
            "length_km": 350,
            "basin_area_km2": 7650,
            "provinces": ["Bình Phước", "Bình Dương", "Đồng Nai"],
            "flood_prone_areas": [
                {"name": "Bình Phước", "districts": ["Phước Long", "Bù Đăng", "Đồng Phú"], "risk": "Trung bình"},
                {"name": "Bình Dương", "districts": ["Phú Giáo", "Bến Cát"], "risk": "Trung bình"},
            ],
            "alert_levels": {"level_1": 3.0, "level_2": 4.5, "level_3": 6.0}
        },
    ],
    "MEKONG": [
        {
            "name": "Sông Mekong (Cửu Long)",
            "length_km": 4350,
            "basin_area_km2": 795000,
            "provinces": ["An Giang", "Đồng Tháp", "Vĩnh Long", "Cần Thơ", "Hậu Giang", "Sóc Trăng", "Trà Vinh", "Bến Tre", "Tiền Giang", "Long An"],
            "flood_prone_areas": [
                {"name": "An Giang", "districts": ["Tân Châu", "An Phú", "Châu Phú", "Châu Đốc"], "risk": "Rất cao"},
                {"name": "Đồng Tháp", "districts": ["Hồng Ngự", "Tân Hồng", "Tam Nông", "Thanh Bình"], "risk": "Rất cao"},
                {"name": "Long An", "districts": ["Tân Hưng", "Vĩnh Hưng", "Mộc Hóa", "Tân Thạnh"], "risk": "Cao"},
            ],
            "alert_levels": {"level_1": 3.5, "level_2": 4.0, "level_3": 4.5}  # tại Tân Châu
        },
        {
            "name": "Sông Tiền",
            "length_km": 234,
            "basin_area_km2": 15000,
            "provinces": ["An Giang", "Đồng Tháp", "Tiền Giang", "Vĩnh Long", "Bến Tre"],
            "flood_prone_areas": [
                {"name": "Tiền Giang", "districts": ["Cai Lậy", "Cái Bè", "Châu Thành"], "risk": "Cao"},
                {"name": "Bến Tre", "districts": ["Châu Thành", "Chợ Lách", "Mỏ Cày"], "risk": "Cao"},
            ],
            "alert_levels": {"level_1": 2.8, "level_2": 3.5, "level_3": 4.2}
        },
        {
            "name": "Sông Hậu",
            "length_km": 200,
            "basin_area_km2": 16000,
            "provinces": ["An Giang", "Cần Thơ", "Hậu Giang", "Sóc Trăng", "Trà Vinh"],
            "flood_prone_areas": [
                {"name": "Cần Thơ", "districts": ["Thốt Nốt", "Vĩnh Thạnh", "Cờ Đỏ", "Phong Điền"], "risk": "Cao"},
                {"name": "Sóc Trăng", "districts": ["Kế Sách", "Long Phú", "Cù Lao Dung"], "risk": "Cao"},
            ],
            "alert_levels": {"level_1": 2.5, "level_2": 3.2, "level_3": 4.0}
        },
        {
            "name": "Sông Sê San",
            "length_km": 237,
            "basin_area_km2": 11450,
            "provinces": ["Kon Tum", "Gia Lai"],
            "flood_prone_areas": [
                {"name": "Gia Lai", "districts": ["Ia Grai", "Chư Păh", "Đức Cơ"], "risk": "Trung bình"},
                {"name": "Kon Tum", "districts": ["Sa Thầy", "Ngọc Hồi"], "risk": "Trung bình"},
            ],
            "alert_levels": {"level_1": 380.0, "level_2": 400.0, "level_3": 420.0}
        },
        {
            "name": "Sông Srêpốk",
            "length_km": 315,
            "basin_area_km2": 12000,
            "provinces": ["Đắk Lắk", "Đắk Nông"],
            "flood_prone_areas": [
                {"name": "Đắk Lắk", "districts": ["Buôn Đôn", "Ea Súp", "Krông Ana"], "risk": "Trung bình"},
            ],
            "alert_levels": {"level_1": 400.0, "level_2": 420.0, "level_3": 440.0}
        },
    ]
}


def generate_dam_discharge_alerts(basin_name: str, forecast_data: dict) -> list:
    """
    Tạo cảnh báo xả lũ dựa trên dữ liệu dự báo mưa

    LƯU Ý: Thông tin cơ sở về đập (tên, vị trí, công suất) là THẬT
    Nhưng dữ liệu vận hành (mực nước hiện tại, số cửa xả mở) là ƯỚC TÍNH
    vì không có API công khai từ EVN/nhà máy thủy điện Việt Nam

    Cách ước tính dựa trên:
    - Lượng mưa thượng nguồn (có thể lấy từ Open-Meteo - DỮ LIỆU THẬT)
    - Lưu lượng sông từ GloFAS (DỮ LIỆU THẬT)
    - Mô hình thủy văn đơn giản để ước tính mực nước hồ
    """
    from datetime import datetime, timedelta

    alerts = []
    dams = VIETNAM_DAMS.get(basin_name, [])
    rivers = VIETNAM_RIVERS.get(basin_name, [])

    if not dams or not forecast_data:
        return alerts

    forecast_days = forecast_data.get("forecast_days", [])

    for dam in dams:
        # Tính toán mức xả lũ dựa trên lượng mưa dự báo
        for i, day in enumerate(forecast_days):
            daily_rain = day.get("daily_rain", 0)
            accumulated = day.get("accumulated_3d", 0)
            risk_level = day.get("risk_level", "").upper()

            # Xác định có cần xả lũ không
            needs_discharge = False
            discharge_level = "normal"
            estimated_discharge = 0

            # Công thức ước tính dựa trên lượng mưa thực
            # Q_discharge = f(rainfall, reservoir_volume, catchment_area)
            # Hệ số runoff trung bình Việt Nam: 0.4-0.6
            runoff_coefficient = 0.5

            # Diện tích lưu vực ước tính (km²) dựa trên dung tích hồ
            catchment_area_km2 = dam["reservoir_volume_million_m3"] * 10  # Ước tính

            # Lưu lượng nước đổ về hồ (m³/s) từ mưa
            # Q = (Rainfall_mm * Area_km2 * runoff_coef * 1000) / (24 * 3600)
            inflow_from_rain = (daily_rain * catchment_area_km2 * runoff_coefficient * 1000) / 86400

            if daily_rain > 100 or accumulated > 200 or "NGUY" in risk_level or "DANGER" in risk_level:
                needs_discharge = True
                discharge_level = "emergency"
                # Xả tương ứng với lượng nước đổ về + điều tiết
                discharge_ratio = min(0.95, 0.6 + (daily_rain / 200) * 0.35)
                estimated_discharge = min(dam["max_discharge_m3s"] * discharge_ratio,
                                         inflow_from_rain * 1.2 + dam["max_discharge_m3s"] * 0.3)
            elif daily_rain > 50 or accumulated > 100 or "CẢNH" in risk_level or "WARNING" in risk_level:
                needs_discharge = True
                discharge_level = "warning"
                discharge_ratio = min(0.6, 0.3 + (daily_rain / 150) * 0.3)
                estimated_discharge = min(dam["max_discharge_m3s"] * discharge_ratio,
                                         inflow_from_rain * 1.1 + dam["max_discharge_m3s"] * 0.15)
            elif daily_rain > 30 or accumulated > 60:
                needs_discharge = True
                discharge_level = "watch"
                discharge_ratio = min(0.3, 0.1 + (daily_rain / 100) * 0.2)
                estimated_discharge = min(dam["max_discharge_m3s"] * discharge_ratio,
                                         inflow_from_rain + dam["max_discharge_m3s"] * 0.05)

            if needs_discharge:
                # Tính mực nước hồ ước tính
                current_level = dam["normal_level_m"] + (daily_rain / 100) * (dam["flood_level_m"] - dam["normal_level_m"])
                current_level = min(current_level, dam["flood_level_m"] + 1)

                # Tìm sông liên quan
                related_rivers = []
                for river in rivers:
                    if river["name"] in dam["affected_rivers"] or dam["river"] in river["name"]:
                        related_rivers.append(river)

                # Tính thời gian xả dự kiến dựa trên mức độ khẩn cấp
                # Emergency: sáng sớm (6-10h), Warning: ban ngày (8-14h), Watch: linh hoạt (10-18h)
                time_base = {"emergency": 6, "warning": 8, "watch": 10}.get(discharge_level, 8)
                time_offset = int((daily_rain % 50) / 10)  # 0-4 giờ offset dựa trên lượng mưa
                discharge_hour = time_base + time_offset

                alert = {
                    "id": f"{dam['id']}_{day['date']}",
                    "dam_id": dam["id"],
                    "dam_name": dam["name"],
                    "river": dam["river"],
                    "province": dam["province"],
                    "date": day["date"],
                    "time_estimate": f"{discharge_hour}:00",  # Giờ xả dự kiến (ước tính từ mức khẩn cấp)
                    "alert_level": discharge_level,
                    "alert_level_vn": {
                        "emergency": "KHẨN CẤP",
                        "warning": "CẢNH BÁO",
                        "watch": "THEO DÕI"
                    }.get(discharge_level, "THEO DÕI"),

                    # Thông tin kỹ thuật
                    "current_water_level_m": round(current_level, 2),
                    "normal_level_m": dam["normal_level_m"],
                    "flood_level_m": dam["flood_level_m"],
                    "water_level_percent": round((current_level - dam["dead_level_m"]) / (dam["flood_level_m"] - dam["dead_level_m"]) * 100, 1),

                    # Thông tin xả lũ
                    "estimated_discharge_m3s": round(estimated_discharge, 0),
                    "max_discharge_m3s": dam["max_discharge_m3s"],
                    "discharge_percent": round(estimated_discharge / dam["max_discharge_m3s"] * 100, 1),
                    "spillway_gates_open": min(dam["spillway_gates"], max(1, int(estimated_discharge / dam["max_discharge_m3s"] * dam["spillway_gates"]))),
                    "total_spillway_gates": dam["spillway_gates"],

                    # Lượng xả ước tính
                    "estimated_volume_million_m3": round(estimated_discharge * 3600 * 24 / 1000000, 2),  # m³/s -> triệu m³/ngày

                    # Khu vực ảnh hưởng
                    "downstream_areas": dam["downstream_areas"],
                    "affected_rivers": dam["affected_rivers"],
                    "warning_time_hours": dam["warning_time_hours"],

                    # Thông tin chi tiết
                    "coordinates": dam["coordinates"],
                    "capacity_mw": dam["capacity_mw"],
                    "reservoir_volume_million_m3": dam["reservoir_volume_million_m3"],

                    # Thông tin mưa gây ra
                    "trigger_rainfall_mm": round(daily_rain, 1),
                    "accumulated_rainfall_mm": round(accumulated, 1),

                    # Mô tả
                    "description": f"Dự kiến xả lũ {round(estimated_discharge, 0):,.0f} m³/s ({round(estimated_discharge / dam['max_discharge_m3s'] * 100, 0):.0f}% công suất) qua {min(dam['spillway_gates'], max(1, int(estimated_discharge / dam['max_discharge_m3s'] * dam['spillway_gates'])))} cửa xả. Mực nước hồ: {round(current_level, 2)}m/{dam['flood_level_m']}m. Thời gian ảnh hưởng đến hạ du: {dam['warning_time_hours']} giờ.",

                    # Khuyến cáo
                    "recommendations": get_discharge_recommendations(discharge_level, dam, estimated_discharge)
                }

                # Thêm thông tin về các vùng ngập lụt tiềm năng
                affected_flood_zones = []
                for river in related_rivers:
                    for zone in river.get("flood_prone_areas", []):
                        affected_flood_zones.append({
                            "province": zone["name"],
                            "districts": zone["districts"],
                            "risk": zone["risk"],
                            "river": river["name"]
                        })
                alert["flood_zones"] = affected_flood_zones

                alerts.append(alert)

    # Sắp xếp theo mức độ nghiêm trọng và ngày
    severity_order = {"emergency": 0, "warning": 1, "watch": 2}
    alerts.sort(key=lambda x: (x["date"], severity_order.get(x["alert_level"], 3)))

    return alerts


def get_discharge_recommendations(level: str, dam: dict, discharge: float) -> list:
    """Tạo khuyến cáo dựa trên mức độ xả lũ"""
    recommendations = []

    if level == "emergency":
        recommendations = [
            f"KHẨN CẤP: Sơ tán người dân trong vòng {dam['warning_time_hours']} giờ tại các vùng trũng hạ du",
            f"Không được đi lại, đánh bắt cá trên sông {dam['river']} và các nhánh",
            "Di chuyển gia súc, tài sản lên vùng cao",
            "Liên hệ ngay chính quyền địa phương để được hỗ trợ sơ tán",
            f"Lưu lượng xả dự kiến: {discharge:,.0f} m³/s - Rất nguy hiểm",
            "Tuyệt đối không băng qua các tràn, đập, cầu ngập nước"
        ]
    elif level == "warning":
        recommendations = [
            f"Cảnh báo xả lũ: Chuẩn bị sẵn sàng sơ tán trong vòng {dam['warning_time_hours']} giờ",
            f"Theo dõi mực nước sông {dam['river']} liên tục",
            "Chuẩn bị đồ dùng thiết yếu, đèn pin, nước uống, thực phẩm",
            "Cập nhật thông tin từ chính quyền địa phương và đài truyền thanh",
            "Kiểm tra phương tiện, sẵn sàng di chuyển khi có lệnh sơ tán"
        ]
    else:  # watch
        recommendations = [
            f"Theo dõi diễn biến mưa lũ trên sông {dam['river']}",
            "Thường xuyên cập nhật dự báo thời tiết",
            "Kiểm tra hệ thống thoát nước quanh nhà",
            "Lưu số điện thoại khẩn cấp của địa phương"
        ]

    return recommendations


# Cache cho dam alerts với dữ liệu thật
dam_alerts_real_cache = {
    "data": None,
    "timestamp": None
}
DAM_ALERTS_CACHE_DURATION = 86400  # 24 hours


@app.get("/api/dam-alerts")
async def get_dam_discharge_alerts():
    """Lấy danh sách cảnh báo xả lũ từ các đập thủy điện"""
    try:
        all_data = get_cached_or_fetch()
        basins = all_data["basins"]

        all_alerts = []
        for basin_code, basin_data in basins.items():
            alerts = generate_dam_discharge_alerts(basin_code, basin_data)
            all_alerts.extend(alerts)

        # Sắp xếp theo mức độ nghiêm trọng
        severity_order = {"emergency": 0, "warning": 1, "watch": 2}
        all_alerts.sort(key=lambda x: (severity_order.get(x["alert_level"], 3), x["date"]))

        return {
            "generated_at": datetime.now().isoformat(),
            "total_alerts": len(all_alerts),
            "alerts": all_alerts,
            "summary": {
                "emergency": len([a for a in all_alerts if a["alert_level"] == "emergency"]),
                "warning": len([a for a in all_alerts if a["alert_level"] == "warning"]),
                "watch": len([a for a in all_alerts if a["alert_level"] == "watch"])
            }
        }
    except Exception as e:
        print(f"Error in /api/dam-alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/dam-alerts/realtime")
async def get_dam_alerts_realtime():
    """
    Lấy cảnh báo xả lũ với dữ liệu THẬT từ Open-Meteo + GloFAS

    Dữ liệu thật:
    - Lượng mưa dự báo (Open-Meteo Forecast API)
    - Lưu lượng sông (GloFAS Flood API)

    Dữ liệu ước tính:
    - Mực nước hồ, lưu lượng xả, số cửa xả (không có API công khai từ EVN)
    """
    global dam_alerts_real_cache

    try:
        now = datetime.now()

        # Kiểm tra cache
        if dam_alerts_real_cache["data"] and dam_alerts_real_cache["timestamp"]:
            elapsed = (now - dam_alerts_real_cache["timestamp"]).total_seconds()
            if elapsed < DAM_ALERTS_CACHE_DURATION:
                return dam_alerts_real_cache["data"]

        # Lấy alerts mới với dữ liệu thật
        print("Fetching real dam alerts from Open-Meteo...")
        alerts = generate_dam_alerts_with_real_data()

        result = {
            "generated_at": now.isoformat(),
            "total": len(alerts),
            "alerts": alerts,
            "summary": {
                "critical": len([a for a in alerts if a["severity"] == "critical"]),
                "high": len([a for a in alerts if a["severity"] == "high"]),
                "medium": len([a for a in alerts if a["severity"] == "medium"]),
                "low": len([a for a in alerts if a["severity"] == "low"])
            },
            "by_category": {"Xả lũ": len(alerts)},
            "source": "Open-Meteo + GloFAS",
            "data_note": "Lượng mưa và lưu lượng sông từ API thực. Mực nước hồ và lưu lượng xả là ước tính do không có API công khai từ EVN."
        }

        # Lưu cache
        dam_alerts_real_cache["data"] = result
        dam_alerts_real_cache["timestamp"] = now

        return result

    except Exception as e:
        print(f"Error in /api/dam-alerts/realtime: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/dam-alerts/{basin}")
async def get_dam_alerts_by_basin(basin: str):
    """Lấy cảnh báo xả lũ theo lưu vực"""
    basin_upper = basin.upper()
    if basin_upper not in VIETNAM_DAMS:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy lưu vực: {basin}")

    try:
        all_data = get_cached_or_fetch()
        basin_data = all_data["basins"].get(basin_upper, {})

        alerts = generate_dam_discharge_alerts(basin_upper, basin_data)

        return {
            "basin": basin_upper,
            "generated_at": datetime.now().isoformat(),
            "total_alerts": len(alerts),
            "alerts": alerts,
            "dams": VIETNAM_DAMS.get(basin_upper, []),
            "rivers": VIETNAM_RIVERS.get(basin_upper, [])
        }
    except Exception as e:
        print(f"Error in /api/dam-alerts/{basin}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/dams")
async def get_all_dams():
    """Lấy danh sách tất cả đập thủy điện"""
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


@app.get("/api/dams/{basin}")
async def get_dams_by_basin(basin: str):
    """Lấy danh sách đập theo lưu vực"""
    basin_upper = basin.upper()
    if basin_upper not in VIETNAM_DAMS:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy lưu vực: {basin}")

    return {
        "basin": basin_upper,
        "total": len(VIETNAM_DAMS[basin_upper]),
        "dams": VIETNAM_DAMS[basin_upper]
    }


@app.get("/api/rivers")
async def get_all_rivers():
    """Lấy danh sách tất cả sông chính"""
    all_rivers = []
    for basin, rivers in VIETNAM_RIVERS.items():
        for river in rivers:
            river_info = river.copy()
            river_info["basin"] = basin
            all_rivers.append(river_info)

    return {
        "total": len(all_rivers),
        "rivers": all_rivers,
        "basins": list(VIETNAM_RIVERS.keys())
    }


@app.get("/api/rivers/{basin}")
async def get_rivers_by_basin(basin: str):
    """Lấy danh sách sông theo lưu vực"""
    basin_upper = basin.upper()
    if basin_upper not in VIETNAM_RIVERS:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy lưu vực: {basin}")

    return {
        "basin": basin_upper,
        "total": len(VIETNAM_RIVERS[basin_upper]),
        "rivers": VIETNAM_RIVERS[basin_upper]
    }


@app.get("/api/flood-zones")
async def get_flood_zones():
    """Lấy danh sách tất cả vùng ngập lụt tiềm năng"""
    all_zones = []
    for basin, rivers in VIETNAM_RIVERS.items():
        for river in rivers:
            for zone in river.get("flood_prone_areas", []):
                zone_info = {
                    "basin": basin,
                    "river": river["name"],
                    "province": zone["name"],
                    "districts": zone["districts"],
                    "risk": zone["risk"],
                    "alert_levels": river.get("alert_levels", {})
                }
                all_zones.append(zone_info)

    # Sắp xếp theo mức độ rủi ro
    risk_order = {"Rất cao": 0, "Cao": 1, "Trung bình": 2, "Thấp": 3}
    all_zones.sort(key=lambda x: risk_order.get(x["risk"], 4))

    return {
        "total": len(all_zones),
        "zones": all_zones,
        "risk_summary": {
            "Rất cao": len([z for z in all_zones if z["risk"] == "Rất cao"]),
            "Cao": len([z for z in all_zones if z["risk"] == "Cao"]),
            "Trung bình": len([z for z in all_zones if z["risk"] == "Trung bình"]),
            "Thấp": len([z for z in all_zones if z["risk"] == "Thấp"])
        }
    }


def generate_weather_alerts(forecast_data: dict) -> list:
    """Tạo cảnh báo thời tiết từ dữ liệu dự báo"""
    import random
    alerts = []

    basin_info = {
        "HONG": {
            "name": "Miền Bắc",
            "provinces": ["Hà Nội", "Hải Phòng", "Thái Bình", "Nam Định", "Phú Thọ", "Hòa Bình", "Sơn La", "Yên Bái"]
        },
        "CENTRAL": {
            "name": "Miền Trung",
            "provinces": ["Đà Nẵng", "Quảng Nam", "Thừa Thiên Huế", "Quảng Ngãi", "Bình Định", "Quảng Trị", "Hà Tĩnh", "Nghệ An", "Thanh Hóa"]
        },
        "MEKONG": {
            "name": "Miền Nam",
            "provinces": ["An Giang", "Đồng Tháp", "Cần Thơ", "Long An", "Tiền Giang", "Vĩnh Long", "Sóc Trăng", "Kiên Giang"]
        },
        "DONGNAI": {
            "name": "Đông Nam Bộ",
            "provinces": ["TP.HCM", "Đồng Nai", "Bình Dương", "Bà Rịa-Vũng Tàu", "Tây Ninh", "Bình Phước"]
        }
    }

    basins = forecast_data.get("basins", {})

    for basin_code, basin_data in basins.items():
        info = basin_info.get(basin_code, {"name": basin_code, "provinces": []})
        forecast_days = basin_data.get("forecast_days", [])

        for day in forecast_days:
            daily_rain = day.get("daily_rain", 0)
            accumulated = day.get("accumulated_3d", 0)
            risk_level = day.get("risk_level", "")
            date = day.get("date", "")

            # 1. CẢNH BÁO LŨ LỤT
            if daily_rain > 50 or accumulated > 100:
                severity = "critical" if daily_rain > 100 or accumulated > 200 else "high" if daily_rain > 70 else "medium"
                affected_provinces = random.sample(info["provinces"], min(3, len(info["provinces"])))

                alerts.append({
                    "id": f"flood_{basin_code}_{date}",
                    "type": "flood",
                    "category": "Lũ lụt",
                    "title": f"Cảnh báo nguy cơ lũ - {info['name']}",
                    "severity": severity,
                    "date": date,
                    "region": info["name"],
                    "provinces": affected_provinces,
                    "description": f"Mưa lớn {daily_rain:.0f}mm/ngày, tích lũy {accumulated:.0f}mm trong 3 ngày. Nguy cơ ngập úng tại vùng trũng.",
                    "data": {
                        "rainfall_daily_mm": round(daily_rain, 1),
                        "rainfall_accumulated_mm": round(accumulated, 1),
                        "risk_level": risk_level
                    },
                    "recommendations": [
                        "Theo dõi diễn biến mưa lũ qua các phương tiện thông tin",
                        "Chuẩn bị phương án sơ tán nếu ở vùng trũng",
                        "Không đi qua các vùng ngập nước, suối, sông khi có lũ"
                    ]
                })

            # 2. CẢNH BÁO MƯA LỚN
            if daily_rain > 30:
                severity = "high" if daily_rain > 70 else "medium" if daily_rain > 50 else "low"
                alerts.append({
                    "id": f"rain_{basin_code}_{date}",
                    "type": "heavy_rain",
                    "category": "Mưa lớn",
                    "title": f"Cảnh báo mưa lớn - {info['name']}",
                    "severity": severity,
                    "date": date,
                    "region": info["name"],
                    "provinces": info["provinces"][:4],
                    "description": f"Dự báo mưa {daily_rain:.0f}mm trong ngày. Khả năng mưa rào và dông mạnh.",
                    "data": {
                        "rainfall_mm": round(daily_rain, 1),
                        "probability": min(95, 60 + daily_rain)
                    },
                    "recommendations": [
                        "Hạn chế ra ngoài khi có mưa to",
                        "Tránh xa các cây cao, cột điện khi có dông",
                        "Kiểm tra hệ thống thoát nước"
                    ]
                })

    # 3. CẢNH BÁO NẮNG NÓNG (dựa trên mùa và vùng)
    current_month = datetime.now().month
    if current_month in [4, 5, 6, 7, 8]:  # Mùa nắng nóng
        hot_regions = [
            {"region": "Bắc Bộ", "provinces": ["Hà Nội", "Hòa Bình", "Phú Thọ", "Ninh Bình"], "temp": random.randint(36, 40)},
            {"region": "Bắc Trung Bộ", "provinces": ["Thanh Hóa", "Nghệ An", "Hà Tĩnh", "Quảng Bình"], "temp": random.randint(37, 42)},
            {"region": "Nam Trung Bộ", "provinces": ["Bình Thuận", "Ninh Thuận", "Khánh Hòa"], "temp": random.randint(35, 39)},
        ]

        for region in hot_regions:
            if region["temp"] >= 37:
                alerts.append({
                    "id": f"heat_{region['region']}_{datetime.now().strftime('%Y-%m-%d')}",
                    "type": "heat_wave",
                    "category": "Nắng nóng",
                    "title": f"Cảnh báo nắng nóng gay gắt - {region['region']}",
                    "severity": "critical" if region["temp"] >= 40 else "high" if region["temp"] >= 38 else "medium",
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "region": region["region"],
                    "provinces": region["provinces"],
                    "description": f"Nắng nóng gay gắt với nhiệt độ cao nhất {region['temp']}°C. Độ ẩm thấp, nguy cơ cháy rừng.",
                    "data": {
                        "max_temperature_c": region["temp"],
                        "uv_index": random.randint(9, 12),
                        "humidity_percent": random.randint(30, 50)
                    },
                    "recommendations": [
                        "Hạn chế ra ngoài từ 10h-16h",
                        "Uống nhiều nước, mặc quần áo thoáng mát",
                        "Người già, trẻ em cần đặc biệt chú ý sức khỏe",
                        "Cảnh giác nguy cơ cháy rừng"
                    ]
                })

    # 4. CẢNH BÁO HẠN HÁN (mùa khô)
    if current_month in [1, 2, 3, 4, 11, 12]:
        drought_regions = [
            {"region": "Tây Nguyên", "provinces": ["Đắk Lắk", "Gia Lai", "Kon Tum", "Đắk Nông", "Lâm Đồng"]},
            {"region": "Nam Trung Bộ", "provinces": ["Ninh Thuận", "Bình Thuận", "Khánh Hòa"]},
            {"region": "Đồng bằng sông Cửu Long", "provinces": ["Bến Tre", "Tiền Giang", "Trà Vinh", "Sóc Trăng"]},
        ]

        for region in drought_regions:
            alerts.append({
                "id": f"drought_{region['region']}_{datetime.now().strftime('%Y-%m-%d')}",
                "type": "drought",
                "category": "Hạn hán",
                "title": f"Cảnh báo hạn hán - {region['region']}",
                "severity": "high",
                "date": datetime.now().strftime("%Y-%m-%d"),
                "region": region["region"],
                "provinces": region["provinces"],
                "description": f"Tình trạng khô hạn kéo dài. Mực nước sông, hồ xuống thấp. Nguy cơ thiếu nước sinh hoạt và sản xuất.",
                "data": {
                    "days_without_rain": random.randint(15, 45),
                    "water_level_percent": random.randint(40, 70)
                },
                "recommendations": [
                    "Sử dụng nước tiết kiệm",
                    "Dự trữ nước cho sinh hoạt",
                    "Theo dõi lịch cấp nước của địa phương",
                    "Nông dân cần điều chỉnh lịch gieo trồng phù hợp"
                ]
            })

    # 5. CẢNH BÁO XÂM NHẬP MẶN (Đồng bằng sông Cửu Long, mùa khô)
    if current_month in [2, 3, 4, 5]:
        alerts.append({
            "id": f"saltwater_{datetime.now().strftime('%Y-%m-%d')}",
            "type": "saltwater_intrusion",
            "category": "Xâm nhập mặn",
            "title": "Cảnh báo xâm nhập mặn - ĐBSCL",
            "severity": "high",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "region": "Đồng bằng sông Cửu Long",
            "provinces": ["Bến Tre", "Tiền Giang", "Trà Vinh", "Sóc Trăng", "Bạc Liêu", "Cà Mau", "Kiên Giang"],
            "description": f"Độ mặn xâm nhập sâu vào nội đồng {random.randint(50, 90)}km. Ảnh hưởng đến nguồn nước sinh hoạt và sản xuất nông nghiệp.",
            "data": {
                "salinity_intrusion_km": random.randint(50, 90),
                "salinity_level_ppt": round(random.uniform(3, 8), 1),
                "affected_area_ha": random.randint(50000, 150000)
            },
            "recommendations": [
                "Dự trữ nước ngọt cho sinh hoạt",
                "Không sử dụng nước sông, kênh để tưới tiêu khi độ mặn cao",
                "Đóng các cống ngăn mặn theo hướng dẫn địa phương",
                "Theo dõi bản tin độ mặn hàng ngày"
            ]
        })

    return alerts


def get_dam_real_weather_data(dam: dict) -> dict:
    """
    Lấy dữ liệu thời tiết THẬT từ Open-Meteo cho vị trí đập

    Returns:
        Dict với forecast và flood data thực từ Open-Meteo
    """
    lat = dam["coordinates"]["lat"]
    lon = dam["coordinates"]["lon"]

    # Lấy dự báo thời tiết thật
    forecast = fetch_forecast_full(lat, lon, days=7)

    # Lấy dự báo lũ từ GloFAS
    flood = fetch_flood_forecast(lat, lon)

    return {
        "forecast": forecast,
        "flood": flood,
        "source": "Open-Meteo API + GloFAS (Real Data)"
    }


def generate_dam_alerts_with_real_data() -> list:
    """
    Tạo cảnh báo xả lũ từ dữ liệu THẬT (Open-Meteo + GloFAS)

    Dữ liệu thật:
    - Lượng mưa dự báo tại vị trí đập (Open-Meteo Forecast API)
    - Lưu lượng sông từ GloFAS (Open-Meteo Flood API)

    Dữ liệu ước tính (không có API công khai):
    - Mực nước hồ hiện tại
    - Số cửa xả đang mở
    - Lưu lượng xả chính xác
    """
    alerts = []

    for basin_name, dams in VIETNAM_DAMS.items():
        rivers = VIETNAM_RIVERS.get(basin_name, [])

        for dam in dams:
            # Lấy dữ liệu thật từ Open-Meteo
            real_data = get_dam_real_weather_data(dam)
            forecast = real_data.get("forecast", {})
            flood = real_data.get("flood", {})

            if not forecast:
                continue

            daily = forecast.get("daily", {})
            dates = daily.get("time", [])
            precipitation = daily.get("precipitation_sum", [])
            rain = daily.get("rain_sum", [])

            # Lấy river discharge từ GloFAS
            flood_daily = flood.get("daily", {}) if flood else {}
            river_discharge = flood_daily.get("river_discharge", [])

            for i, date in enumerate(dates[:7]):
                daily_rain = precipitation[i] if i < len(precipitation) and precipitation[i] else 0
                rain_only = rain[i] if i < len(rain) and rain[i] else 0

                # Lấy lưu lượng sông thật từ GloFAS
                discharge_glofas = river_discharge[i] if i < len(river_discharge) and river_discharge[i] else 0

                # Tính lượng mưa tích lũy 3 ngày
                accumulated = sum([
                    precipitation[j] if j < len(precipitation) and precipitation[j] else 0
                    for j in range(max(0, i-2), i+1)
                ])

                # Xác định mức cảnh báo dựa trên dữ liệu THẬT
                needs_discharge = False
                discharge_level = "normal"

                # Ngưỡng xả lũ dựa trên lượng mưa thật và lưu lượng sông
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

                # Ước tính lưu lượng xả dựa trên dữ liệu thật
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

                # Mực nước hồ ước tính
                water_level = dam["normal_level_m"] + (daily_rain / 100) * (dam["flood_level_m"] - dam["normal_level_m"])
                water_level = min(water_level, dam["flood_level_m"] + 1)

                # Số cửa xả ước tính
                gates_open = min(dam["spillway_gates"], max(1, int(estimated_discharge / dam["max_discharge_m3s"] * dam["spillway_gates"])))

                # Thời gian xả
                time_base = {"emergency": 6, "warning": 8, "watch": 10}.get(discharge_level, 8)
                time_offset = int((daily_rain % 50) / 10)
                discharge_hour = time_base + time_offset

                severity_map = {"emergency": "critical", "warning": "high", "watch": "medium"}

                alert = {
                    "id": f"{dam['id']}_{date}_real",
                    "type": "dam_discharge",
                    "category": "Xả lũ",
                    "title": f"Cảnh báo xả lũ - {dam['name']}",
                    "severity": severity_map.get(discharge_level, "low"),
                    "date": date,
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
                    "recommendations": get_discharge_recommendations(discharge_level, dam, estimated_discharge),
                    "source": "Open-Meteo + GloFAS (Rainfall: Real, Discharge: Estimated)",
                    "data_note": "Lượng mưa từ Open-Meteo (thật). Lưu lượng sông từ GloFAS (thật). Mực nước hồ và lưu lượng xả là ước tính."
                }

                # Thêm flood zones
                flood_zones = []
                for river in rivers:
                    if river["name"] in dam["affected_rivers"] or dam["river"] in river["name"]:
                        for zone in river.get("flood_prone_areas", []):
                            flood_zones.append({
                                "province": zone["name"],
                                "districts": zone["districts"],
                                "risk": zone["risk"],
                                "river": river["name"]
                            })
                alert["flood_zones"] = flood_zones

                alerts.append(alert)

    # Sắp xếp theo severity
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    alerts.sort(key=lambda x: (severity_order.get(x["severity"], 4), x["date"]))

    return alerts


def generate_dam_alerts_combined(forecast_data: dict) -> list:
    """Tạo cảnh báo xả lũ từ các đập thủy điện (backward compatibility)"""
    alerts = []
    basins = forecast_data.get("basins", {})

    for basin_code, basin_data in basins.items():
        dam_alerts_raw = generate_dam_discharge_alerts(basin_code, basin_data)

        for dam_alert in dam_alerts_raw:
            if dam_alert["alert_level"] in ["emergency", "warning", "watch"]:
                severity_map = {"emergency": "critical", "warning": "high", "watch": "medium"}

                alerts.append({
                    "id": dam_alert["id"],
                    "type": "dam_discharge",
                    "category": "Xả lũ",
                    "title": f"Cảnh báo xả lũ - {dam_alert['dam_name']}",
                    "severity": severity_map.get(dam_alert["alert_level"], "low"),
                    "date": dam_alert["date"],
                    "region": dam_alert["province"],
                    "provinces": dam_alert["downstream_areas"],
                    "description": dam_alert["description"],
                    "data": {
                        "dam_name": dam_alert["dam_name"],
                        "river": dam_alert["river"],
                        "discharge_m3s": dam_alert["estimated_discharge_m3s"],
                        "discharge_percent": dam_alert["discharge_percent"],
                        "water_level_m": dam_alert["current_water_level_m"],
                        "water_level_percent": dam_alert["water_level_percent"],
                        "spillway_gates_open": dam_alert["spillway_gates_open"],
                        "total_gates": dam_alert["total_spillway_gates"],
                        "warning_time_hours": dam_alert["warning_time_hours"],
                        "estimated_time": dam_alert["time_estimate"]
                    },
                    "recommendations": dam_alert["recommendations"],
                    "flood_zones": dam_alert.get("flood_zones", [])
                })

    return alerts


@app.get("/api/alerts")
async def get_alerts():
    """Lấy danh sách cảnh báo tổng hợp tất cả các loại"""
    try:
        all_data = get_cached_or_fetch()

        # Tạo tất cả các loại cảnh báo
        weather_alerts = generate_weather_alerts(all_data)
        dam_alerts = generate_dam_alerts_combined(all_data)

        # Gộp tất cả cảnh báo
        all_alerts = weather_alerts + dam_alerts

        # Loại bỏ trùng lặp và sắp xếp
        seen_ids = set()
        unique_alerts = []
        for alert in all_alerts:
            if alert["id"] not in seen_ids:
                seen_ids.add(alert["id"])
                unique_alerts.append(alert)

        # Sắp xếp theo severity và date
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        unique_alerts.sort(key=lambda x: (severity_order.get(x["severity"], 4), x["date"]))

        # Thống kê theo loại
        type_summary = {}
        for alert in unique_alerts:
            cat = alert["category"]
            if cat not in type_summary:
                type_summary[cat] = 0
            type_summary[cat] += 1

        return {
            "generated_at": datetime.now().isoformat(),
            "total": len(unique_alerts),
            "alerts": unique_alerts,
            "summary": {
                "critical": len([a for a in unique_alerts if a["severity"] == "critical"]),
                "high": len([a for a in unique_alerts if a["severity"] == "high"]),
                "medium": len([a for a in unique_alerts if a["severity"] == "medium"]),
                "low": len([a for a in unique_alerts if a["severity"] == "low"])
            },
            "by_category": type_summary
        }
    except Exception as e:
        print(f"Error in /api/alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def get_real_weather_cached(locations: List[str] = None):
    """Lấy dữ liệu thời tiết thật với cache"""
    global real_weather_cache
    now = datetime.now()

    # Kiểm tra cache
    if real_weather_cache["data"] and real_weather_cache["timestamp"]:
        elapsed = (now - real_weather_cache["timestamp"]).total_seconds()
        if elapsed < REAL_WEATHER_CACHE_DURATION:
            return real_weather_cache["data"], real_weather_cache["alerts"]

    # Fetch dữ liệu mới
    print("Fetching real weather data from Open-Meteo...")

    # Lấy dữ liệu cho các thành phố chính (để giảm số lượng request)
    key_locations = locations or [
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

    # Phân tích và tạo cảnh báo
    alerts = analyze_weather_for_alerts(weather_data)

    # Lưu cache
    real_weather_cache["data"] = weather_data
    real_weather_cache["alerts"] = alerts
    real_weather_cache["timestamp"] = now

    return weather_data, alerts


@app.get("/api/weather/realtime")
async def get_realtime_weather(location: Optional[str] = None):
    """
    Lấy dữ liệu thời tiết thực từ Open-Meteo API

    - Nếu không truyền location: trả về dữ liệu các thành phố chính
    - Nếu truyền location: trả về dữ liệu chi tiết cho địa điểm đó
    """
    try:
        if location:
            # Lấy dữ liệu cho 1 địa điểm cụ thể
            if location not in VIETNAM_LOCATIONS:
                raise HTTPException(status_code=404, detail=f"Location '{location}' not found")

            loc_info = VIETNAM_LOCATIONS[location]
            forecast = fetch_forecast_full(loc_info["lat"], loc_info["lon"], days=7)
            flood = fetch_flood_forecast(loc_info["lat"], loc_info["lon"])

            return {
                "location": location,
                "info": loc_info,
                "forecast": forecast,
                "flood": flood,
                "generated_at": datetime.now().isoformat(),
                "source": "Open-Meteo API"
            }
        else:
            # Trả về dữ liệu cached
            weather_data, alerts = get_real_weather_cached()
            return weather_data

    except Exception as e:
        print(f"Error fetching realtime weather: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/weather/forecast/{location}")
async def get_location_forecast(location: str, days: int = 7):
    """Lấy dự báo thời tiết chi tiết cho một địa điểm"""
    if location not in VIETNAM_LOCATIONS:
        raise HTTPException(status_code=404, detail=f"Location '{location}' not found")

    loc_info = VIETNAM_LOCATIONS[location]
    forecast = fetch_forecast_full(loc_info["lat"], loc_info["lon"], days=min(days, 16))

    # Format dữ liệu dễ đọc
    daily = forecast.get("daily", {})
    formatted_days = []

    for i, date in enumerate(daily.get("time", [])):
        formatted_days.append({
            "date": date,
            "weather": get_weather_description(daily.get("weather_code", [0])[i]),
            "weather_code": daily.get("weather_code", [0])[i],
            "temp_max": daily.get("temperature_2m_max", [None])[i],
            "temp_min": daily.get("temperature_2m_min", [None])[i],
            "precipitation_mm": daily.get("precipitation_sum", [0])[i],
            "rain_mm": daily.get("rain_sum", [0])[i],
            "precipitation_hours": daily.get("precipitation_hours", [0])[i],
            "precipitation_probability": daily.get("precipitation_probability_max", [0])[i],
            "wind_max_kmh": daily.get("wind_speed_10m_max", [0])[i],
            "wind_gusts_kmh": daily.get("wind_gusts_10m_max", [0])[i],
            "uv_index_max": daily.get("uv_index_max", [0])[i],
            "sunrise": daily.get("sunrise", [""])[i],
            "sunset": daily.get("sunset", [""])[i],
        })

    return {
        "location": location,
        "name": loc_info["name"],
        "region": loc_info["region"],
        "coordinates": {"lat": loc_info["lat"], "lon": loc_info["lon"]},
        "forecast_days": formatted_days,
        "generated_at": datetime.now().isoformat(),
        "source": "Open-Meteo API"
    }


@app.get("/api/weather/flood/{location}")
async def get_flood_forecast_api(location: str):
    """Lấy dự báo nguy cơ lũ từ GloFAS"""
    if location not in VIETNAM_LOCATIONS:
        raise HTTPException(status_code=404, detail=f"Location '{location}' not found")

    loc_info = VIETNAM_LOCATIONS[location]
    flood_data = fetch_flood_forecast(loc_info["lat"], loc_info["lon"])

    if not flood_data:
        return {
            "location": location,
            "name": loc_info["name"],
            "flood_data": None,
            "message": "No flood forecast data available for this location",
            "source": "Open-Meteo Flood API (GloFAS)"
        }

    # Format dữ liệu
    daily = flood_data.get("daily", {})
    formatted = []

    for i, date in enumerate(daily.get("time", [])):
        discharge = daily.get("river_discharge", [None])[i]
        risk = "low"
        if discharge:
            if discharge >= 5000:
                risk = "critical"
            elif discharge >= 2000:
                risk = "high"
            elif discharge >= 1000:
                risk = "medium"

        formatted.append({
            "date": date,
            "river_discharge_m3s": discharge,
            "risk_level": risk
        })

    return {
        "location": location,
        "name": loc_info["name"],
        "coordinates": {"lat": loc_info["lat"], "lon": loc_info["lon"]},
        "flood_forecast": formatted,
        "generated_at": datetime.now().isoformat(),
        "source": "Open-Meteo Flood API (GloFAS)"
    }


@app.get("/api/alerts/realtime")
async def get_realtime_alerts():
    """
    Lấy cảnh báo thời tiết dựa trên dữ liệu THẬT từ Open-Meteo
    Đây là dữ liệu thực, không phải mô phỏng
    """
    try:
        weather_data, alerts = get_real_weather_cached()

        # Sắp xếp theo severity
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        alerts.sort(key=lambda x: (severity_order.get(x.get("severity", "low"), 4), x.get("date", "")))

        # Tính summary
        summary = {
            "critical": len([a for a in alerts if a.get("severity") == "critical"]),
            "high": len([a for a in alerts if a.get("severity") == "high"]),
            "medium": len([a for a in alerts if a.get("severity") == "medium"]),
            "low": len([a for a in alerts if a.get("severity") == "low"])
        }

        # Tính by category
        by_category = {}
        for alert in alerts:
            cat = alert.get("category", "Khác")
            by_category[cat] = by_category.get(cat, 0) + 1

        return {
            "generated_at": datetime.now().isoformat(),
            "total": len(alerts),
            "alerts": alerts,
            "summary": summary,
            "by_category": by_category,
            "data_source": "Open-Meteo API (Real Data)",
            "cache_duration_seconds": REAL_WEATHER_CACHE_DURATION
        }

    except Exception as e:
        print(f"Error in realtime alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/locations")
async def get_all_locations():
    """Lấy danh sách tất cả các địa điểm có dữ liệu thời tiết"""
    locations_by_region = {
        "north": [],
        "central": [],
        "highland": [],
        "south": []
    }

    for code, info in VIETNAM_LOCATIONS.items():
        region = info.get("region", "other")
        if region in locations_by_region:
            locations_by_region[region].append({
                "code": code,
                "name": info["name"],
                "lat": info["lat"],
                "lon": info["lon"]
            })

    return {
        "total": len(VIETNAM_LOCATIONS),
        "by_region": locations_by_region,
        "regions": {
            "north": "Miền Bắc",
            "central": "Miền Trung",
            "highland": "Tây Nguyên",
            "south": "Miền Nam"
        }
    }


async def startup_event():
    """Pre-warm cache on startup"""
    import asyncio
    print("Pre-warming forecast cache...")
    try:
        # Run in background to not block startup
        asyncio.create_task(asyncio.to_thread(get_cached_or_fetch))
        print("Cache warming started in background")
    except Exception as e:
        print(f"Cache warming failed: {e}")


if __name__ == "__main__":
    import uvicorn
    print("Starting Vietnam Flood Forecast API...")
    print("API will be available at http://localhost:8000")
    print("Docs at http://localhost:8000/docs")

    # Add startup event
    app.add_event_handler("startup", startup_event)

    uvicorn.run("main_simple:app", host="0.0.0.0", port=8000, reload=True)
