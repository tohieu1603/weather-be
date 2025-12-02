#!/usr/bin/env python3
"""
Open-Meteo Weather API Integration
Lấy tất cả dữ liệu thời tiết miễn phí từ Open-Meteo
"""
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import json

# Open-Meteo API endpoints
OPEN_METEO_FORECAST = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_HISTORICAL = "https://archive-api.open-meteo.com/v1/archive"
OPEN_METEO_FLOOD = "https://flood-api.open-meteo.com/v1/flood"
OPEN_METEO_AIR_QUALITY = "https://air-quality-api.open-meteo.com/v1/air-quality"
OPEN_METEO_MARINE = "https://marine-api.open-meteo.com/v1/marine"

# Các điểm quan trắc chính của Việt Nam (63 tỉnh thành + điểm quan trọng)
VIETNAM_LOCATIONS = {
    # === MIỀN BẮC ===
    "hanoi": {"lat": 21.0285, "lon": 105.8542, "name": "Hà Nội", "region": "north"},
    "hai_phong": {"lat": 20.8449, "lon": 106.6881, "name": "Hải Phòng", "region": "north"},
    "quang_ninh": {"lat": 21.0064, "lon": 107.2925, "name": "Quảng Ninh", "region": "north"},
    "bac_ninh": {"lat": 21.1861, "lon": 106.0763, "name": "Bắc Ninh", "region": "north"},
    "hai_duong": {"lat": 20.9373, "lon": 106.3145, "name": "Hải Dương", "region": "north"},
    "hung_yen": {"lat": 20.6464, "lon": 106.0511, "name": "Hưng Yên", "region": "north"},
    "thai_binh": {"lat": 20.4463, "lon": 106.3365, "name": "Thái Bình", "region": "north"},
    "nam_dinh": {"lat": 20.4388, "lon": 106.1621, "name": "Nam Định", "region": "north"},
    "ninh_binh": {"lat": 20.2506, "lon": 105.9745, "name": "Ninh Bình", "region": "north"},
    "ha_nam": {"lat": 20.5835, "lon": 105.9230, "name": "Hà Nam", "region": "north"},
    "vinh_phuc": {"lat": 21.3609, "lon": 105.5474, "name": "Vĩnh Phúc", "region": "north"},
    "bac_giang": {"lat": 21.2819, "lon": 106.1946, "name": "Bắc Giang", "region": "north"},
    "phu_tho": {"lat": 21.4200, "lon": 105.2000, "name": "Phú Thọ", "region": "north"},
    "thai_nguyen": {"lat": 21.5671, "lon": 105.8252, "name": "Thái Nguyên", "region": "north"},
    "bac_kan": {"lat": 22.1471, "lon": 105.8348, "name": "Bắc Kạn", "region": "north"},
    "cao_bang": {"lat": 22.6667, "lon": 106.2500, "name": "Cao Bằng", "region": "north"},
    "lang_son": {"lat": 21.8536, "lon": 106.7610, "name": "Lạng Sơn", "region": "north"},
    "tuyen_quang": {"lat": 21.8167, "lon": 105.2167, "name": "Tuyên Quang", "region": "north"},
    "ha_giang": {"lat": 22.8333, "lon": 104.9833, "name": "Hà Giang", "region": "north"},
    "yen_bai": {"lat": 21.7168, "lon": 104.8987, "name": "Yên Bái", "region": "north"},
    "lao_cai": {"lat": 22.4856, "lon": 103.9707, "name": "Lào Cai", "region": "north"},
    "lai_chau": {"lat": 22.3864, "lon": 103.4701, "name": "Lai Châu", "region": "north"},
    "dien_bien": {"lat": 21.3833, "lon": 103.0167, "name": "Điện Biên", "region": "north"},
    "son_la": {"lat": 21.3261, "lon": 103.9008, "name": "Sơn La", "region": "north"},
    "hoa_binh": {"lat": 20.8167, "lon": 105.3167, "name": "Hòa Bình", "region": "north"},

    # === MIỀN TRUNG ===
    "thanh_hoa": {"lat": 19.8067, "lon": 105.7851, "name": "Thanh Hóa", "region": "central"},
    "nghe_an": {"lat": 18.6793, "lon": 105.6811, "name": "Nghệ An", "region": "central"},
    "ha_tinh": {"lat": 18.3430, "lon": 105.9050, "name": "Hà Tĩnh", "region": "central"},
    "quang_binh": {"lat": 17.4676, "lon": 106.6222, "name": "Quảng Bình", "region": "central"},
    "quang_tri": {"lat": 16.7943, "lon": 107.1859, "name": "Quảng Trị", "region": "central"},
    "thua_thien_hue": {"lat": 16.4637, "lon": 107.5909, "name": "Thừa Thiên Huế", "region": "central"},
    "da_nang": {"lat": 16.0544, "lon": 108.2022, "name": "Đà Nẵng", "region": "central"},
    "quang_nam": {"lat": 15.5393, "lon": 108.0192, "name": "Quảng Nam", "region": "central"},
    "quang_ngai": {"lat": 15.1214, "lon": 108.8044, "name": "Quảng Ngãi", "region": "central"},
    "binh_dinh": {"lat": 13.7830, "lon": 109.2192, "name": "Bình Định", "region": "central"},
    "phu_yen": {"lat": 13.0955, "lon": 109.0929, "name": "Phú Yên", "region": "central"},
    "khanh_hoa": {"lat": 12.2585, "lon": 109.0526, "name": "Khánh Hòa", "region": "central"},
    "ninh_thuan": {"lat": 11.6739, "lon": 108.8629, "name": "Ninh Thuận", "region": "central"},
    "binh_thuan": {"lat": 10.9273, "lon": 108.1017, "name": "Bình Thuận", "region": "central"},

    # === TÂY NGUYÊN ===
    "kon_tum": {"lat": 14.3497, "lon": 108.0005, "name": "Kon Tum", "region": "highland"},
    "gia_lai": {"lat": 13.9833, "lon": 108.0000, "name": "Gia Lai", "region": "highland"},
    "dak_lak": {"lat": 12.6667, "lon": 108.0500, "name": "Đắk Lắk", "region": "highland"},
    "dak_nong": {"lat": 12.2646, "lon": 107.6098, "name": "Đắk Nông", "region": "highland"},
    "lam_dong": {"lat": 11.9404, "lon": 108.4583, "name": "Lâm Đồng", "region": "highland"},

    # === MIỀN NAM ===
    "ho_chi_minh": {"lat": 10.7769, "lon": 106.7009, "name": "TP.HCM", "region": "south"},
    "binh_duong": {"lat": 11.3254, "lon": 106.4770, "name": "Bình Dương", "region": "south"},
    "dong_nai": {"lat": 10.9574, "lon": 106.8426, "name": "Đồng Nai", "region": "south"},
    "binh_phuoc": {"lat": 11.7511, "lon": 106.7234, "name": "Bình Phước", "region": "south"},
    "tay_ninh": {"lat": 11.3351, "lon": 106.0987, "name": "Tây Ninh", "region": "south"},
    "ba_ria_vung_tau": {"lat": 10.5417, "lon": 107.2429, "name": "Bà Rịa-Vũng Tàu", "region": "south"},
    "long_an": {"lat": 10.5333, "lon": 106.4167, "name": "Long An", "region": "south"},
    "tien_giang": {"lat": 10.3600, "lon": 106.3600, "name": "Tiền Giang", "region": "south"},
    "ben_tre": {"lat": 10.2333, "lon": 106.3833, "name": "Bến Tre", "region": "south"},
    "tra_vinh": {"lat": 9.8128, "lon": 106.2992, "name": "Trà Vinh", "region": "south"},
    "vinh_long": {"lat": 10.2395, "lon": 105.9572, "name": "Vĩnh Long", "region": "south"},
    "dong_thap": {"lat": 10.4938, "lon": 105.6881, "name": "Đồng Tháp", "region": "south"},
    "an_giang": {"lat": 10.5216, "lon": 105.1258, "name": "An Giang", "region": "south"},
    "kien_giang": {"lat": 10.0125, "lon": 105.0808, "name": "Kiên Giang", "region": "south"},
    "can_tho": {"lat": 10.0452, "lon": 105.7469, "name": "Cần Thơ", "region": "south"},
    "hau_giang": {"lat": 9.7577, "lon": 105.6412, "name": "Hậu Giang", "region": "south"},
    "soc_trang": {"lat": 9.6024, "lon": 105.9739, "name": "Sóc Trăng", "region": "south"},
    "bac_lieu": {"lat": 9.2840, "lon": 105.7244, "name": "Bạc Liêu", "region": "south"},
    "ca_mau": {"lat": 9.1767, "lon": 105.1524, "name": "Cà Mau", "region": "south"},
}


