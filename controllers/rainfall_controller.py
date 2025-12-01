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
    Fetch rainfall forecast data from Open-Meteo
    """
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "precipitation,rain,showers,precipitation_probability",
        "daily": "precipitation_sum,rain_sum,showers_sum,precipitation_hours,precipitation_probability_max",
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
    Analyze rainfall data and generate insights
    """
    daily = data.get("daily", {})
    hourly = data.get("hourly", {})

    dates = daily.get("time", [])
    precipitation_sum = daily.get("precipitation_sum", [])
    rain_sum = daily.get("rain_sum", [])
    precipitation_hours = daily.get("precipitation_hours", [])
    precipitation_prob_max = daily.get("precipitation_probability_max", [])

    # Calculate totals and averages
    total_rainfall = sum(p for p in precipitation_sum if p is not None)
    max_daily_rainfall = max(precipitation_sum) if precipitation_sum else 0
    max_day_index = precipitation_sum.index(max_daily_rainfall) if max_daily_rainfall > 0 else 0
    max_day_date = dates[max_day_index] if dates else ""

    avg_daily_rainfall = total_rainfall / len(precipitation_sum) if precipitation_sum else 0
    total_rain_hours = sum(h for h in precipitation_hours if h is not None)

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

    # Daily analysis
    daily_analysis = []
    for i, date in enumerate(dates):
        precip = precipitation_sum[i] if i < len(precipitation_sum) else 0
        rain = rain_sum[i] if i < len(rain_sum) else 0
        hours = precipitation_hours[i] if i < len(precipitation_hours) else 0
        prob = precipitation_prob_max[i] if i < len(precipitation_prob_max) else 0

        risk_code, risk_level, risk_desc = get_risk_level(precip or 0)

        daily_analysis.append({
            "date": date,
            "precipitation_mm": round(precip or 0, 1),
            "rain_mm": round(rain or 0, 1),
            "rain_hours": round(hours or 0, 1),
            "probability_percent": prob or 0,
            "risk_code": risk_code,
            "risk_level": risk_level,
            "risk_description": risk_desc
        })

    # Hourly peak analysis (find peak hours)
    hourly_times = hourly.get("time", [])
    hourly_precip = hourly.get("precipitation", [])

    peak_hours = []
    for i, time in enumerate(hourly_times):
        precip = hourly_precip[i] if i < len(hourly_precip) else 0
        if precip and precip >= 5:  # Significant rainfall threshold
            peak_hours.append({
                "time": time,
                "precipitation_mm": round(precip, 1)
            })

    # Sort peak hours by precipitation
    peak_hours.sort(key=lambda x: x["precipitation_mm"], reverse=True)
    peak_hours = peak_hours[:10]  # Top 10 peak hours

    # Overall risk for the period
    overall_risk_code, overall_risk_level, overall_risk_desc = get_risk_level(max_daily_rainfall)

    # Recommendations
    recommendations = []
    if max_daily_rainfall >= 100:
        recommendations = [
            "Cảnh báo mưa rất lớn, có nguy cơ ngập úng nghiêm trọng",
            "Hạn chế ra ngoài trong thời gian mưa lớn",
            "Di chuyển đồ đạc lên cao nếu ở vùng trũng",
            "Theo dõi thông tin từ cơ quan chức năng"
        ]
    elif max_daily_rainfall >= 70:
        recommendations = [
            "Dự kiến mưa lớn, cần đề phòng ngập cục bộ",
            "Kiểm tra hệ thống thoát nước",
            "Tránh đi qua vùng ngập nước"
        ]
    elif max_daily_rainfall >= 50:
        recommendations = [
            "Mưa vừa đến lớn, nên mang theo áo mưa",
            "Lái xe cẩn thận trên đường trơn"
        ]
    elif max_daily_rainfall >= 20:
        recommendations = [
            "Có mưa rải rác, chuẩn bị ô/áo mưa khi ra ngoài"
        ]
    else:
        recommendations = [
            "Thời tiết thuận lợi, ít khả năng mưa"
        ]

    return {
        "summary": {
            "total_rainfall_mm": round(total_rainfall, 1),
            "max_daily_rainfall_mm": round(max_daily_rainfall, 1),
            "max_day_date": max_day_date,
            "avg_daily_rainfall_mm": round(avg_daily_rainfall, 1),
            "total_rain_hours": round(total_rain_hours, 1),
            "forecast_days": len(dates)
        },
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
        Kết quả phân tích lượng mưa
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

    return {
        "location": {
            "code": province_code,
            "name": loc["name"],
            "region": loc["region"],
            "coordinates": {
                "latitude": loc["lat"],
                "longitude": loc["lon"]
            }
        },
        "analysis": analysis,
        "metadata": {
            "forecast_days": days,
            "data_source": "Open-Meteo API"
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
