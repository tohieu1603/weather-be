#!/usr/bin/env python3
import requests
import json
from datetime import datetime
from typing import Dict, List, Tuple

# Điểm quan trắc chính - Mở rộng toàn quốc 63 tỉnh thành
MONITORING_POINTS = {
    # === VÙNG ĐỒNG BẰNG SÔNG HỒNG (17 tỉnh) ===
    # Sông Hồng chính
    "lao_cai": {"lat": 22.4856, "lon": 103.9707, "river": "Hong", "type": "border"},
    "yen_bai": {"lat": 21.7168, "lon": 104.8987, "river": "Hong", "type": "upstream"},
    "ha_giang": {"lat": 22.8333, "lon": 104.9833, "river": "Lo", "type": "border"},
    "tuyen_quang": {"lat": 21.8167, "lon": 105.2167, "river": "Lo", "type": "upstream"},
    "phu_tho": {"lat": 21.4200, "lon": 105.2000, "river": "Hong", "type": "upstream"},
    "viet_tri": {"lat": 21.3100, "lon": 105.4019, "river": "Hong", "type": "confluence"},
    "son_tay": {"lat": 21.1333, "lon": 105.5000, "river": "Hong", "type": "key_gauge"},
    "hanoi": {"lat": 21.0285, "lon": 105.8542, "river": "Hong", "type": "capital"},
    "hai_phong": {"lat": 20.8449, "lon": 106.6881, "river": "Hong", "type": "coastal"},
    "hai_duong": {"lat": 20.9373, "lon": 106.3145, "river": "Hong", "type": "delta"},
    "hung_yen": {"lat": 20.6464, "lon": 106.0511, "river": "Hong", "type": "delta"},
    "thai_binh": {"lat": 20.4463, "lon": 106.3365, "river": "Hong", "type": "delta"},
    "nam_dinh": {"lat": 20.4388, "lon": 106.1621, "river": "Hong", "type": "delta"},
    "ninh_binh": {"lat": 20.2506, "lon": 105.9745, "river": "Hong", "type": "delta"},
    "ha_nam": {"lat": 20.5835, "lon": 105.9230, "river": "Hong", "type": "delta"},

    # Sông Đà và Tây Bắc
    "hoa_binh_dam": {"lat": 20.8167, "lon": 105.3167, "river": "Da", "type": "dam"},
    "son_la_dam": {"lat": 21.3261, "lon": 103.9008, "river": "Da", "type": "dam"},
    "dien_bien": {"lat": 21.3833, "lon": 103.0167, "river": "Da", "type": "border"},
    "lai_chau": {"lat": 22.3864, "lon": 103.4701, "river": "Da", "type": "upstream"},

    # Vùng núi Đông Bắc
    "cao_bang": {"lat": 22.6667, "lon": 106.2500, "river": "BangGiang", "type": "border"},
    "lang_son": {"lat": 21.8536, "lon": 106.7610, "river": "Ky_Cung", "type": "border"},
    "bac_kan": {"lat": 22.1471, "lon": 105.8348, "river": "Cau", "type": "upstream"},
    "thai_nguyen": {"lat": 21.5671, "lon": 105.8252, "river": "Cau", "type": "upstream"},
    "bac_giang": {"lat": 21.2819, "lon": 106.1946, "river": "Cau", "type": "midstream"},
    "quang_ninh": {"lat": 21.0064, "lon": 107.2925, "river": "Hong", "type": "coastal"},

    # === VÙNG BẮC TRUNG BỘ (6 tỉnh) ===
    "thanh_hoa": {"lat": 19.8067, "lon": 105.7851, "river": "Ma", "type": "central"},
    "nghe_an": {"lat": 18.6793, "lon": 105.6811, "river": "Lam", "type": "central"},
    "ha_tinh": {"lat": 18.3430, "lon": 105.9050, "river": "Ngan", "type": "central"},
    "quang_binh": {"lat": 17.4676, "lon": 106.6222, "river": "Gianh", "type": "central"},
    "quang_tri": {"lat": 16.7943, "lon": 107.1859, "river": "Thach_Han", "type": "central"},
    "thua_thien_hue": {"lat": 16.4637, "lon": 107.5909, "river": "Huong", "type": "central"},

    # === VÙNG DUY YÊN HẢI MIỀN TRUNG (8 tỉnh) ===
    "da_nang": {"lat": 16.0544, "lon": 108.2022, "river": "Han", "type": "central"},
    "quang_nam": {"lat": 15.5393, "lon": 108.0192, "river": "Thu_Bon", "type": "central"},
    "quang_ngai": {"lat": 15.1214, "lon": 108.8044, "river": "TraKhuc", "type": "central"},
    "binh_dinh": {"lat": 13.7830, "lon": 109.2192, "river": "Kon", "type": "central"},
    "phu_yen": {"lat": 13.0955, "lon": 109.0929, "river": "Ba", "type": "central"},
    "khanh_hoa": {"lat": 12.2585, "lon": 109.0526, "river": "Cai", "type": "coastal"},
    "ninh_thuan": {"lat": 11.6739, "lon": 108.8629, "river": "Dinh", "type": "coastal"},
    "binh_thuan": {"lat": 10.9273, "lon": 108.1017, "river": "La_Nga", "type": "coastal"},

    # === TÂY NGUYÊN (5 tỉnh) ===
    "kon_tum": {"lat": 14.3497, "lon": 108.0005, "river": "Dak_Bla", "type": "highland"},
    "gia_lai": {"lat": 13.9833, "lon": 108.0000, "river": "Ba", "type": "highland"},
    "dak_lak": {"lat": 12.6667, "lon": 108.0500, "river": "Srepok", "type": "highland"},
    "dak_nong": {"lat": 12.2646, "lon": 107.6098, "river": "Srepok", "type": "highland"},
    "lam_dong": {"lat": 11.9404, "lon": 108.4583, "river": "DongNai", "type": "highland"},

    # === ĐÔNG NAM BỘ (6 tỉnh) ===
    "binh_phuoc": {"lat": 11.7511, "lon": 106.7234, "river": "DongNai", "type": "upstream"},
    "tay_ninh": {"lat": 11.3351, "lon": 106.0987, "river": "Vam_Co", "type": "upstream"},
    "binh_duong": {"lat": 11.3254, "lon": 106.4770, "river": "DongNai", "type": "midstream"},
    "dong_nai": {"lat": 10.9574, "lon": 106.8426, "river": "DongNai", "type": "downstream"},
    "ba_ria_vung_tau": {"lat": 10.5417, "lon": 107.2429, "river": "DongNai", "type": "coastal"},
    "tp_ho_chi_minh": {"lat": 10.7769, "lon": 106.7009, "river": "SaiGon", "type": "delta"},
    "tri_an_dam": {"lat": 11.0833, "lon": 107.0167, "river": "DongNai", "type": "dam"},

    # === ĐỒNG BẰNG SÔNG CỬU LONG (13 tỉnh) ===
    # Sông Mekong chính
    "chiang_saen": {"lat": 20.2667, "lon": 100.0833, "river": "Mekong", "type": "thai_gauge"},
    "vientiane": {"lat": 17.9757, "lon": 102.6331, "river": "Mekong", "type": "lao_gauge"},
    "stung_treng": {"lat": 13.5167, "lon": 106.0167, "river": "Mekong", "type": "cambodia"},
    "tan_chau": {"lat": 10.8000, "lon": 105.2333, "river": "Tien", "type": "vn_entry"},
    "chau_doc": {"lat": 10.7000, "lon": 105.1167, "river": "Hau", "type": "vn_entry"},

    # Các tỉnh đồng bằng
    "long_an": {"lat": 10.5333, "lon": 106.4167, "river": "Vam_Co", "type": "delta"},
    "tien_giang": {"lat": 10.3600, "lon": 106.3600, "river": "Tien", "type": "delta"},
    "ben_tre": {"lat": 10.2333, "lon": 106.3833, "river": "Tien", "type": "delta"},
    "tra_vinh": {"lat": 9.8128, "lon": 106.2992, "river": "Hau", "type": "coastal"},
    "vinh_long": {"lat": 10.2395, "lon": 105.9572, "river": "Hau", "type": "delta"},
    "dong_thap": {"lat": 10.4938, "lon": 105.6881, "river": "Tien", "type": "delta"},
    "an_giang": {"lat": 10.5216, "lon": 105.1258, "river": "Hau", "type": "upstream_delta"},
    "kien_giang": {"lat": 10.0125, "lon": 105.0808, "river": "Hau", "type": "coastal"},
    "can_tho": {"lat": 10.0452, "lon": 105.7469, "river": "Hau", "type": "delta_center"},
    "hau_giang": {"lat": 9.7577, "lon": 105.6412, "river": "Hau", "type": "delta"},
    "soc_trang": {"lat": 9.6024, "lon": 105.9739, "river": "Hau", "type": "coastal"},
    "bac_lieu": {"lat": 9.2840, "lon": 105.7244, "river": "Hau", "type": "coastal"},
    "ca_mau": {"lat": 9.1767, "lon": 105.1524, "river": "Hau", "type": "coastal"},
}