def fetch_forecast_full(lat: float, lon: float, days: int = 7) -> Dict:
    """
    Lấy dự báo thời tiết đầy đủ từ Open-Meteo
    Bao gồm: nhiệt độ, mưa, gió, độ ẩm, UV, v.v.
    """
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": ",".join([
            "temperature_2m",
            "relative_humidity_2m",
            "apparent_temperature",
            "precipitation_probability",
            "precipitation",
            "rain",
            "showers",
            "weather_code",
            "cloud_cover",
            "visibility",
            "wind_speed_10m",
            "wind_direction_10m",
            "wind_gusts_10m",
            "uv_index",
            "is_day"
        ]),
        "daily": ",".join([
            "weather_code",
            "temperature_2m_max",
            "temperature_2m_min",
            "apparent_temperature_max",
            "apparent_temperature_min",
            "sunrise",
            "sunset",
            "daylight_duration",
            "sunshine_duration",
            "uv_index_max",
            "precipitation_sum",
            "rain_sum",
            "showers_sum",
            "precipitation_hours",
            "precipitation_probability_max",
            "wind_speed_10m_max",
            "wind_gusts_10m_max",
            "wind_direction_10m_dominant",
            "et0_fao_evapotranspiration"
        ]),
        "forecast_days": days,
        "timezone": "Asia/Ho_Chi_Minh",
    }

    try:
        resp = requests.get(OPEN_METEO_FORECAST, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"Error fetching forecast: {e}")
        return {}


