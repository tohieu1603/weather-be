#!/usr/bin/env python3
"""
Module phân tích lũ nâng cao
Bao gồm các phương pháp thủy văn và thống kê cho dự báo lũ
"""

import numpy as np
from typing import Dict, List, Tuple
from datetime import datetime, timedelta


def calculate_basin_rainfall_thiessen(points_data: Dict, basin_weights: Dict) -> Tuple[float, Dict]:
    """
    Tính lượng mưa trung bình lưu vực theo phương pháp Thiessen Polygon

    Công thức: P_basin = Σ(Pi × Ai) / Σ(Ai)

    Trong đó:
    - Pi: Lượng mưa tại trạm i (mm)
    - Ai: Diện tích ảnh hưởng của trạm i (km²) - được thể hiện bằng weight

    Args:
        points_data: Dict chứa dữ liệu mưa của các trạm
                     Format: {"station_code": {"precipitation_sum": value}}
        basin_weights: Dict chứa trọng số diện tích của các trạm
                      Format: {"station_code": weight}

    Returns:
        Tuple:
        - float: Lượng mưa trung bình lưu vực (mm)
        - Dict: Chi tiết tính toán cho từng trạm
    """
    total_weighted_rainfall = 0.0
    total_area = 0.0
    details = {}

    for station, data in points_data.items():
        weight = basin_weights.get(station, 0)
        rainfall = data.get('precipitation_sum', 0) or 0

        if weight > 0:
            weighted_rain = rainfall * weight
            total_weighted_rainfall += weighted_rain
            total_area += weight

            details[station] = {
                "rainfall": rainfall,
                "weight": weight,
                "weighted_rainfall": weighted_rain
            }

    basin_avg = total_weighted_rainfall / total_area if total_area > 0 else 0

    return basin_avg, details


def calculate_accumulated_rainfall(daily_rainfall: List[float], days: int = 3) -> List[float]:
    """
    Tính lượng mưa tích lũy cho mỗi ngày

    Args:
        daily_rainfall: Danh sách lượng mưa hàng ngày (mm)
        days: Số ngày tích lũy (mặc định 3 ngày)

    Returns:
        List[float]: Lượng mưa tích lũy cho từng ngày
    """
    accumulated = []

    for i in range(len(daily_rainfall)):
        start_idx = max(0, i - days + 1)
        acc_rain = sum(daily_rainfall[start_idx:i+1])
        accumulated.append(acc_rain)

    return accumulated


def calculate_return_period_gumbel(discharge: float, historical_data: List[float]) -> Dict:
    """
    Tính chu kỳ lặp lại của lũ (Return Period) theo phân phối Gumbel

    Công thức Gumbel: T = 1 / (1 - F(x))

    Trong đó:
    - T: Chu kỳ lặp lại (năm)
    - F(x): Hàm phân phối tích lũy
    - x: Lưu lượng đỉnh lũ (m³/s)

    Phân phối Gumbel (Type I Extreme Value):
    F(x) = exp(-exp(-(x-μ)/β))

    Parameters:
    - μ (location): mean - 0.5772 * β
    - β (scale): std * √6 / π
    - 0.5772: Euler-Mascheroni constant

    Args:
        discharge: Lưu lượng cần tính (m³/s)
        historical_data: Dữ liệu lịch sử lưu lượng đỉnh lũ hàng năm

    Returns:
        Dict chứa:
        - return_period: Chu kỳ lặp lại (năm)
        - probability: Xác suất xảy ra trong 1 năm
        - category: Phân loại mức độ (common, rare, very_rare, extreme)
        - gumbel_params: Tham số phân phối Gumbel
    """
    if not historical_data or len(historical_data) < 3:
        return {
            "return_period": None,
            "probability": None,
            "category": "insufficient_data",
            "error": "Cần ít nhất 3 năm dữ liệu lịch sử"
        }

    mean = np.mean(historical_data)
    std = np.std(historical_data)

    # Kiểm tra std = 0 (dữ liệu không đổi)
    if std == 0 or std < 0.01:
        return {
            "return_period": 1.0,
            "probability": 100.0,
            "category": "common",
            "interpretation": "Dữ liệu không thay đổi, không thể tính Return Period",
            "gumbel_params": {"mu": mean, "beta": 0, "mean": mean, "std": std}
        }

    # Euler-Mascheroni constant
    EULER = 0.5772156649

    # Gumbel parameters
    beta = std * np.sqrt(6) / np.pi
    mu = mean - EULER * beta

    # Cumulative Distribution Function (CDF)
    z = -(discharge - mu) / beta
    F = np.exp(-np.exp(z))

    # Return period T = 1 / (1 - F)
    if F >= 0.9999:  # Tránh chia cho 0
        return_period = float('inf')
        probability = 0.0
    else:
        return_period = 1.0 / (1.0 - F)
        probability = 1.0 / return_period

    # Phân loại
    if return_period < 2:
        category = "common"  # Xảy ra thường xuyên
    elif return_period < 10:
        category = "moderate"  # Trung bình
    elif return_period < 50:
        category = "rare"  # Hiếm
    elif return_period < 100:
        category = "very_rare"  # Rất hiếm
    else:
        category = "extreme"  # Cực hiếm

    return {
        "return_period": round(return_period, 2),
        "probability": round(probability * 100, 2),  # %
        "category": category,
        "gumbel_params": {
            "mu": round(mu, 2),
            "beta": round(beta, 2),
            "mean": round(mean, 2),
            "std": round(std, 2)
        },
        "cdf": round(F, 4)
    }