# Trọng số Thiessen mẫu (thay bằng diện tích thực tế nếu có)
BASIN_WEIGHTS = {
    "HONG": {
        # Sông Hồng chính
        "lao_cai": 1.2,
        "yen_bai": 1.1,
        "ha_giang": 1.0,
        "tuyen_quang": 1.0,
        "phu_tho": 0.9,
        "viet_tri": 0.8,
        "son_tay": 0.7,
        "hanoi": 0.7,
        "hai_phong": 0.6,
        "hai_duong": 0.6,
        "hung_yen": 0.6,
        "thai_binh": 0.6,
        "nam_dinh": 0.6,
        "ninh_binh": 0.6,
        "ha_nam": 0.6,
        # Sông Đà
        "hoa_binh_dam": 1.0,
        "son_la_dam": 1.2,
        "dien_bien": 1.1,
        "lai_chau": 1.1,
        # Đông Bắc
        "cao_bang": 0.9,
        "lang_son": 0.9,
        "bac_kan": 0.9,
        "thai_nguyen": 0.8,
        "bac_giang": 0.7,
        "quang_ninh": 0.7,
    },
    "MEKONG": {
        # Mekong chính
        "chiang_saen": 1.5,
        "vientiane": 1.4,
        "stung_treng": 1.2,
        "tan_chau": 1.0,
        "chau_doc": 1.0,
        # Delta
        "long_an": 0.8,
        "tien_giang": 0.8,
        "ben_tre": 0.7,
        "tra_vinh": 0.7,
        "vinh_long": 0.8,
        "dong_thap": 0.8,
        "an_giang": 0.9,
        "kien_giang": 0.7,
        "can_tho": 0.8,
        "hau_giang": 0.7,
        "soc_trang": 0.7,
        "bac_lieu": 0.6,
        "ca_mau": 0.6,
    },
    "DONGNAI": {
        # Cao nguyên và thượng nguồn
        "lam_dong": 1.2,
        "binh_phuoc": 1.0,
        "tay_ninh": 0.9,
        "binh_duong": 0.8,
        "dong_nai": 0.8,
        "ba_ria_vung_tau": 0.7,
        "tp_ho_chi_minh": 0.7,
        "tri_an_dam": 1.0,
        # Tây Nguyên liên quan
        "dak_lak": 1.1,
        "dak_nong": 1.0,
    },
    "CENTRAL": {
        # Bắc Trung Bộ
        "thanh_hoa": 1.0,
        "nghe_an": 1.1,
        "ha_tinh": 1.0,
        "quang_binh": 1.0,
        "quang_tri": 1.0,
        "thua_thien_hue": 1.0,
        # Duyên hải miền Trung
        "da_nang": 1.0,
        "quang_nam": 1.1,
        "quang_ngai": 1.0,
        "binh_dinh": 1.0,
        "phu_yen": 1.0,
        "khanh_hoa": 0.9,
        "ninh_thuan": 0.8,
        "binh_thuan": 0.8,
        # Tây Nguyên
        "kon_tum": 1.1,
        "gia_lai": 1.1,
    },
}