def fetch_flood_forecast(lat: float, lon: float) -> Dict:
    """
    Lấy dự báo nguy cơ lũ từ Open-Meteo Flood API
    API này cung cấp river discharge forecast dựa trên GloFAS
    """
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "river_discharge",
        "forecast_days": 7,
    }

    try:
        resp = requests.get(OPEN_METEO_FLOOD, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"Error fetching flood data: {e}")
        return {}


def fetch_air_quality(lat: float, lon: float) -> Dict:
    """
    Lấy chỉ số chất lượng không khí từ Open-Meteo Air Quality API
    """
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": ",".join([
            "pm10",
            "pm2_5",
            "carbon_monoxide",
            "nitrogen_dioxide",
            "sulphur_dioxide",
            "ozone",
            "aerosol_optical_depth",
            "dust",
            "uv_index",
            "uv_index_clear_sky",
            "alder_pollen",
            "birch_pollen",
            "grass_pollen",
            "mugwort_pollen",
            "olive_pollen",
            "ragweed_pollen",
            "european_aqi",
            "us_aqi"
        ]),
        "timezone": "Asia/Ho_Chi_Minh",
    }

    try:
        resp = requests.get(OPEN_METEO_AIR_QUALITY, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"Error fetching air quality: {e}")
        return {}


def fetch_marine_forecast(lat: float, lon: float) -> Dict:
    """
    Lấy dự báo biển từ Open-Meteo Marine API
    Cho các vùng ven biển
    """
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": ",".join([
            "wave_height",
            "wave_direction",
            "wave_period",
            "wind_wave_height",
            "wind_wave_direction",
            "swell_wave_height",
            "swell_wave_direction",
            "swell_wave_period"
        ]),
        "daily": ",".join([
            "wave_height_max",
            "wave_direction_dominant",
            "wave_period_max",
            "wind_wave_height_max",
            "swell_wave_height_max"
        ]),
        "timezone": "Asia/Ho_Chi_Minh",
    }

    try:
        resp = requests.get(OPEN_METEO_MARINE, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"Error fetching marine data: {e}")
        return {}


def fetch_historical_weather(lat: float, lon: float, start_date: str, end_date: str) -> Dict:
    """
    Lấy dữ liệu thời tiết lịch sử từ Open-Meteo Historical API
    Có thể lấy dữ liệu từ 1940 đến hiện tại
    """
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date,
        "end_date": end_date,
        "daily": ",".join([
            "weather_code",
            "temperature_2m_max",
            "temperature_2m_min",
            "precipitation_sum",
            "rain_sum",
            "precipitation_hours",
            "wind_speed_10m_max"
        ]),
        "timezone": "Asia/Ho_Chi_Minh",
    }

    try:
        resp = requests.get(OPEN_METEO_HISTORICAL, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"Error fetching historical data: {e}")
        return {}


def get_all_vietnam_weather(locations: List[str] = None, include_flood: bool = True,
                            include_air_quality: bool = False, include_marine: bool = False) -> Dict:
    """
    Lấy dữ liệu thời tiết cho nhiều địa điểm ở Việt Nam

    Args:
        locations: Danh sách mã tỉnh/thành (nếu None sẽ lấy tất cả)
        include_flood: Có lấy dữ liệu dự báo lũ không
        include_air_quality: Có lấy chỉ số chất lượng không khí không
        include_marine: Có lấy dữ liệu biển không (cho vùng ven biển)
    """
    if locations is None:
        locations = list(VIETNAM_LOCATIONS.keys())

    results = {
        "generated_at": datetime.now().isoformat(),
        "total_locations": len(locations),
        "locations": {}
    }

    for loc_code in locations:
        if loc_code not in VIETNAM_LOCATIONS:
            continue

        loc_info = VIETNAM_LOCATIONS[loc_code]
        lat, lon = loc_info["lat"], loc_info["lon"]

        print(f"Fetching weather for {loc_info['name']}...")

        loc_data = {
            "info": loc_info,
            "forecast": fetch_forecast_full(lat, lon),
        }

        if include_flood:
            loc_data["flood"] = fetch_flood_forecast(lat, lon)

        if include_air_quality:
            loc_data["air_quality"] = fetch_air_quality(lat, lon)

        # Chỉ lấy dữ liệu biển cho vùng ven biển
        coastal_provinces = [
            "quang_ninh", "hai_phong", "thai_binh", "nam_dinh", "ninh_binh",
            "thanh_hoa", "nghe_an", "ha_tinh", "quang_binh", "quang_tri",
            "thua_thien_hue", "da_nang", "quang_nam", "quang_ngai", "binh_dinh",
            "phu_yen", "khanh_hoa", "ninh_thuan", "binh_thuan", "ba_ria_vung_tau",
            "ho_chi_minh", "ben_tre", "tra_vinh", "soc_trang", "bac_lieu",
            "ca_mau", "kien_giang"
        ]

        if include_marine and loc_code in coastal_provinces:
            loc_data["marine"] = fetch_marine_forecast(lat, lon)

        results["locations"][loc_code] = loc_data

    return results