def estimate_discharge_from_rainfall(
    basin_rainfall: float,
    basin_area: float,
    curve_number: int = 75,
    time_concentration: float = 6.0
) -> Dict:
    """
    Ước tính lưu lượng đỉnh lũ từ lượng mưa bằng phương pháp SCS Curve Number

    Phương pháp SCS-CN (Soil Conservation Service - Curve Number):

    1. Tính Runoff (Dòng chảy mặt):
       Q = (P - Ia)² / (P - Ia + S)

       Trong đó:
       - Q: Runoff (mm)
       - P: Precipitation (lượng mưa, mm)
       - Ia: Initial abstraction = 0.2 * S
       - S: Potential maximum retention = (25400/CN) - 254
       - CN: Curve Number (30-100)

    2. Ước tính lưu lượng đỉnh (Peak discharge):
       Qp = (C * A * Q) / Tc

       Trong đó:
       - Qp: Peak discharge (m³/s)
       - C: Runoff coefficient (0.6-0.9)
       - A: Basin area (km²)
       - Q: Runoff depth (mm)
       - Tc: Time of concentration (hours)

    Args:
        basin_rainfall: Lượng mưa lưu vực (mm)
        basin_area: Diện tích lưu vực (km²)
        curve_number: Curve Number (30-100), mặc định 75 (đất trung bình)
        time_concentration: Thời gian tập trung (giờ), mặc định 6h

    Returns:
        Dict chứa:
        - peak_discharge: Lưu lượng đỉnh ước tính (m³/s)
        - runoff: Dòng chảy mặt (mm)
        - runoff_coefficient: Hệ số dòng chảy
        - method: Phương pháp tính
    """
    # SCS Curve Number method
    S = (25400.0 / curve_number) - 254.0  # mm
    Ia = 0.2 * S  # Initial abstraction

    # Calculate runoff
    if basin_rainfall <= Ia:
        runoff = 0.0
    else:
        runoff = ((basin_rainfall - Ia) ** 2) / (basin_rainfall - Ia + S)

    # Runoff coefficient
    runoff_coeff = runoff / basin_rainfall if basin_rainfall > 0 else 0

    # Peak discharge estimation (simplified rational method)
    # Qp = C * i * A / 3.6
    # Với i = intensity (mm/h) = runoff / Tc
    # C = runoff coefficient

    if time_concentration > 0 and runoff > 0:
        intensity = runoff / time_concentration  # mm/h
        # Convert to m³/s: C * i(mm/h) * A(km²) / 3.6
        peak_discharge = runoff_coeff * intensity * basin_area / 3.6
    else:
        peak_discharge = 0.0

    return {
        "peak_discharge": round(peak_discharge, 2),
        "runoff": round(runoff, 2),
        "runoff_coefficient": round(runoff_coeff, 3),
        "potential_retention_s": round(S, 2),
        "initial_abstraction_ia": round(Ia, 2),
        "method": "SCS-CN",
        "curve_number": curve_number
    }