# Ngưỡng cảnh báo lũ (mm/ngày và mm tích lũy)
FLOOD_THRESHOLDS = {
    "HONG": {
        "watch": {"daily": 100, "accumulated_3d": 250},
        "warning": {"daily": 150, "accumulated_3d": 400},
        "danger": {"daily": 200, "accumulated_3d": 600}
    },
    "MEKONG": {
        "watch": {"daily": 80, "accumulated_3d": 200},
        "warning": {"daily": 120, "accumulated_3d": 350},
        "danger": {"daily": 180, "accumulated_3d": 550}
    },
    "DONGNAI": {
        "watch": {"daily": 100, "accumulated_3d": 250},
        "warning": {"daily": 150, "accumulated_3d": 400},
        "danger": {"daily": 200, "accumulated_3d": 600}
    },
    "CENTRAL": {
        "watch": {"daily": 120, "accumulated_3d": 300},
        "warning": {"daily": 200, "accumulated_3d": 500},
        "danger": {"daily": 300, "accumulated_3d": 800}
    }
}

BASE_URL = "https://api.open-meteo.com/v1/forecast"
PARAMS = {
    "hourly": "precipitation,rain,showers,snowfall",
    "daily": "precipitation_sum,precipitation_hours,precipitation_probability_max",
    "forecast_days": 16,
    "timezone": "Asia/Ho_Chi_Minh",
}