def analyze_weather_for_alerts(weather_data: Dict) -> List[Dict]:
    """
    Phân tích dữ liệu thời tiết và tạo cảnh báo thực
    Dựa trên dữ liệu thật từ Open-Meteo
    """
    alerts = []
    today = datetime.now().strftime("%Y-%m-%d")

    for loc_code, loc_data in weather_data.get("locations", {}).items():
        loc_info = loc_data.get("info", {})
        forecast = loc_data.get("forecast", {})
        flood = loc_data.get("flood", {})

        if not forecast:
            continue

        daily = forecast.get("daily", {})

        # Lấy dữ liệu ngày hôm nay và các ngày tới
        dates = daily.get("time", [])
        temps_max = daily.get("temperature_2m_max", [])
        temps_min = daily.get("temperature_2m_min", [])
        precipitation = daily.get("precipitation_sum", [])
        rain = daily.get("rain_sum", [])
        uv_max = daily.get("uv_index_max", [])
        wind_max = daily.get("wind_speed_10m_max", [])
        wind_gusts = daily.get("wind_gusts_10m_max", [])
        weather_codes = daily.get("weather_code", [])

        for i, date in enumerate(dates[:7]):  # 7 ngày tới
            if i >= len(precipitation):
                break

            precip = precipitation[i] if precipitation[i] else 0
            temp_max = temps_max[i] if i < len(temps_max) else None
            temp_min = temps_min[i] if i < len(temps_min) else None
            uv = uv_max[i] if i < len(uv_max) else None
            wind = wind_max[i] if i < len(wind_max) else None
            gust = wind_gusts[i] if i < len(wind_gusts) else None
            weather_code = weather_codes[i] if i < len(weather_codes) else None

            # === CẢNH BÁO MƯA LỚN ===
            if precip >= 30:
                severity = "critical" if precip >= 100 else "high" if precip >= 70 else "medium" if precip >= 50 else "low"
                # Tính toán thêm các chỉ số
                rain_intensity = "Mưa rất to" if precip >= 100 else "Mưa to" if precip >= 50 else "Mưa vừa" if precip >= 25 else "Mưa nhỏ"
                flood_risk = round(min(100, (precip / 150) * 100), 0)  # % nguy cơ ngập
                precip_hours = daily.get("precipitation_hours", [])[i] if i < len(daily.get("precipitation_hours", [])) else None
                precip_prob = daily.get("precipitation_probability_max", [])[i] if i < len(daily.get("precipitation_probability_max", [])) else None

                alerts.append({
                    "id": f"rain_{loc_code}_{date}",
                    "type": "heavy_rain",
                    "category": "Mưa lớn",
                    "title": f"Cảnh báo mưa lớn - {loc_info.get('name', loc_code)}",
                    "severity": severity,
                    "date": date,
                    "region": loc_info.get("name", loc_code),
                    "provinces": [loc_info.get("name", loc_code)],
                    "description": f"Dự báo lượng mưa {precip:.1f}mm trong ngày {date}. " +
                                   ("Mưa rất lớn, nguy cơ ngập úng cao." if precip >= 100 else
                                    "Mưa lớn, cần đề phòng ngập cục bộ." if precip >= 70 else
                                    "Mưa vừa đến lớn."),
                    "data": {
                        "rainfall_mm": round(precip, 1),
                        "rain_intensity": rain_intensity,
                        "precipitation_hours": round(precip_hours, 1) if precip_hours else None,
                        "precipitation_probability": round(precip_prob) if precip_prob else None,
                        "flood_risk_percent": flood_risk,
                        "weather_code": weather_code,
                        "weather_description": get_weather_description(weather_code) if weather_code else None,
                        "wind_speed_kmh": round(wind, 1) if wind else None,
                        "wind_gust_kmh": round(gust, 1) if gust else None,
                        "temp_max_c": round(temp_max, 1) if temp_max else None,
                        "temp_min_c": round(temp_min, 1) if temp_min else None,
                        "humidity_note": "Độ ẩm cao" if precip >= 50 else "Độ ẩm tăng",
                    },
                    "recommendations": [
                        "Hạn chế ra ngoài khi có mưa to",
                        "Tránh xa các vùng trũng, dễ ngập",
                        "Kiểm tra hệ thống thoát nước",
                        "Chuẩn bị đèn pin, nến phòng mất điện" if precip >= 70 else "Mang theo áo mưa khi ra ngoài",
                        "Không lội qua vùng nước ngập" if precip >= 50 else "Cẩn thận đường trơn trượt",
                    ],
                    "source": "Open-Meteo API"
                })

            # === CẢNH BÁO NẮNG NÓNG ===
            # Theo QCVN: Nắng nóng >= 35°C, Nắng nóng gay gắt >= 37°C, Đặc biệt gay gắt >= 39°C
            if temp_max and temp_max >= 35:
                apparent_max = daily.get("apparent_temperature_max", [])[i] if i < len(daily.get("apparent_temperature_max", [])) else None
                sunshine_hours = daily.get("sunshine_duration", [])[i] if i < len(daily.get("sunshine_duration", [])) else None
                sunshine_hours = round(sunshine_hours / 3600, 1) if sunshine_hours else None

                # Xác định loại nắng nóng và mức độ
                if temp_max >= 39 or (apparent_max and apparent_max >= 42):
                    severity = "critical"
                    category = "Nắng nóng"
                    heat_level = "Nắng nóng đặc biệt gay gắt"
                    title = f"Nắng nóng đặc biệt gay gắt - {loc_info.get('name', loc_code)}"
                elif temp_max >= 37 or (apparent_max and apparent_max >= 40):
                    severity = "high"
                    category = "Nắng nóng"
                    heat_level = "Nắng nóng gay gắt"
                    title = f"Nắng nóng gay gắt - {loc_info.get('name', loc_code)}"
                else:
                    severity = "medium"
                    category = "Nắng nóng"
                    heat_level = "Nắng nóng"
                    title = f"Cảnh báo nắng nóng - {loc_info.get('name', loc_code)}"

                alerts.append({
                    "id": f"heat_{loc_code}_{date}",
                    "type": "heat_wave",
                    "category": category,
                    "title": title,
                    "severity": severity,
                    "date": date,
                    "region": loc_info.get("name", loc_code),
                    "provinces": [loc_info.get("name", loc_code)],
                    "description": f"Nhiệt độ cao nhất {temp_max:.1f}°C" +
                                   (f", cảm giác thực tế {apparent_max:.1f}°C" if apparent_max else "") +
                                   f" vào ngày {date}. " +
                                   ("Nguy hiểm cho sức khỏe, tránh ra ngoài." if temp_max >= 39 else
                                    "Hạn chế hoạt động ngoài trời." if temp_max >= 37 else "Chú ý bổ sung nước."),
                    "data": {
                        "max_temperature_c": round(temp_max, 1),
                        "min_temperature_c": round(temp_min, 1) if temp_min else None,
                        "apparent_temperature_c": round(apparent_max, 1) if apparent_max else None,
                        "heat_level": heat_level,
                        "uv_index": round(uv, 1) if uv else None,
                        "uv_level": "Cực kỳ cao" if uv and uv >= 11 else "Rất cao" if uv and uv >= 8 else "Cao" if uv and uv >= 6 else "Trung bình" if uv else None,
                        "sunshine_hours": sunshine_hours,
                        "weather_code": weather_code,
                        "weather_description": get_weather_description(weather_code) if weather_code else None,
                        "wind_speed_kmh": round(wind, 1) if wind else None,
                        "dehydration_risk": "Rất cao" if temp_max >= 39 else "Cao" if temp_max >= 37 else "Trung bình",
                    },
                    "recommendations": [
                        "KHÔNG ra ngoài từ 10h-16h" if temp_max >= 39 else "Hạn chế ra ngoài từ 10h-16h",
                        "Uống 3-4 lít nước/ngày" if temp_max >= 37 else "Uống ít nhất 2 lít nước/ngày",
                        "Người già, trẻ em, người bệnh tim mạch cần ở trong nhà mát",
                        "Mặc quần áo thoáng mát, màu sáng",
                        "Sử dụng kem chống nắng SPF 50+" if uv and uv >= 8 else "Đội mũ, kính râm khi ra ngoài",
                        "Tránh lao động nặng ngoài trời" if temp_max >= 37 else "Nghỉ ngơi trong bóng râm"
                    ],
                    "source": "Open-Meteo API"
                })

            # === CẢNH BÁO NẮNG NÓNG CỤC BỘ ===
            # Khi nhiệt độ 33-35°C nhưng apparent (cảm giác) >= 37°C hoặc UV rất cao
            elif temp_max and temp_max >= 33 and temp_max < 35:
                apparent_max = daily.get("apparent_temperature_max", [])[i] if i < len(daily.get("apparent_temperature_max", [])) else None
                sunshine_hours = daily.get("sunshine_duration", [])[i] if i < len(daily.get("sunshine_duration", [])) else None
                sunshine_hours = round(sunshine_hours / 3600, 1) if sunshine_hours else None

                # Chỉ cảnh báo nếu cảm giác nóng hơn hoặc UV cao
                if (apparent_max and apparent_max >= 37) or (uv and uv >= 9):
                    severity = "medium" if (apparent_max and apparent_max >= 38) or (uv and uv >= 10) else "low"

                    alerts.append({
                        "id": f"heat_local_{loc_code}_{date}",
                        "type": "heat_local",
                        "category": "Nắng nóng cục bộ",
                        "title": f"Nắng nóng cục bộ - {loc_info.get('name', loc_code)}",
                        "severity": severity,
                        "date": date,
                        "region": loc_info.get("name", loc_code),
                        "provinces": [loc_info.get("name", loc_code)],
                        "description": f"Nhiệt độ {temp_max:.1f}°C" +
                                       (f", cảm giác thực tế {apparent_max:.1f}°C" if apparent_max else "") +
                                       (f", chỉ số UV {uv:.0f}" if uv else "") +
                                       f" vào ngày {date}. Có thể nắng nóng cục bộ vào buổi trưa.",
                        "data": {
                            "max_temperature_c": round(temp_max, 1),
                            "min_temperature_c": round(temp_min, 1) if temp_min else None,
                            "apparent_temperature_c": round(apparent_max, 1) if apparent_max else None,
                            "heat_level": "Nắng nóng cục bộ",
                            "uv_index": round(uv, 1) if uv else None,
                            "uv_level": "Rất cao" if uv and uv >= 8 else "Cao" if uv and uv >= 6 else "Trung bình",
                            "sunshine_hours": sunshine_hours,
                            "weather_code": weather_code,
                            "weather_description": get_weather_description(weather_code) if weather_code else None,
                            "wind_speed_kmh": round(wind, 1) if wind else None,
                        },
                        "recommendations": [
                            "Hạn chế hoạt động ngoài trời từ 11h-15h",
                            "Uống đủ nước, tránh đồ uống có cồn",
                            "Đội mũ, mặc áo dài tay khi ra ngoài",
                            "Chú ý bảo vệ da khi UV cao" if uv and uv >= 8 else "Nghỉ ngơi nơi thoáng mát"
                        ],
                        "source": "Open-Meteo API"
                    })

            # === CẢNH BÁO GIÓ MẠNH ===
            if gust and gust >= 60:  # Gió giật >= 60 km/h
                severity = "critical" if gust >= 100 else "high" if gust >= 80 else "medium"
                # Xác định cấp gió Beaufort
                beaufort_scale = 12 if gust >= 118 else 11 if gust >= 103 else 10 if gust >= 89 else 9 if gust >= 75 else 8 if gust >= 62 else 7
                wind_level = "Bão" if gust >= 89 else "Gió mạnh cấp 8-9" if gust >= 75 else "Gió mạnh" if gust >= 62 else "Gió khá mạnh"
                wind_direction = daily.get("wind_direction_10m_dominant", [])[i] if i < len(daily.get("wind_direction_10m_dominant", [])) else None
                wind_dir_text = _get_wind_direction_text(wind_direction) if wind_direction else None

                alerts.append({
                    "id": f"wind_{loc_code}_{date}",
                    "type": "strong_wind",
                    "category": "Gió mạnh",
                    "title": f"Cảnh báo gió mạnh - {loc_info.get('name', loc_code)}",
                    "severity": severity,
                    "date": date,
                    "region": loc_info.get("name", loc_code),
                    "provinces": [loc_info.get("name", loc_code)],
                    "description": f"Gió giật mạnh lên đến {gust:.0f} km/h vào ngày {date}. " +
                                   (f"Hướng gió chủ đạo: {wind_dir_text}. " if wind_dir_text else "") +
                                   f"Tương đương gió cấp {beaufort_scale} theo thang Beaufort.",
                    "data": {
                        "wind_gust_kmh": round(gust, 1),
                        "wind_speed_kmh": round(wind, 1) if wind else None,
                        "wind_level": wind_level,
                        "beaufort_scale": beaufort_scale,
                        "wind_direction_deg": round(wind_direction) if wind_direction else None,
                        "wind_direction_text": wind_dir_text,
                        "weather_code": weather_code,
                        "weather_description": get_weather_description(weather_code) if weather_code else None,
                        "rainfall_mm": round(precip, 1) if precip else None,
                        "danger_level": "Rất nguy hiểm" if gust >= 100 else "Nguy hiểm" if gust >= 80 else "Cần cảnh giác",
                    },
                    "recommendations": [
                        "Chằng chống nhà cửa, cắt tỉa cành cây",
                        "Không đứng dưới cây lớn hoặc biển quảng cáo",
                        "Tàu thuyền không ra khơi",
                        "Di chuyển đồ vật có thể bay" if gust >= 80 else "Đóng cửa sổ, cửa ra vào",
                        "Sơ tán khỏi nhà yếu" if gust >= 100 else "Ở trong nhà kiên cố",
                        "Tránh xa bờ biển và sông" if gust >= 80 else "Hạn chế ra ngoài"
                    ],
                    "source": "Open-Meteo API"
                })

            # === CẢNH BÁO UV CAO ===
            if uv and uv >= 8:
                severity = "critical" if uv >= 11 else "high" if uv >= 9 else "medium"
                alerts.append({
                    "id": f"uv_{loc_code}_{date}",
                    "type": "high_uv",
                    "category": "Tia UV cao",
                    "title": f"Cảnh báo tia UV - {loc_info.get('name', loc_code)}",
                    "severity": severity,
                    "date": date,
                    "region": loc_info.get("name", loc_code),
                    "provinces": [loc_info.get("name", loc_code)],
                    "description": f"Chỉ số UV đạt mức {uv:.0f} (rất cao) vào ngày {date}.",
                    "data": {
                        "uv_index": round(uv, 1),
                        "uv_level": "Cực kỳ cao" if uv >= 11 else "Rất cao" if uv >= 8 else "Cao",
                        "max_temperature_c": round(temp_max, 1) if temp_max else None,
                        "sunshine_hours": round(daily.get("sunshine_duration", [])[i] / 3600, 1) if i < len(daily.get("sunshine_duration", [])) and daily.get("sunshine_duration", [])[i] else None,
                        "weather_code": weather_code,
                        "weather_description": get_weather_description(weather_code) if weather_code else None,
                    },
                    "recommendations": [
                        "Tránh ra ngoài từ 10h-15h",
                        "Sử dụng kem chống nắng SPF 50+",
                        "Đội mũ, mặc áo dài tay khi ra ngoài",
                        "Đeo kính râm bảo vệ mắt",
                        "Uống nhiều nước"
                    ],
                    "source": "Open-Meteo API"
                })

            # === CẢNH BÁO RÉT ĐẬM / RÉT HẠI ===
            if temp_min is not None and temp_min <= 15:
                # Rét hại: <= 10°C, Rét đậm: 10-13°C, Rét: 13-15°C
                if temp_min <= 10:
                    severity = "critical" if temp_min <= 5 else "high"
                    category = "Rét hại"
                    cold_level = "Rét hại nghiêm trọng" if temp_min <= 5 else "Rét hại"
                elif temp_min <= 13:
                    severity = "high" if temp_min <= 11 else "medium"
                    category = "Rét đậm"
                    cold_level = "Rét đậm"
                else:
                    severity = "medium"
                    category = "Rét"
                    cold_level = "Trời rét"

                apparent_min = daily.get("apparent_temperature_min", [])[i] if i < len(daily.get("apparent_temperature_min", [])) else None

                alerts.append({
                    "id": f"cold_{loc_code}_{date}",
                    "type": "cold_wave",
                    "category": category,
                    "title": f"Cảnh báo {category.lower()} - {loc_info.get('name', loc_code)}",
                    "severity": severity,
                    "date": date,
                    "region": loc_info.get("name", loc_code),
                    "provinces": [loc_info.get("name", loc_code)],
                    "description": f"Nhiệt độ thấp nhất dự báo {temp_min:.1f}°C vào ngày {date}. " +
                                   (f"Nhiệt độ cảm nhận thực tế có thể xuống đến {apparent_min:.1f}°C. " if apparent_min else "") +
                                   ("Nguy hiểm cho sức khỏe." if temp_min <= 10 else "Cần giữ ấm cơ thể."),
                    "data": {
                        "min_temperature_c": round(temp_min, 1),
                        "max_temperature_c": round(temp_max, 1) if temp_max else None,
                        "apparent_min_temperature_c": round(apparent_min, 1) if apparent_min else None,
                        "cold_level": cold_level,
                        "wind_speed_kmh": round(wind, 1) if wind else None,
                        "weather_code": weather_code,
                        "weather_description": get_weather_description(weather_code) if weather_code else None,
                        "rainfall_mm": round(precip, 1) if precip else None,
                    },
                    "recommendations": [
                        "Mặc đủ ấm, nhiều lớp áo",
                        "Giữ ấm tay chân, đầu, cổ",
                        "Người già, trẻ em hạn chế ra ngoài",
                        "Không sưởi ấm bằng than trong phòng kín",
                        "Che chắn chuồng trại gia súc, gia cầm" if temp_min <= 10 else "Uống nước ấm, ăn đủ chất",
                        "Kiểm tra sức khỏe người già, trẻ nhỏ thường xuyên" if temp_min <= 10 else "Hạn chế tắm khuya"
                    ],
                    "source": "Open-Meteo API"
                })

            # === CẢNH BÁO HẠN HÁN ===
            # Kiểm tra nếu không có mưa nhiều ngày và nhiệt độ cao
            et0 = daily.get("et0_fao_evapotranspiration", [])[i] if i < len(daily.get("et0_fao_evapotranspiration", [])) else None
            # Hạn hán khi: không mưa (precip < 5mm) + nhiệt độ cao (>30°C) + bốc hơi cao (et0 > 5mm/ngày)
            if precip < 5 and temp_max and temp_max >= 32 and et0 and et0 >= 5:
                severity = "high" if et0 >= 7 or temp_max >= 37 else "medium"
                drought_level = "Khô hạn nghiêm trọng" if et0 >= 7 else "Khô hạn"

                alerts.append({
                    "id": f"drought_{loc_code}_{date}",
                    "type": "drought",
                    "category": "Hạn hán",
                    "title": f"Cảnh báo hạn hán - {loc_info.get('name', loc_code)}",
                    "severity": severity,
                    "date": date,
                    "region": loc_info.get("name", loc_code),
                    "provinces": [loc_info.get("name", loc_code)],
                    "description": f"Thời tiết khô nóng vào ngày {date}. Nhiệt độ {temp_max:.1f}°C, " +
                                   f"lượng bốc hơi {et0:.1f}mm/ngày, không có mưa. Nguy cơ thiếu nước.",
                    "data": {
                        "max_temperature_c": round(temp_max, 1),
                        "evapotranspiration_mm": round(et0, 1),
                        "rainfall_mm": round(precip, 1),
                        "drought_level": drought_level,
                        "humidity_status": "Rất khô" if et0 >= 7 else "Khô",
                        "weather_code": weather_code,
                        "weather_description": get_weather_description(weather_code) if weather_code else None,
                        "uv_index": round(uv, 1) if uv else None,
                    },
                    "recommendations": [
                        "Tiết kiệm nước sinh hoạt",
                        "Tưới cây vào sáng sớm hoặc chiều tối",
                        "Che phủ đất để giữ ẩm",
                        "Dự trữ nước cho gia súc, gia cầm",
                        "Theo dõi nguồn nước sinh hoạt",
                        "Phòng chống cháy rừng"
                    ],
                    "source": "Open-Meteo API"
                })

        # === CẢNH BÁO LŨ (từ Flood API) ===
        if flood:
            flood_daily = flood.get("daily", {})
            flood_dates = flood_daily.get("time", [])
            river_discharge = flood_daily.get("river_discharge", [])

            for i, date in enumerate(flood_dates):
                if i >= len(river_discharge) or river_discharge[i] is None:
                    continue

                discharge = river_discharge[i]

                # Ngưỡng cảnh báo (m³/s) - cần điều chỉnh theo từng sông
                if discharge >= 1000:  # Ngưỡng cảnh báo lũ
                    severity = "critical" if discharge >= 5000 else "high" if discharge >= 2000 else "medium"
                    alerts.append({
                        "id": f"flood_{loc_code}_{date}",
                        "type": "flood",
                        "category": "Lũ lụt",
                        "title": f"Cảnh báo nguy cơ lũ - {loc_info.get('name', loc_code)}",
                        "severity": severity,
                        "date": date,
                        "region": loc_info.get("name", loc_code),
                        "provinces": [loc_info.get("name", loc_code)],
                        "description": f"Lưu lượng sông dự báo {discharge:.0f} m³/s vào ngày {date}. " +
                                       ("Nguy cơ lũ rất cao." if discharge >= 5000 else
                                        "Nguy cơ lũ cao, cần theo dõi." if discharge >= 2000 else
                                        "Mực nước có thể dâng cao."),
                        "data": {
                            "river_discharge_m3s": round(discharge, 0),
                        },
                        "recommendations": [
                            "Theo dõi diễn biến mưa lũ qua đài phát thanh",
                            "Chuẩn bị sẵn sàng sơ tán nếu ở vùng trũng",
                            "Dự trữ lương thực, nước uống, đèn pin"
                        ],
                        "source": "Open-Meteo Flood API (GloFAS)"
                    })

    return alerts