def classify_flood_severity(
    discharge: float = None,
    rainfall: float = None,
    accumulated_3d: float = None,
    thresholds: Dict = None
) -> Dict:
    """
    Phân loại mức độ nghiêm trọng của lũ

    Args:
        discharge: Lưu lượng (m³/s)
        rainfall: Lượng mưa ngày (mm)
        accumulated_3d: Lượng mưa tích lũy 3 ngày (mm)
        thresholds: Ngưỡng cảnh báo

    Returns:
        Dict chứa phân loại và khuyến nghị
    """
    severity = "safe"
    alert_level = 0
    recommendations = []

    if thresholds and rainfall and accumulated_3d:
        # Kiểm tra ngưỡng
        if (rainfall >= thresholds["danger"]["daily"] or
            accumulated_3d >= thresholds["danger"]["accumulated_3d"]):
            severity = "danger"
            alert_level = 4
            recommendations = [
                "⛔ NGUY HIỂM: Sơ tán khẩn cấp người dân vùng trũng",
                "Chuẩn bị phương án cứu hộ, cứu nạn",
                "Đóng cửa xả đập nếu có",
                "Cảnh báo toàn bộ dân cư hạ du"
            ]
        elif (rainfall >= thresholds["warning"]["daily"] or
              accumulated_3d >= thresholds["warning"]["accumulated_3d"]):
            severity = "warning"
            alert_level = 3
            recommendations = [
                "⚠️ CẢNH BÁO: Chuẩn bị sơ tán người dân vùng nguy hiểm",
                "Tăng cường quan trắc mực nước",
                "Kiểm tra hệ thống thoát nước",
                "Thông báo rộng rãi cho dân cư"
            ]
        elif (rainfall >= thresholds["watch"]["daily"] or
              accumulated_3d >= thresholds["watch"]["accumulated_3d"]):
            severity = "watch"
            alert_level = 2
            recommendations = [
                "⚡ THEO DÕI: Theo dõi chặt chẽ diễn biến thời tiết",
                "Chuẩn bị phương án ứng phó",
                "Kiểm tra khu vực trũng thấp",
                "Thông báo đến chính quyền địa phương"
            ]
        else:
            severity = "safe"
            alert_level = 1
            recommendations = [
                "✅ AN TOÀN: Tình hình bình thường",
                "Tiếp tục theo dõi dự báo thời tiết"
            ]

    return {
        "severity": severity,
        "alert_level": alert_level,
        "recommendations": recommendations,
        "discharge": discharge,
        "rainfall_daily": rainfall,
        "rainfall_3d": accumulated_3d
    }


def analyze_flood_trend(daily_rainfall: List[float], window: int = 3) -> Dict:
    """
    Phân tích xu hướng lũ

    Args:
        daily_rainfall: Lượng mưa hàng ngày
        window: Cửa sổ phân tích (ngày)

    Returns:
        Dict chứa xu hướng và dự đoán
    """
    if len(daily_rainfall) < window:
        return {
            "trend": "insufficient_data",
            "slope": 0,
            "prediction": "unknown"
        }

    # Tính slope của window gần nhất
    recent = daily_rainfall[-window:]
    x = np.arange(len(recent))
    slope = np.polyfit(x, recent, 1)[0]

    # Phân loại xu hướng
    if slope > 10:
        trend = "increasing_fast"
        prediction = "Nguy cơ lũ tăng nhanh"
    elif slope > 5:
        trend = "increasing"
        prediction = "Nguy cơ lũ đang tăng"
    elif slope > -5:
        trend = "stable"
        prediction = "Tình hình ổn định"
    elif slope > -10:
        trend = "decreasing"
        prediction = "Nguy cơ lũ đang giảm"
    else:
        trend = "decreasing_fast"
        prediction = "Nguy cơ lũ giảm nhanh"

    return {
        "trend": trend,
        "slope": round(slope, 2),
        "prediction": prediction,
        "recent_avg": round(np.mean(recent), 2),
        "recent_max": round(np.max(recent), 2)
    }