def fetch_weather_data(lat: float, lon: float) -> Dict:
    """Lấy dữ liệu thời tiết từ Open-Meteo API"""
    resp = requests.get(
        BASE_URL,
        params={**PARAMS, "latitude": lat, "longitude": lon},
        timeout=20
    )
    resp.raise_for_status()
    return resp.json()


def calculate_basin_rainfall(points_data: Dict, basin_weights: Dict) -> float:
    """
    Tính lượng mưa trung bình lưu vực theo phương pháp Thiessen Polygon

    Công thức: P_basin = Σ(Pi × Ai) / Σ(Ai)

    Args:
        points_data: Dict chứa dữ liệu mưa của các trạm
        basin_weights: Dict chứa trọng số diện tích của các trạm

    Returns:
        Lượng mưa trung bình lưu vực (mm)
    """
    total_weighted = 0.0
    total_area = 0.0

    for station, data in points_data.items():
        weight = basin_weights.get(station, 0)
        rain = data.get("precipitation_sum")
        if weight <= 0 or rain is None:
            continue
        total_weighted += rain * weight
        total_area += weight

    return total_weighted / total_area if total_area > 0 else 0.0


def assess_flood_risk(daily_rain: float, accumulated_3d: float, thresholds: Dict) -> Tuple[str, str]:
    """
    Đánh giá mức độ nguy cơ lũ

    Returns:
        (risk_level, description)
    """
    if daily_rain >= thresholds["danger"]["daily"] or accumulated_3d >= thresholds["danger"]["accumulated_3d"]:
        return "NGUY HIỂM", "⛔ Nguy cơ lũ lớn - cần sơ tán khẩn cấp"
    elif daily_rain >= thresholds["warning"]["daily"] or accumulated_3d >= thresholds["warning"]["accumulated_3d"]:
        return "CẢNH BÁO", "⚠️  Nguy cơ lũ cao - chuẩn bị sơ tán"
    elif daily_rain >= thresholds["watch"]["daily"] or accumulated_3d >= thresholds["watch"]["accumulated_3d"]:
        return "THEO DÕI", "⚡ Nguy cơ lũ - theo dõi chặt chẽ"
    else:
        return "AN TOÀN", "✓ Trong ngưỡng an toàn"


def analyze_basin_forecast(basin_name: str, basin_rainfall: List[float],
                          dates: List[str], thresholds: Dict) -> Dict:
    """
    Phân tích dự báo lũ cho lưu vực

    Returns:
        Dict chứa thông tin phân tích và cảnh báo
    """
    analysis = {
        "basin": basin_name,
        "forecast_days": [],
        "max_daily_rain": 0,
        "max_daily_date": "",
        "warnings": []
    }

    for idx, (date, rain) in enumerate(zip(dates, basin_rainfall)):
        # Tính mưa tích lũy 3 ngày
        accumulated_3d = sum(basin_rainfall[max(0, idx-2):idx+1])

        # Đánh giá nguy cơ
        risk_level, risk_desc = assess_flood_risk(rain, accumulated_3d, thresholds)

        day_info = {
            "date": date,
            "daily_rain": round(rain, 2),
            "accumulated_3d": round(accumulated_3d, 2),
            "risk_level": risk_level,
            "risk_description": risk_desc
        }

        analysis["forecast_days"].append(day_info)

        # Theo dõi ngày có mưa lớn nhất
        if rain > analysis["max_daily_rain"]:
            analysis["max_daily_rain"] = rain
            analysis["max_daily_date"] = date

        # Thu thập cảnh báo
        if risk_level in ["CẢNH BÁO", "NGUY HIỂM"]:
            analysis["warnings"].append(day_info)

    return analysis