# Weather code mapping (WMO)
WEATHER_CODES = {
    0: "Trời quang",
    1: "Chủ yếu quang",
    2: "Có mây",
    3: "U ám",
    45: "Sương mù",
    48: "Sương mù đóng băng",
    51: "Mưa phùn nhẹ",
    53: "Mưa phùn vừa",
    55: "Mưa phùn dày đặc",
    56: "Mưa phùn đóng băng nhẹ",
    57: "Mưa phùn đóng băng dày",
    61: "Mưa nhẹ",
    63: "Mưa vừa",
    65: "Mưa to",
    66: "Mưa đóng băng nhẹ",
    67: "Mưa đóng băng nặng",
    71: "Tuyết rơi nhẹ",
    73: "Tuyết rơi vừa",
    75: "Tuyết rơi dày",
    77: "Hạt tuyết",
    80: "Mưa rào nhẹ",
    81: "Mưa rào vừa",
    82: "Mưa rào to",
    85: "Mưa tuyết nhẹ",
    86: "Mưa tuyết nặng",
    95: "Dông",
    96: "Dông kèm mưa đá nhẹ",
    99: "Dông kèm mưa đá lớn",
}


def get_weather_description(code: int) -> str:
    """Chuyển weather code thành mô tả tiếng Việt"""
    return WEATHER_CODES.get(code, "Không xác định")