# Curve Number reference values
CN_VALUES = {
    "urban_high_density": 85,      # Đô thị mật độ cao
    "urban_medium_density": 75,    # Đô thị mật độ trung bình
    "agricultural": 70,            # Đất nông nghiệp
    "forest_good": 55,             # Rừng tốt
    "forest_poor": 70,             # Rừng xấu
    "grassland": 65,               # Đồng cỏ
    "water": 100                   # Mặt nước
}

# Basin area estimates (km²) - Approximate values
BASIN_AREAS = {
    "HONG": 169000,      # Sông Hồng - Thái Bình
    "MEKONG": 795000,    # Mekong (toàn lưu vực)
    "DONGNAI": 44000,    # Đồng Nai
    "CENTRAL": 50000     # Miền Trung (tổng các lưu vực)
}


# ==================================================================================
# PHẦN 2: CÔNG THỨC THỦY VĂN CỐT LÕI
# ==================================================================================

def reservoir_water_balance(
    S_current: float,
    inflow: float,
    outflow: float,
    evap: float,
    seepage: float,
    dt: float = 3600
) -> Dict:
    """
    A. Phương trình cân bằng nước hồ chứa

    Công thức: dS/dt = I(t) - O(t) - E(t) - L(t)

    Trong đó:
    - S: Dung tích hồ chứa (m³)
    - I(t): Lưu lượng đến - inflow (m³/s)
    - O(t): Lưu lượng xả - outflow (m³/s)
    - E(t): Bốc hơi - evaporation (m³/s)
    - L(t): Thất thoát/thấm - seepage (m³/s)

    Parameters:
    - S_current: Dung tích hiện tại (m³)
    - inflow: Lưu lượng đến (m³/s)
    - outflow: Lưu lượng xả (m³/s)
    - evap: Bốc hơi (m³/s)
    - seepage: Thất thoát (m³/s)
    - dt: Bước thời gian (s), mặc định 3600s = 1 giờ

    Returns:
    - Dict chứa S_new và các thông tin chi tiết
    """
    # Tính biến thiên dung tích
    dS_dt = inflow - outflow - evap - seepage
    dS = dS_dt * dt

    # Dung tích mới
    S_new = max(0, S_current + dS)

    # Tỷ lệ thay đổi
    change_percent = (dS / S_current * 100) if S_current > 0 else 0

    return {
        "S_current": round(S_current, 2),
        "S_new": round(S_new, 2),
        "dS": round(dS, 2),
        "dS_dt": round(dS_dt, 4),
        "inflow": round(inflow, 2),
        "outflow": round(outflow, 2),
        "evaporation": round(evap, 2),
        "seepage": round(seepage, 2),
        "dt_hours": dt / 3600,
        "change_percent": round(change_percent, 3),
        "status": "increasing" if dS > 0 else "decreasing" if dS < 0 else "stable"
    }