def print_basin_report(analysis: Dict):
    """In báo cáo chi tiết cho lưu vực"""
    print(f"\n{'='*80}")
    print(f"🌊 LƯU VỰC: {analysis['basin'].upper()}")
    print(f"{'='*80}")

    # Tổng quan
    print(f"\n📊 TỔNG QUAN:")
    print(f"  • Ngày có mưa lớn nhất: {analysis['max_daily_date']} ({analysis['max_daily_rain']:.2f} mm)")
    print(f"  • Số ngày cảnh báo: {len(analysis['warnings'])} ngày")

    # Cảnh báo nổi bật
    if analysis["warnings"]:
        print(f"\n🚨 CẢNH BÁO NỔI BẬT:")
        for warning in analysis["warnings"]:
            print(f"  {warning['date']} - {warning['risk_level']}")
            print(f"    └─ Mưa: {warning['daily_rain']:.2f} mm | Tích lũy 3d: {warning['accumulated_3d']:.2f} mm")
            print(f"    └─ {warning['risk_description']}")

    # Dự báo 7 ngày tới
    print(f"\n📅 DỰ BÁO 7 NGÀY TỚI:")
    print(f"{'Ngày':<12} {'Mưa(mm)':<12} {'TL 3d(mm)':<12} {'Mức độ':<15} {'Trạng thái'}")
    print(f"{'-'*80}")

    for day in analysis["forecast_days"][:7]:
        status_icon = "⛔" if day["risk_level"] == "NGUY HIỂM" else \
                     "⚠️ " if day["risk_level"] == "CẢNH BÁO" else \
                     "⚡" if day["risk_level"] == "THEO DÕI" else "✓"
        print(f"{day['date']:<12} {day['daily_rain']:<12.2f} {day['accumulated_3d']:<12.2f} "
              f"{day['risk_level']:<15} {status_icon}")


def export_results(all_analysis: Dict[str, Dict], filename: str = "flood_forecast.json"):
    """Export kết quả ra file JSON"""
    output = {
        "generated_at": datetime.now().isoformat(),
        "basins": all_analysis
    }

    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n💾 Đã lưu kết quả vào: {filename}")


def main():
    print("🌧️  HỆ THỐNG DỰ BÁO THIÊN TAI LŨ LỤT")
    print(f"⏰ Thời gian: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📍 Số điểm quan trắc: {len(MONITORING_POINTS)}")

    # Bước 1: Lấy dữ liệu từ API
    print(f"\n🔄 Đang lấy dữ liệu từ {len(MONITORING_POINTS)} điểm quan trắc...")
    station_data = {}
    dates_ref = None

    for code, info in MONITORING_POINTS.items():
        try:
            data = fetch_weather_data(info["lat"], info["lon"])
            if dates_ref is None:
                dates_ref = data["daily"]["time"]
            station_data[code] = data["daily"]["precipitation_sum"]
            print(f"  ✓ {code}")
        except Exception as e:
            print(f"  ✗ {code}: {e}")

    if not dates_ref:
        raise SystemExit("❌ Không lấy được dữ liệu nào")

    print(f"✅ Đã lấy dữ liệu thành công cho {len(station_data)} điểm")

    # Bước 2: Phân tích từng lưu vực
    all_analysis = {}

    for basin, weights in BASIN_WEIGHTS.items():
        # Tính lượng mưa lưu vực theo ngày
        basin_rainfall = []
        for idx in range(len(dates_ref)):
            day_points = {
                st: {"precipitation_sum": station_data.get(st, [0] * len(dates_ref))[idx]}
                for st in weights.keys()
            }
            basin_rain = calculate_basin_rainfall(day_points, weights)
            basin_rainfall.append(basin_rain)

        # Phân tích và đánh giá nguy cơ
        thresholds = FLOOD_THRESHOLDS.get(basin, FLOOD_THRESHOLDS["Central"])
        analysis = analyze_basin_forecast(basin, basin_rainfall, dates_ref, thresholds)
        all_analysis[basin] = analysis

        # In báo cáo
        print_basin_report(analysis)

    # Bước 3: Export kết quả
    export_results(all_analysis)

    print(f"\n{'='*80}")
    print("✅ Hoàn thành phân tích dự báo lũ!")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