def _get_wind_direction_text(degrees: float) -> str:
    """Chuyển độ hướng gió thành văn bản tiếng Việt"""
    if degrees is None:
        return None
    directions = [
        "Bắc", "Bắc Đông Bắc", "Đông Bắc", "Đông Đông Bắc",
        "Đông", "Đông Đông Nam", "Đông Nam", "Nam Đông Nam",
        "Nam", "Nam Tây Nam", "Tây Nam", "Tây Tây Nam",
        "Tây", "Tây Tây Bắc", "Tây Bắc", "Bắc Tây Bắc"
    ]
    index = round(degrees / 22.5) % 16
    return directions[index]


if __name__ == "__main__":
    # Test fetching weather for Hanoi
    print("Testing Open-Meteo API...")

    hanoi = VIETNAM_LOCATIONS["hanoi"]
    forecast = fetch_forecast_full(hanoi["lat"], hanoi["lon"])

    if forecast:
        print(f"\n=== Dự báo thời tiết Hà Nội ===")
        daily = forecast.get("daily", {})
        for i, date in enumerate(daily.get("time", [])[:7]):
            temp_max = daily.get("temperature_2m_max", [None])[i]
            temp_min = daily.get("temperature_2m_min", [None])[i]
            rain = daily.get("precipitation_sum", [0])[i]
            code = daily.get("weather_code", [0])[i]
            print(f"{date}: {temp_min:.1f}-{temp_max:.1f}°C | Mưa: {rain:.1f}mm | {get_weather_description(code)}")

    # Test flood API
    flood = fetch_flood_forecast(hanoi["lat"], hanoi["lon"])
    if flood:
        print(f"\n=== Dự báo lũ Hà Nội ===")
        flood_daily = flood.get("daily", {})
        for i, date in enumerate(flood_daily.get("time", [])[:7]):
            discharge = flood_daily.get("river_discharge", [None])[i]
            print(f"{date}: Lưu lượng sông: {discharge:.0f} m³/s" if discharge else f"{date}: Không có dữ liệu")