def muskingum_cunge_routing(
    inflow: List[float],
    K: float,
    X: float = 0.2,
    dt: float = 3600
) -> Dict:
    """
    B. Mô hình truyền lũ Muskingum-Cunge

    Công thức diễn toán:
    O(j+1) = C1*I(j+1) + C2*I(j) + C3*O(j)

    Trong đó:
    - K: Hằng số thời gian truyền lũ (s)
    - X: Hệ số trọng số (0 ≤ X ≤ 0.5), mặc định 0.2
    - Δt: Bước thời gian (s)

    Hệ số:
    C1 = (Δt - 2KX) / (2K(1-X) + Δt)
    C2 = (Δt + 2KX) / (2K(1-X) + Δt)
    C3 = (2K(1-X) - Δt) / (2K(1-X) + Δt)

    Điều kiện ổn định: C1, C2, C3 ≥ 0 và C1 + C2 + C3 = 1

    Parameters:
    - inflow: Chuỗi lưu lượng đến (m³/s)
    - K: Hằng số thời gian (s), thường = thời gian truyền lũ
    - X: Hệ số trọng số (0-0.5), X=0: hồ chứa, X=0.5: kênh thẳng
    - dt: Bước thời gian (s)

    Returns:
    - Dict chứa outflow và thông tin diễn toán
    """
    # Validate input
    if not (0 <= X <= 0.5):
        raise ValueError("X phải trong khoảng [0, 0.5]")

    if K <= 0 or dt <= 0:
        raise ValueError("K và dt phải dương")

    # Tính các hệ số Muskingum-Cunge
    denom = 2 * K * (1 - X) + dt
    C1 = (dt - 2 * K * X) / denom
    C2 = (dt + 2 * K * X) / denom
    C3 = (2 * K * (1 - X) - dt) / denom

    # Kiểm tra điều kiện ổn định
    coeff_sum = C1 + C2 + C3
    is_stable = (
        abs(coeff_sum - 1.0) < 0.001 and
        C1 >= 0 and C2 >= 0 and C3 >= 0
    )

    if not is_stable:
        return {
            "error": "Mô hình không ổn định",
            "coefficients": {"C1": C1, "C2": C2, "C3": C3},
            "sum": coeff_sum,
            "suggestion": "Giảm dt hoặc tăng K để ổn định"
        }

    # Diễn toán lũ
    outflow = [inflow[0]]  # Điều kiện ban đầu: O(0) = I(0)

    for j in range(len(inflow) - 1):
        O_new = C1 * inflow[j + 1] + C2 * inflow[j] + C3 * outflow[j]
        outflow.append(O_new)

    # Tính peak attenuation và lag time
    peak_inflow_idx = np.argmax(inflow)
    peak_outflow_idx = np.argmax(outflow)
    peak_inflow = inflow[peak_inflow_idx]
    peak_outflow = outflow[peak_outflow_idx]

    attenuation = ((peak_inflow - peak_outflow) / peak_inflow * 100) if peak_inflow > 0 else 0
    lag_time = (peak_outflow_idx - peak_inflow_idx) * dt / 3600  # hours

    return {
        "inflow": [round(q, 2) for q in inflow],
        "outflow": [round(q, 2) for q in outflow],
        "coefficients": {
            "C1": round(C1, 4),
            "C2": round(C2, 4),
            "C3": round(C3, 4),
            "sum": round(C1 + C2 + C3, 4)
        },
        "parameters": {
            "K_hours": round(K / 3600, 2),
            "X": X,
            "dt_hours": round(dt / 3600, 2)
        },
        "analysis": {
            "peak_inflow": round(peak_inflow, 2),
            "peak_outflow": round(peak_outflow, 2),
            "attenuation_percent": round(attenuation, 2),
            "lag_time_hours": round(lag_time, 2),
            "peak_inflow_time": peak_inflow_idx,
            "peak_outflow_time": peak_outflow_idx
        },
        "is_stable": is_stable,
        "method": "Muskingum-Cunge"
    }


