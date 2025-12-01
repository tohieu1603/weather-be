#!/usr/bin/env python3
"""
Rainfall Analysis Controller - API routes for rainfall analysis by location
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
import requests

from weather_api import OPEN_METEO_FORECAST, VIETNAM_LOCATIONS

router = APIRouter(prefix="/api/rainfall", tags=["Rainfall Analysis"])

# Nominatim API for reverse geocoding (free, no API key required)
NOMINATIM_BASE_URL = "https://nominatim.openstreetmap.org"
NOMINATIM_REVERSE_URL = f"{NOMINATIM_BASE_URL}/reverse"
NOMINATIM_SEARCH_URL = f"{NOMINATIM_BASE_URL}/search"

# Region descriptions with climate and geography info
REGION_INFO = {
    "north": {
        "name": "Miền Bắc",
        "climate": "Khí hậu nhiệt đới gió mùa có mùa đông lạnh. Mùa mưa từ tháng 5-10, mùa khô từ tháng 11-4.",
        "terrain": "Đồng bằng sông Hồng, núi cao phía Bắc và Tây Bắc. Địa hình trũng, dễ ngập khi mưa lớn.",
        "flood_risk": "Cao vào mùa mưa (tháng 7-9). Các khu vực hay ngập: ngoại thành Hà Nội, vùng trũng đồng bằng.",
        "avg_annual_rainfall": "1400-2000mm/năm"
    },
    "central": {
        "name": "Miền Trung",
        "climate": "Khí hậu nhiệt đới gió mùa, chịu ảnh hưởng bão từ Biển Đông. Mùa mưa từ tháng 9-12.",
        "terrain": "Dải đất hẹp ven biển, dãy Trường Sơn phía Tây. Sông ngắn, dốc, lũ lên nhanh.",
        "flood_risk": "Rất cao vào mùa bão (tháng 9-11). Lũ quét, sạt lở đất thường xuyên. Các tỉnh hay ngập: Quảng Bình, Quảng Trị, Thừa Thiên Huế, Quảng Nam, Quảng Ngãi.",
        "avg_annual_rainfall": "2000-3500mm/năm"
    },
    "south": {
        "name": "Miền Nam",
        "climate": "Khí hậu nhiệt đới 2 mùa rõ rệt: mùa mưa (tháng 5-11) và mùa khô (tháng 12-4).",
        "terrain": "Đồng bằng sông Cửu Long bằng phẳng, thấp trũng. Hệ thống kênh rạch chằng chịt.",
        "flood_risk": "Cao vào tháng 9-10 do nước lũ từ thượng nguồn Mekong. Ngập úng đô thị phổ biến ở TP.HCM.",
        "avg_annual_rainfall": "1800-2500mm/năm"
    }
}

# Province-specific info for detailed analysis
PROVINCE_INFO = {
    "hanoi": {
        "description": "Thủ đô Việt Nam, nằm ở trung tâm đồng bằng sông Hồng",
        "population": "~8.5 triệu người",
        "area": "3,358 km²",
        "elevation": "5-20m so với mực nước biển",
        "flood_zones": ["Quốc Oai", "Chương Mỹ", "Mỹ Đức", "Ứng Hòa", "Phú Xuyên"],
        "rivers": ["Sông Hồng", "Sông Đuống", "Sông Đáy", "Sông Nhuệ"],
        "notes": "Khu vực ngoại thành phía Tây và Nam thường xuyên ngập khi có mưa lớn kết hợp xả lũ"
    },
    "ho_chi_minh": {
        "description": "Thành phố lớn nhất Việt Nam, trung tâm kinh tế phía Nam",
        "population": "~9.5 triệu người",
        "area": "2,095 km²",
        "elevation": "0-32m, phần lớn <10m",
        "flood_zones": ["Quận 7", "Bình Chánh", "Nhà Bè", "Thủ Đức", "Quận 12"],
        "rivers": ["Sông Sài Gòn", "Sông Đồng Nai", "Kênh Tẻ", "Kênh Đôi"],
        "notes": "Ngập úng đô thị nghiêm trọng do triều cường kết hợp mưa lớn. Hệ thống thoát nước quá tải"
    },
    "da_nang": {
        "description": "Thành phố trực thuộc TW, trung tâm kinh tế miền Trung",
        "population": "~1.2 triệu người",
        "area": "1,285 km²",
        "elevation": "0-1,487m (Bà Nà)",
        "flood_zones": ["Hòa Vang", "Cẩm Lệ", "Liên Chiểu"],
        "rivers": ["Sông Hàn", "Sông Cu Đê", "Sông Túy Loan"],
        "notes": "Chịu ảnh hưởng trực tiếp của bão. Lũ ống, lũ quét từ vùng núi phía Tây"
    },
    "hue": {
        "description": "Cố đô, di sản văn hóa thế giới UNESCO",
        "population": "~350,000 người",
        "area": "5,033 km²",
        "elevation": "0-1,774m",
        "flood_zones": ["TP Huế", "Phong Điền", "Quảng Điền", "Hương Trà"],
        "rivers": ["Sông Hương", "Sông Bồ", "Sông Ô Lâu"],
        "notes": "Một trong những nơi mưa nhiều nhất VN. Lũ lụt nghiêm trọng vào tháng 10-11"
    },
    "can_tho": {
        "description": "Thành phố lớn nhất đồng bằng sông Cửu Long",
        "population": "~1.3 triệu người",
        "area": "1,439 km²",
        "elevation": "0.8-1.5m so với mực nước biển",
        "flood_zones": ["Thốt Nốt", "Vĩnh Thạnh", "Cờ Đỏ", "Phong Điền"],
        "rivers": ["Sông Hậu", "Sông Cần Thơ"],
        "notes": "Chịu ảnh hưởng lũ từ thượng nguồn Mekong và triều cường"
    }
}


def search_location(query: str, limit: int = 10) -> list:
    """
    Search for locations by name using Nominatim
    Returns list of matching locations with coordinates
    """
    try:
        params = {
            "q": f"{query}, Vietnam",
            "format": "json",
            "addressdetails": 1,
            "limit": limit,
            "accept-language": "vi",
            "countrycodes": "vn"
        }
        headers = {
            "User-Agent": "VietnamFloodForecast/1.0"
        }
        resp = requests.get(NOMINATIM_SEARCH_URL, params=params, headers=headers, timeout=10)
        resp.raise_for_status()
        results = resp.json()

        locations = []
        for r in results:
            addr = r.get("address", {})
            locations.append({
                "display_name": r.get("display_name", ""),
                "lat": float(r.get("lat", 0)),
                "lon": float(r.get("lon", 0)),
                "type": r.get("type", ""),
                "ward": addr.get("quarter") or addr.get("suburb") or addr.get("village") or "",
                "district": addr.get("city_district") or addr.get("district") or addr.get("county") or "",
                "province": addr.get("city") or addr.get("state") or addr.get("province") or "",
            })
        return locations
    except Exception as e:
        print(f"Search location error: {e}")
        return []


def get_administrative_divisions(province_code: str) -> dict:
    """
    Get districts and wards for a province using Nominatim
    """
    if province_code not in VIETNAM_LOCATIONS:
        return {"districts": []}

    loc = VIETNAM_LOCATIONS[province_code]
    province_name = loc["name"]

    try:
        # Search for districts in this province
        params = {
            "q": f"quận huyện {province_name}, Vietnam",
            "format": "json",
            "addressdetails": 1,
            "limit": 30,
            "accept-language": "vi",
            "countrycodes": "vn"
        }
        headers = {
            "User-Agent": "VietnamFloodForecast/1.0"
        }
        resp = requests.get(NOMINATIM_SEARCH_URL, params=params, headers=headers, timeout=15)
        resp.raise_for_status()
        results = resp.json()

        districts = {}
        for r in results:
            addr = r.get("address", {})
            district_name = addr.get("city_district") or addr.get("district") or addr.get("county") or ""
            if district_name and district_name not in districts:
                districts[district_name] = {
                    "name": district_name,
                    "lat": float(r.get("lat", 0)),
                    "lon": float(r.get("lon", 0)),
                    "type": r.get("type", "")
                }

        return {
            "province": province_name,
            "province_code": province_code,
            "districts": list(districts.values())
        }
    except Exception as e:
        print(f"Get divisions error: {e}")
        return {"province": province_name, "province_code": province_code, "districts": []}


def reverse_geocode(lat: float, lon: float) -> dict:
    """
    Reverse geocode coordinates to get location details (ward, district, province)
    Uses Nominatim (OpenStreetMap) API
    """
    try:
        params = {
            "lat": lat,
            "lon": lon,
            "format": "json",
            "addressdetails": 1,
            "accept-language": "vi"
        }
        headers = {
            "User-Agent": "VietnamFloodForecast/1.0"
        }
        resp = requests.get(NOMINATIM_REVERSE_URL, params=params, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        address = data.get("address", {})

        return {
            "display_name": data.get("display_name", ""),
            "ward": address.get("quarter") or address.get("suburb") or address.get("village") or "",
            "district": address.get("city_district") or address.get("district") or address.get("county") or "",
            "province": address.get("city") or address.get("state") or address.get("province") or "",
            "country": address.get("country", "Vietnam"),
            "raw_address": address
        }
    except Exception as e:
        print(f"Reverse geocoding error: {e}")
        return {
            "display_name": f"{lat}, {lon}",
            "ward": "",
            "district": "",
            "province": "",
            "country": "Vietnam",
            "raw_address": {}
        }


def fetch_rainfall_data(lat: float, lon: float, days: int = 7) -> dict:
    """
    Fetch comprehensive weather forecast data from Open-Meteo
    Including: rainfall, temperature, humidity, wind, UV index
    """
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "precipitation,rain,showers,precipitation_probability,temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m",
        "daily": "precipitation_sum,rain_sum,showers_sum,precipitation_hours,precipitation_probability_max,temperature_2m_max,temperature_2m_min,apparent_temperature_max,apparent_temperature_min,wind_speed_10m_max,wind_gusts_10m_max,wind_direction_10m_dominant,uv_index_max,sunrise,sunset",
        "forecast_days": days,
        "timezone": "Asia/Ho_Chi_Minh",
    }

    try:
        resp = requests.get(OPEN_METEO_FORECAST, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"Error fetching rainfall data: {e}")
        return {}


def analyze_rainfall(data: dict) -> dict:
    """
    Analyze rainfall data and generate comprehensive insights
    Including: rainfall, temperature, humidity, wind analysis
    """
    daily = data.get("daily", {})
    hourly = data.get("hourly", {})

    dates = daily.get("time", [])
    precipitation_sum = daily.get("precipitation_sum", [])
    rain_sum = daily.get("rain_sum", [])
    precipitation_hours = daily.get("precipitation_hours", [])
    precipitation_prob_max = daily.get("precipitation_probability_max", [])

    # Temperature data
    temp_max = daily.get("temperature_2m_max", [])
    temp_min = daily.get("temperature_2m_min", [])
    apparent_temp_max = daily.get("apparent_temperature_max", [])
    apparent_temp_min = daily.get("apparent_temperature_min", [])

    # Wind data
    wind_speed_max = daily.get("wind_speed_10m_max", [])
    wind_gusts_max = daily.get("wind_gusts_10m_max", [])
    wind_direction = daily.get("wind_direction_10m_dominant", [])

    # UV and sun
    uv_index_max = daily.get("uv_index_max", [])
    sunrise = daily.get("sunrise", [])
    sunset = daily.get("sunset", [])

    # Calculate totals and averages
    total_rainfall = sum(p for p in precipitation_sum if p is not None)
    max_daily_rainfall = max(precipitation_sum) if precipitation_sum else 0
    max_day_index = precipitation_sum.index(max_daily_rainfall) if max_daily_rainfall > 0 else 0
    max_day_date = dates[max_day_index] if dates else ""

    avg_daily_rainfall = total_rainfall / len(precipitation_sum) if precipitation_sum else 0
    total_rain_hours = sum(h for h in precipitation_hours if h is not None)

    # Temperature stats
    avg_temp_max = sum(t for t in temp_max if t is not None) / len(temp_max) if temp_max else 0
    avg_temp_min = sum(t for t in temp_min if t is not None) / len(temp_min) if temp_min else 0
    max_temp = max(temp_max) if temp_max else 0
    min_temp = min(temp_min) if temp_min else 0

    # Wind stats
    max_wind = max(wind_speed_max) if wind_speed_max else 0
    max_gust = max(wind_gusts_max) if wind_gusts_max else 0

    # Risk assessment
    def get_risk_level(daily_rain: float) -> tuple:
        if daily_rain >= 100:
            return "very_high", "Rất cao", "Nguy cơ ngập úng nghiêm trọng"
        elif daily_rain >= 70:
            return "high", "Cao", "Có khả năng xảy ra ngập cục bộ"
        elif daily_rain >= 50:
            return "medium", "Trung bình", "Cần theo dõi tình hình"
        elif daily_rain >= 20:
            return "low", "Thấp", "Mưa vừa phải, ít ảnh hưởng"
        else:
            return "very_low", "Rất thấp", "Thời tiết bình thường"

    def get_wind_description(speed: float) -> str:
        if speed >= 62:
            return "Bão (cấp 8+)"
        elif speed >= 50:
            return "Gió rất mạnh (cấp 7)"
        elif speed >= 39:
            return "Gió mạnh (cấp 6)"
        elif speed >= 29:
            return "Gió khá mạnh (cấp 5)"
        elif speed >= 20:
            return "Gió vừa (cấp 4)"
        elif speed >= 12:
            return "Gió nhẹ (cấp 3)"
        else:
            return "Gió yếu (cấp 1-2)"

    def get_wind_direction_name(deg: float) -> str:
        directions = ["Bắc", "Đông Bắc", "Đông", "Đông Nam", "Nam", "Tây Nam", "Tây", "Tây Bắc"]
        idx = int((deg + 22.5) / 45) % 8
        return directions[idx]

    def get_uv_description(uv: float) -> str:
        if uv >= 11:
            return "Cực cao - Rất nguy hiểm"
        elif uv >= 8:
            return "Rất cao - Nguy hiểm"
        elif uv >= 6:
            return "Cao - Cần bảo vệ"
        elif uv >= 3:
            return "Trung bình"
        else:
            return "Thấp - An toàn"

    # Daily analysis with full weather info
    daily_analysis = []
    for i, date in enumerate(dates):
        precip = precipitation_sum[i] if i < len(precipitation_sum) else 0
        rain = rain_sum[i] if i < len(rain_sum) else 0
        hours = precipitation_hours[i] if i < len(precipitation_hours) else 0
        prob = precipitation_prob_max[i] if i < len(precipitation_prob_max) else 0

        t_max = temp_max[i] if i < len(temp_max) else None
        t_min = temp_min[i] if i < len(temp_min) else None
        at_max = apparent_temp_max[i] if i < len(apparent_temp_max) else None
        at_min = apparent_temp_min[i] if i < len(apparent_temp_min) else None

        w_speed = wind_speed_max[i] if i < len(wind_speed_max) else 0
        w_gust = wind_gusts_max[i] if i < len(wind_gusts_max) else 0
        w_dir = wind_direction[i] if i < len(wind_direction) else 0

        uv = uv_index_max[i] if i < len(uv_index_max) else 0
        sun_rise = sunrise[i] if i < len(sunrise) else ""
        sun_set = sunset[i] if i < len(sunset) else ""

        risk_code, risk_level, risk_desc = get_risk_level(precip or 0)

        daily_analysis.append({
            "date": date,
            "precipitation_mm": round(precip or 0, 1),
            "rain_mm": round(rain or 0, 1),
            "rain_hours": round(hours or 0, 1),
            "probability_percent": prob or 0,
            "risk_code": risk_code,
            "risk_level": risk_level,
            "risk_description": risk_desc,
            "temperature": {
                "max": round(t_max, 1) if t_max else None,
                "min": round(t_min, 1) if t_min else None,
                "feels_like_max": round(at_max, 1) if at_max else None,
                "feels_like_min": round(at_min, 1) if at_min else None
            },
            "wind": {
                "max_speed_kmh": round(w_speed, 1),
                "max_gust_kmh": round(w_gust, 1),
                "direction_deg": w_dir,
                "direction_name": get_wind_direction_name(w_dir) if w_dir else "",
                "description": get_wind_description(w_speed)
            },
            "uv_index": {
                "value": round(uv, 1) if uv else 0,
                "description": get_uv_description(uv) if uv else "Không có dữ liệu"
            },
            "sun": {
                "sunrise": sun_rise.split("T")[1][:5] if sun_rise and "T" in sun_rise else "",
                "sunset": sun_set.split("T")[1][:5] if sun_set and "T" in sun_set else ""
            }
        })

    # Hourly peak analysis (find peak hours)
    hourly_times = hourly.get("time", [])
    hourly_precip = hourly.get("precipitation", [])
    hourly_temp = hourly.get("temperature_2m", [])
    hourly_humidity = hourly.get("relative_humidity_2m", [])
    hourly_wind = hourly.get("wind_speed_10m", [])

    peak_hours = []
    for i, time in enumerate(hourly_times):
        precip = hourly_precip[i] if i < len(hourly_precip) else 0
        if precip and precip >= 5:  # Significant rainfall threshold
            peak_hours.append({
                "time": time,
                "precipitation_mm": round(precip, 1),
                "temperature": round(hourly_temp[i], 1) if i < len(hourly_temp) and hourly_temp[i] else None,
                "humidity": hourly_humidity[i] if i < len(hourly_humidity) else None,
                "wind_kmh": round(hourly_wind[i], 1) if i < len(hourly_wind) and hourly_wind[i] else None
            })

    # Sort peak hours by precipitation
    peak_hours.sort(key=lambda x: x["precipitation_mm"], reverse=True)
    peak_hours = peak_hours[:10]  # Top 10 peak hours

    # Overall risk for the period
    overall_risk_code, overall_risk_level, overall_risk_desc = get_risk_level(max_daily_rainfall)

    # Generate weather description text
    def generate_weather_description() -> str:
        parts = []

        # Temperature description
        if avg_temp_max >= 35:
            parts.append(f"Nắng nóng gay gắt (nhiệt độ cao nhất {max_temp:.0f}°C)")
        elif avg_temp_max >= 30:
            parts.append(f"Trời nóng (nhiệt độ {avg_temp_min:.0f}-{avg_temp_max:.0f}°C)")
        elif avg_temp_max >= 25:
            parts.append(f"Thời tiết mát mẻ (nhiệt độ {avg_temp_min:.0f}-{avg_temp_max:.0f}°C)")
        elif avg_temp_max >= 20:
            parts.append(f"Trời se lạnh (nhiệt độ {avg_temp_min:.0f}-{avg_temp_max:.0f}°C)")
        else:
            parts.append(f"Trời lạnh (nhiệt độ thấp nhất {min_temp:.0f}°C)")

        # Rainfall description
        if total_rainfall >= 100:
            parts.append(f"Mưa rất lớn với tổng lượng {total_rainfall:.0f}mm trong {len(dates)} ngày")
        elif total_rainfall >= 50:
            parts.append(f"Mưa vừa đến lớn, tổng lượng {total_rainfall:.0f}mm")
        elif total_rainfall >= 20:
            parts.append(f"Có mưa rải rác với tổng lượng {total_rainfall:.0f}mm")
        elif total_rainfall > 0:
            parts.append(f"Ít mưa, tổng lượng chỉ {total_rainfall:.1f}mm")
        else:
            parts.append("Không có mưa")

        # Wind description
        if max_wind >= 40:
            parts.append(f"Gió mạnh đến rất mạnh (tốc độ tối đa {max_wind:.0f}km/h)")
        elif max_wind >= 20:
            parts.append(f"Gió vừa phải (tốc độ {max_wind:.0f}km/h)")

        return ". ".join(parts) + "."

    # Recommendations
    recommendations = []
    if max_daily_rainfall >= 100:
        recommendations = [
            "🚨 Cảnh báo mưa rất lớn, có nguy cơ ngập úng nghiêm trọng",
            "🏠 Hạn chế ra ngoài trong thời gian mưa lớn",
            "📦 Di chuyển đồ đạc lên cao nếu ở vùng trũng",
            "📻 Theo dõi thông tin từ cơ quan chức năng",
            "🚗 Không lái xe qua vùng ngập sâu"
        ]
    elif max_daily_rainfall >= 70:
        recommendations = [
            "⚠️ Dự kiến mưa lớn, cần đề phòng ngập cục bộ",
            "🔧 Kiểm tra hệ thống thoát nước",
            "🚶 Tránh đi qua vùng ngập nước",
            "🔌 Cẩn thận với thiết bị điện khi mưa"
        ]
    elif max_daily_rainfall >= 50:
        recommendations = [
            "🌧️ Mưa vừa đến lớn, nên mang theo áo mưa",
            "🚗 Lái xe cẩn thận trên đường trơn",
            "⚡ Có thể có dông, tránh đứng dưới cây cao"
        ]
    elif max_daily_rainfall >= 20:
        recommendations = [
            "☔ Có mưa rải rác, chuẩn bị ô/áo mưa khi ra ngoài"
        ]
    else:
        recommendations = [
            "☀️ Thời tiết thuận lợi, ít khả năng mưa"
        ]

    # Add temperature-based recommendations
    if avg_temp_max >= 35:
        recommendations.append("🌡️ Nắng nóng, uống nhiều nước và tránh ra ngoài giữa trưa")
    elif avg_temp_min <= 15:
        recommendations.append("🧥 Trời lạnh, giữ ấm cơ thể")

    # Add wind-based recommendations
    if max_wind >= 40:
        recommendations.append("💨 Gió mạnh, cẩn thận với biển báo và cây cối")

    return {
        "summary": {
            "total_rainfall_mm": round(total_rainfall, 1),
            "max_daily_rainfall_mm": round(max_daily_rainfall, 1),
            "max_day_date": max_day_date,
            "avg_daily_rainfall_mm": round(avg_daily_rainfall, 1),
            "total_rain_hours": round(total_rain_hours, 1),
            "forecast_days": len(dates),
            "temperature_range": {
                "max": round(max_temp, 1) if max_temp else None,
                "min": round(min_temp, 1) if min_temp else None,
                "avg_high": round(avg_temp_max, 1),
                "avg_low": round(avg_temp_min, 1)
            },
            "wind_max_kmh": round(max_wind, 1),
            "wind_gust_max_kmh": round(max_gust, 1)
        },
        "description": generate_weather_description(),
        "overall_risk": {
            "code": overall_risk_code,
            "level": overall_risk_level,
            "description": overall_risk_desc
        },
        "daily_forecast": daily_analysis,
        "peak_hours": peak_hours,
        "recommendations": recommendations
    }


def find_nearest_province(lat: float, lon: float) -> tuple:
    """
    Find the nearest province from predefined locations
    """
    min_distance = float('inf')
    nearest_key = None
    nearest_info = None

    for key, loc in VIETNAM_LOCATIONS.items():
        # Simple Euclidean distance (good enough for nearby locations)
        dist = ((loc["lat"] - lat) ** 2 + (loc["lon"] - lon) ** 2) ** 0.5
        if dist < min_distance:
            min_distance = dist
            nearest_key = key
            nearest_info = loc

    return nearest_key, nearest_info, min_distance


@router.get("/analyze")
async def analyze_rainfall_by_location(
    lat: float = Query(..., description="Vĩ độ (latitude)"),
    lon: float = Query(..., description="Kinh độ (longitude)"),
    days: int = Query(7, ge=1, le=16, description="Số ngày dự báo (1-16)")
):
    """
    Phân tích lượng mưa cho một vị trí cụ thể

    - Lấy thông tin địa chỉ (phường/xã, quận/huyện, tỉnh/thành phố)
    - Dự báo lượng mưa theo ngày
    - Phân tích rủi ro ngập úng
    - Đề xuất và khuyến nghị

    Args:
        lat: Vĩ độ (ví dụ: 21.0285 cho Hà Nội)
        lon: Kinh độ (ví dụ: 105.8542 cho Hà Nội)
        days: Số ngày dự báo

    Returns:
        Kết quả phân tích lượng mưa chi tiết
    """
    try:
        # Validate coordinates for Vietnam
        if not (8 <= lat <= 24 and 102 <= lon <= 110):
            raise HTTPException(
                status_code=400,
                detail="Tọa độ ngoài phạm vi Việt Nam. Vĩ độ: 8-24, Kinh độ: 102-110"
            )

        # Get location details
        location_info = reverse_geocode(lat, lon)

        # Find nearest predefined province
        nearest_key, nearest_province, distance = find_nearest_province(lat, lon)

        # Fetch rainfall data
        rainfall_data = fetch_rainfall_data(lat, lon, days)

        if not rainfall_data:
            raise HTTPException(status_code=500, detail="Không thể lấy dữ liệu thời tiết")

        # Analyze rainfall
        analysis = analyze_rainfall(rainfall_data)

        return {
            "location": {
                "coordinates": {
                    "latitude": lat,
                    "longitude": lon
                },
                "address": {
                    "ward": location_info["ward"],
                    "district": location_info["district"],
                    "province": location_info["province"],
                    "full_address": location_info["display_name"]
                },
                "nearest_station": {
                    "code": nearest_key,
                    "name": nearest_province["name"] if nearest_province else "",
                    "region": nearest_province["region"] if nearest_province else "",
                    "distance_deg": round(distance, 4)
                }
            },
            "analysis": analysis,
            "metadata": {
                "forecast_days": days,
                "data_source": "Open-Meteo API",
                "geocoding_source": "OpenStreetMap Nominatim"
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi phân tích: {str(e)}")


@router.get("/province/{province_code}")
async def analyze_rainfall_by_province(
    province_code: str,
    days: int = Query(7, ge=1, le=16, description="Số ngày dự báo (1-16)")
):
    """
    Phân tích lượng mưa cho một tỉnh/thành phố

    Args:
        province_code: Mã tỉnh/thành (vd: hanoi, ho_chi_minh, da_nang)
        days: Số ngày dự báo

    Returns:
        Kết quả phân tích lượng mưa với thông tin chi tiết về khu vực
    """
    if province_code not in VIETNAM_LOCATIONS:
        raise HTTPException(
            status_code=404,
            detail=f"Không tìm thấy tỉnh/thành: {province_code}. Xem danh sách tại /api/locations"
        )

    loc = VIETNAM_LOCATIONS[province_code]

    # Fetch and analyze
    rainfall_data = fetch_rainfall_data(loc["lat"], loc["lon"], days)

    if not rainfall_data:
        raise HTTPException(status_code=500, detail="Không thể lấy dữ liệu thời tiết")

    analysis = analyze_rainfall(rainfall_data)

    # Get region info
    region_key = loc["region"]
    region_info = REGION_INFO.get(region_key, {})

    # Get province-specific info if available
    province_info = PROVINCE_INFO.get(province_code, {})

    # Build detailed location info
    location_data = {
        "code": province_code,
        "name": loc["name"],
        "region": loc["region"],
        "region_name": region_info.get("name", ""),
        "coordinates": {
            "latitude": loc["lat"],
            "longitude": loc["lon"]
        }
    }

    # Add province details if available
    if province_info:
        location_data["details"] = {
            "description": province_info.get("description", ""),
            "population": province_info.get("population", ""),
            "area": province_info.get("area", ""),
            "elevation": province_info.get("elevation", ""),
            "flood_zones": province_info.get("flood_zones", []),
            "rivers": province_info.get("rivers", []),
            "notes": province_info.get("notes", "")
        }

    # Add region climate info
    if region_info:
        location_data["climate_info"] = {
            "climate": region_info.get("climate", ""),
            "terrain": region_info.get("terrain", ""),
            "flood_risk": region_info.get("flood_risk", ""),
            "avg_annual_rainfall": region_info.get("avg_annual_rainfall", "")
        }

    return {
        "location": location_data,
        "analysis": analysis,
        "metadata": {
            "forecast_days": days,
            "data_source": "Open-Meteo API",
            "data_description": "Dữ liệu dự báo thời tiết từ Open-Meteo (ECMWF, GFS models). Cập nhật mỗi 6 giờ."
        }
    }


@router.get("/search")
async def search_locations(
    q: str = Query(..., min_length=2, description="Tên địa điểm cần tìm (quận, huyện, xã, phường)"),
    limit: int = Query(10, ge=1, le=20, description="Số kết quả tối đa")
):
    """
    Tìm kiếm địa điểm theo tên (quận, huyện, xã, phường)

    Args:
        q: Từ khóa tìm kiếm (vd: "Cầu Giấy", "Quận 1", "Xã Đông Anh")
        limit: Số kết quả tối đa

    Returns:
        Danh sách địa điểm phù hợp với tọa độ
    """
    results = search_location(q, limit)

    if not results:
        return {
            "query": q,
            "results": [],
            "total": 0
        }

    return {
        "query": q,
        "results": results,
        "total": len(results)
    }


@router.get("/province/{province_code}/districts")
async def get_province_districts(province_code: str):
    """
    Lấy danh sách quận/huyện của một tỉnh/thành phố

    Args:
        province_code: Mã tỉnh/thành (vd: hanoi, ho_chi_minh)

    Returns:
        Danh sách quận/huyện với tọa độ
    """
    if province_code not in VIETNAM_LOCATIONS:
        raise HTTPException(
            status_code=404,
            detail=f"Không tìm thấy tỉnh/thành: {province_code}"
        )

    result = get_administrative_divisions(province_code)
    return result


@router.get("/compare")
async def compare_rainfall_multiple_locations(
    locations: str = Query(..., description="Danh sách mã tỉnh/thành cách nhau bởi dấu phẩy (vd: hanoi,da_nang,ho_chi_minh)"),
    days: int = Query(7, ge=1, le=16, description="Số ngày dự báo")
):
    """
    So sánh lượng mưa giữa nhiều địa điểm

    Args:
        locations: Danh sách mã tỉnh/thành (cách nhau bởi dấu phẩy)
        days: Số ngày dự báo

    Returns:
        So sánh lượng mưa giữa các địa điểm
    """
    location_list = [loc.strip().lower() for loc in locations.split(",")]

    if len(location_list) < 2:
        raise HTTPException(status_code=400, detail="Cần ít nhất 2 địa điểm để so sánh")

    if len(location_list) > 5:
        raise HTTPException(status_code=400, detail="Tối đa 5 địa điểm để so sánh")

    results = []

    for loc_code in location_list:
        if loc_code not in VIETNAM_LOCATIONS:
            continue

        loc = VIETNAM_LOCATIONS[loc_code]
        rainfall_data = fetch_rainfall_data(loc["lat"], loc["lon"], days)

        if rainfall_data:
            analysis = analyze_rainfall(rainfall_data)
            results.append({
                "location": {
                    "code": loc_code,
                    "name": loc["name"],
                    "region": loc["region"]
                },
                "summary": analysis["summary"],
                "overall_risk": analysis["overall_risk"]
            })

    if not results:
        raise HTTPException(status_code=404, detail="Không tìm thấy địa điểm hợp lệ")

    # Sort by total rainfall
    results.sort(key=lambda x: x["summary"]["total_rainfall_mm"], reverse=True)

    return {
        "comparison": results,
        "highest_rainfall": results[0]["location"]["name"] if results else None,
        "metadata": {
            "forecast_days": days,
            "locations_analyzed": len(results)
        }
    }