def calculate_travel_time(
    distance: float,
    slope: float,
    manning_n: float,
    hydraulic_radius: float
) -> Dict:
    """
    C. Tính thời gian truyền lũ từ điểm A đến điểm B

    Công thức Manning: V = (1/n) * R^(2/3) * S^(1/2)

    Trong đó:
    - V: Vận tốc dòng chảy (m/s)
    - n: Hệ số nhám Manning
    - R: Bán kính thủy lực (m)
    - S: Độ dốc lòng sông (m/m)

    Bán kính thủy lực: R = A/P
    - A: Diện tích mặt cắt ướt (m²)
    - P: Chu vi ướt (m)

    Parameters:
    - distance: Khoảng cách (km)
    - slope: Độ dốc lòng sông (m/m)
    - manning_n: Hệ số nhám Manning (0.02-0.15)
    - hydraulic_radius: Bán kính thủy lực (m)

    Manning's n values:
    - Kênh bê tông: 0.012 - 0.015
    - Sông có đá nhỏ: 0.030 - 0.040
    - Sông có cây cối: 0.050 - 0.150

    Returns:
    - Dict chứa thời gian truyền và vận tốc
    """
    # Validate input
    if distance <= 0 or slope <= 0 or manning_n <= 0 or hydraulic_radius <= 0:
        raise ValueError("Tất cả tham số phải dương")

    if not (0.01 <= manning_n <= 0.20):
        raise ValueError("Manning's n phải trong khoảng [0.01, 0.20]")

    # Công thức Manning: V = (1/n) * R^(2/3) * S^(1/2)
    velocity = (1 / manning_n) * (hydraulic_radius ** (2/3)) * (slope ** 0.5)

    # Thời gian truyền
    distance_m = distance * 1000  # km to m
    travel_time_seconds = distance_m / velocity
    travel_time_hours = travel_time_seconds / 3600

    # Phân loại vận tốc
    if velocity < 0.3:
        velocity_class = "very_slow"
        description = "Dòng chảy rất chậm"
    elif velocity < 0.6:
        velocity_class = "slow"
        description = "Dòng chảy chậm"
    elif velocity < 1.0:
        velocity_class = "moderate"
        description = "Dòng chảy trung bình"
    elif velocity < 2.0:
        velocity_class = "fast"
        description = "Dòng chảy nhanh"
    else:
        velocity_class = "very_fast"
        description = "Dòng chảy rất nhanh"

    return {
        "distance_km": round(distance, 2),
        "velocity_m_s": round(velocity, 3),
        "velocity_km_h": round(velocity * 3.6, 2),
        "travel_time_hours": round(travel_time_hours, 2),
        "travel_time_minutes": round(travel_time_hours * 60, 1),
        "travel_time_days": round(travel_time_hours / 24, 2),
        "velocity_class": velocity_class,
        "description": description,
        "parameters": {
            "slope": slope,
            "manning_n": manning_n,
            "hydraulic_radius": round(hydraulic_radius, 2)
        },
        "formula": "Manning: V = (1/n) * R^(2/3) * S^(1/2)"
    }


def calculate_flood_wave_celerity(discharge: float, width: float, depth: float) -> Dict:
    """
    Tính vận tốc truyền sóng lũ (Flood wave celerity)

    Công thức: c = dQ/dA = (5/3) * V

    Trong đó:
    - c: Vận tốc sóng lũ (m/s)
    - V: Vận tốc dòng chảy bình quân (m/s)
    - Q: Lưu lượng (m³/s)
    - A: Diện tích mặt cắt (m²)

    Parameters:
    - discharge: Lưu lượng (m³/s)
    - width: Bề rộng lòng sông (m)
    - depth: Độ sâu trung bình (m)

    Returns:
    - Dict chứa vận tốc sóng lũ
    """
    area = width * depth
    velocity = discharge / area if area > 0 else 0
    wave_celerity = (5/3) * velocity

    return {
        "discharge": round(discharge, 2),
        "cross_section_area": round(area, 2),
        "mean_velocity": round(velocity, 3),
        "wave_celerity": round(wave_celerity, 3),
        "ratio_c_to_v": round(wave_celerity / velocity, 2) if velocity > 0 else 0,
        "interpretation": "Sóng lũ truyền nhanh hơn dòng nước khoảng 1.67 lần"
    }


# ==================================================================================
# WRAPPER FUNCTIONS - Tương thích với các tên gọi khác
# ==================================================================================

def calculate_thiessen_rainfall(rainfall_data: Dict[str, float], weights: Dict[str, float]) -> Dict:
    """
    Wrapper function cho Thiessen Polygon với interface đơn giản hơn

    Args:
        rainfall_data: Dict {station_name: total_rainfall}
        weights: Dict {station_name: weight}

    Returns:
        Dict chứa basin_average và chi tiết
    """
    total_weighted = 0.0
    total_weight = 0.0

    for station, rainfall in rainfall_data.items():
        weight = weights.get(station, 0)
        total_weighted += rainfall * weight
        total_weight += weight

    basin_average = total_weighted / total_weight if total_weight > 0 else 0

    return {
        "basin_average": basin_average,
        "weighted_sum": total_weighted,
        "total_weight": total_weight,
        "method": "Thiessen Polygon"
    }


def estimate_discharge_scs(
    rainfall: float,
    area_km2: float,
    curve_number: int = 70,
    time_of_concentration: float = 6.0
) -> Dict:
    """
    Ước tính lưu lượng đỉnh bằng phương pháp SCS Curve Number

    Args:
        rainfall: Lượng mưa (mm)
        area_km2: Diện tích lưu vực (km²)
        curve_number: Curve Number (30-100)
        time_of_concentration: Thời gian tập trung (giờ)

    Returns:
        Dict chứa peak_discharge và các thông số
    """
    # SCS Curve Number method
    # S = (25400/CN) - 254 (mm)
    S = (25400 / curve_number) - 254

    # Initial abstraction
    Ia = 0.2 * S

    # Runoff depth (mm)
    if rainfall > Ia:
        runoff = ((rainfall - Ia) ** 2) / (rainfall - Ia + S)
    else:
        runoff = 0

    # Runoff coefficient
    runoff_coef = runoff / rainfall if rainfall > 0 else 0

    # Peak discharge (m³/s) - simplified rational method
    # Qp = C * A * Q / Tc
    C = runoff_coef
    peak_discharge = (C * area_km2 * runoff) / (3.6 * time_of_concentration) if time_of_concentration > 0 else 0

    return {
        "peak_discharge": peak_discharge,
        "runoff": runoff,
        "runoff_coefficient": runoff_coef,
        "potential_retention_s": S,
        "initial_abstraction_ia": Ia,
        "method": "SCS-CN",
        "curve_number": curve_number
    }


def calculate_return_period(discharge: float, historical_data: List[float]) -> Dict:
    """
    Wrapper cho return period sử dụng Gumbel distribution
    """
    return calculate_return_period_gumbel(discharge, historical_data)


def analyze_trend(daily_data: List[float]) -> Dict:
    """
    Phân tích xu hướng dữ liệu theo thời gian

    Args:
        daily_data: Chuỗi dữ liệu theo ngày

    Returns:
        Dict chứa trend, slope, prediction
    """
    if len(daily_data) < 2:
        return {
            "trend": "stable",
            "slope": 0,
            "prediction": "Không đủ dữ liệu để phân tích xu hướng"
        }

    # Linear regression
    x = np.arange(len(daily_data))
    y = np.array(daily_data)

    # Calculate slope using least squares
    n = len(x)
    slope = (n * np.sum(x * y) - np.sum(x) * np.sum(y)) / (n * np.sum(x**2) - (np.sum(x))**2)

    # Classify trend
    if slope > 10:
        trend = "increasing_fast"
        prediction = "Nguy cơ lũ đang tăng nhanh"
    elif slope > 5:
        trend = "increasing"
        prediction = "Nguy cơ lũ đang tăng"
    elif slope > -5:
        trend = "stable"
        prediction = "Tình hình ổn định"
    elif slope > -10:
        trend = "decreasing"
        prediction = "Nguy cơ lũ đang giảm"
    else:
        trend = "decreasing_fast"
        prediction = "Nguy cơ lũ đang giảm nhanh"

    return {
        "trend": trend,
        "slope": slope,
        "prediction": prediction,
        "recent_avg": float(np.mean(daily_data[-3:])) if len(daily_data) >= 3 else float(np.mean(daily_data)),
        "recent_max": float(np.max(daily_data[-3:])) if len(daily_data) >= 3 else float(np.max(daily_data))
    }
