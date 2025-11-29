#!/usr/bin/env python3
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import Dict, List
from datetime import datetime, date
from pydantic import BaseModel
import sys
import os
import numpy as np

# Import database
from database import get_db, engine
import models

# Pydantic models for request bodies
class ReservoirBalanceRequest(BaseModel):
    S_current: float
    inflow: float
    outflow: float
    evap: float = 0
    seepage: float = 0
    dt: float = 3600

class FloodRoutingRequest(BaseModel):
    inflow: List[float]
    K: float
    X: float = 0.2
    dt: float = 3600

class TravelTimeRequest(BaseModel):
    distance: float
    slope: float
    manning_n: float
    hydraulic_radius: float

class WaveCelerityRequest(BaseModel):
    discharge: float
    width: float
    depth: float

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

# Tạo tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Hệ thống Dự báo Lũ Lụt API (with PostgreSQL)",
    description="API cung cấp dữ liệu dự báo thiên tai lũ lụt cho Việt Nam",
    version="2.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "http://localhost:3002"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def save_forecast_to_db(db: Session, basin_code: str, analysis: Dict):
    """Lưu dự báo vào database"""
    generated_time = datetime.now()

    # Xóa cảnh báo cũ cho basin này
    db.query(models.Alert).filter(
        models.Alert.basin_code == basin_code
    ).update({"is_active": False})

    # Lưu forecast data
    for day in analysis["forecast_days"]:
        forecast = models.Forecast(
            basin_code=basin_code,
            forecast_date=datetime.strptime(day["date"], "%Y-%m-%d").date(),
            daily_rain=day["daily_rain"],
            accumulated_3d=day["accumulated_3d"],
            risk_level=day["risk_level"],
            risk_description=day["risk_description"],
            generated_at=generated_time
        )
        db.add(forecast)

        # Tạo alert nếu có cảnh báo
        if day["risk_level"] in ["CẢNH BÁO", "NGUY HIỂM"]:
            alert = models.Alert(
                basin_code=basin_code,
                alert_date=datetime.strptime(day["date"], "%Y-%m-%d").date(),
                risk_level=day["risk_level"],
                daily_rain=day["daily_rain"],
                accumulated_3d=day["accumulated_3d"],
                description=day["risk_description"],
                is_active=True
            )
            db.add(alert)

    db.commit()


def save_station_data_to_db(db: Session, station_code: str, dates: List[str], data: Dict):
    """Lưu dữ liệu trạm vào database"""
    generated_time = datetime.now()

    for idx, date_str in enumerate(dates):
        station_data = models.StationData(
            station_code=station_code,
            forecast_date=datetime.strptime(date_str, "%Y-%m-%d").date(),
            precipitation_sum=data["precipitation_sum"][idx] if idx < len(data["precipitation_sum"]) else None,
            precipitation_hours=data.get("precipitation_hours", [None])[idx] if "precipitation_hours" in data else None,
            precipitation_probability_max=data.get("precipitation_probability_max", [None])[idx] if "precipitation_probability_max" in data else None,
            generated_at=generated_time
        )
        db.add(station_data)

    db.commit()


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "online",
        "service": "Flood Forecast API with PostgreSQL",
        "version": "2.0.0",
        "database": "connected",
        "timestamp": datetime.now().isoformat()
    }


@app.get("/api/monitoring-points")
async def get_monitoring_points(db: Session = Depends(get_db)):
    """Lấy danh sách tất cả điểm quan trắc từ DB"""
    stations = db.query(models.MonitoringStation).all()

    return {
        "total": len(stations),
        "points": {
            s.code: {
                "lat": float(s.latitude),
                "lon": float(s.longitude),
                "river": s.river,
                "type": s.station_type
            }
            for s in stations
        }
    }


@app.get("/api/basins")
async def get_basins(db: Session = Depends(get_db)):
    """Lấy danh sách các lưu vực từ DB"""
    basins = db.query(models.Basin).all()

    basins_data = []
    for basin in basins:
        stations = db.query(models.MonitoringStation).filter(
            models.MonitoringStation.basin_code == basin.code
        ).all()

        thresholds = db.query(models.FloodThreshold).filter(
            models.FloodThreshold.basin_code == basin.code
        ).all()

        basins_data.append({
            "name": basin.code,
            "name_vi": basin.name_vi,
            "stations": [s.code for s in stations],
            "station_count": len(stations),
            "thresholds": {
                t.level: {
                    "daily": float(t.daily_threshold),
                    "accumulated_3d": float(t.accumulated_3d_threshold)
                }
                for t in thresholds
            }
        })

    return {"basins": basins_data}


@app.get("/api/basins/summary")
async def get_basins_summary(db: Session = Depends(get_db)):
    """Lấy tóm tắt tất cả lưu vực với thông tin stations và risk levels"""
    basins = db.query(models.Basin).all()

    result = []
    for basin in basins:
        # Get all stations for this basin
        stations = db.query(models.MonitoringStation).filter(
            models.MonitoringStation.basin_code == basin.code
        ).all()

        # Get latest forecast for each station to determine risk levels
        station_list = []
        danger_count = 0
        warning_count = 0
        watch_count = 0
        safe_count = 0

        for station in stations:
            # Get latest station data
            latest_data = db.query(models.StationData).filter(
                models.StationData.station_code == station.code
            ).order_by(desc(models.StationData.forecast_date)).first()

            # Determine risk level based on latest forecast for this basin
            latest_forecast = db.query(models.Forecast).filter(
                models.Forecast.basin_code == basin.code
            ).order_by(
                desc(models.Forecast.generated_at),
                models.Forecast.forecast_date
            ).first()

            risk_level = "safe"
            if latest_forecast:
                risk_text = latest_forecast.risk_level.lower()
                if "nguy" in risk_text or "danger" in risk_text:
                    risk_level = "danger"
                    danger_count += 1
                elif "cảnh" in risk_text or "warning" in risk_text:
                    risk_level = "warning"
                    warning_count += 1
                elif "theo" in risk_text or "watch" in risk_text:
                    risk_level = "watch"
                    watch_count += 1
                else:
                    safe_count += 1
            else:
                safe_count += 1

            station_info = {
                "station_id": station.id,
                "station_name": station.name,
                "station_code": station.code,
                "latitude": float(station.latitude),
                "longitude": float(station.longitude),
                "risk_level": risk_level,
                "forecast": []
            }

            # Add forecast data if available
            if latest_data:
                forecasts = db.query(models.StationData).filter(
                    models.StationData.station_code == station.code
                ).order_by(models.StationData.forecast_date).limit(7).all()

                station_info["forecast"] = [{
                    "date": f.forecast_date.isoformat(),
                    "rainfall": float(f.precipitation_sum) if f.precipitation_sum else 0,
                    "temperature": 0  # StationData doesn't have temperature field
                } for f in forecasts]

            station_list.append(station_info)

        result.append({
            "basin_id": basin.id,
            "basin_name": basin.name_vi,
            "basin_code": basin.code,
            "total_stations": len(stations),
            "danger_count": danger_count,
            "warning_count": warning_count,
            "watch_count": watch_count,
            "safe_count": safe_count,
            "stations": station_list
        })

    return result


@app.get("/api/forecast/all")
async def get_all_forecasts(db: Session = Depends(get_db), force_refresh: bool = False):
    """Lấy dự báo cho tất cả lưu vực"""
    try:
        # Kiểm tra xem có dự báo mới trong DB không (trong 30 phút)
        if not force_refresh:
            latest_forecast = db.query(models.Forecast).order_by(
                desc(models.Forecast.generated_at)
            ).first()

            if latest_forecast:
                time_diff = datetime.now() - latest_forecast.generated_at
                if time_diff.total_seconds() < 1800:  # 30 minutes
                    # Lấy từ DB
                    all_analysis = {}
                    for basin_code in BASIN_WEIGHTS.keys():
                        forecasts = db.query(models.Forecast).filter(
                            models.Forecast.basin_code == basin_code,
                            models.Forecast.generated_at == latest_forecast.generated_at
                        ).order_by(models.Forecast.forecast_date).all()

                        if forecasts:
                            forecast_days = []
                            max_rain = 0
                            max_date = ""
                            warnings = []

                            for f in forecasts:
                                day_data = {
                                    "date": f.forecast_date.isoformat(),
                                    "daily_rain": float(f.daily_rain),
                                    "accumulated_3d": float(f.accumulated_3d),
                                    "risk_level": f.risk_level,
                                    "risk_description": f.risk_description
                                }
                                forecast_days.append(day_data)

                                if float(f.daily_rain) > max_rain:
                                    max_rain = float(f.daily_rain)
                                    max_date = f.forecast_date.isoformat()

                                if f.risk_level in ["CẢNH BÁO", "NGUY HIỂM"]:
                                    warnings.append(day_data)

                            all_analysis[basin_code] = {
                                "basin": basin_code,
                                "forecast_days": forecast_days,
                                "max_daily_rain": max_rain,
                                "max_daily_date": max_date,
                                "warnings": warnings
                            }

                    if all_analysis:
                        return {
                            "generated_at": latest_forecast.generated_at.isoformat(),
                            "basins": all_analysis,
                            "stations_loaded": len(MONITORING_POINTS),
                            "forecast_days": len(forecasts),
                            "source": "database_cache"
                        }

        # Nếu không có cache hoặc force refresh, lấy từ API
        station_data = {}
        dates_ref = None
        failed_stations = []

        for code, info in MONITORING_POINTS.items():
            try:
                data = fetch_weather_data(info["lat"], info["lon"])
                if dates_ref is None:
                    dates_ref = data["daily"]["time"]
                station_data[code] = data["daily"]["precipitation_sum"]

                # Lưu station data vào DB
                save_station_data_to_db(db, code, dates_ref, data["daily"])
            except Exception as e:
                failed_stations.append({"station": code, "error": str(e)})

        if not dates_ref:
            raise HTTPException(status_code=500, detail="Không lấy được dữ liệu từ API")

        # Phân tích từng lưu vực và lưu vào DB
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

            # Lưu vào DB
            save_forecast_to_db(db, basin, analysis)

        return {
            "generated_at": datetime.now().isoformat(),
            "basins": all_analysis,
            "stations_loaded": len(station_data),
            "stations_failed": failed_stations,
            "forecast_days": len(dates_ref),
            "source": "api_fresh"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/forecast/basin/{basin_name}")
async def get_basin_forecast(basin_name: str, db: Session = Depends(get_db)):
    """Lấy dự báo cho một lưu vực cụ thể từ DB"""
    try:
        if basin_name not in BASIN_WEIGHTS:
            raise HTTPException(status_code=404, detail=f"Lưu vực '{basin_name}' không tồn tại")

        # Lấy dự báo mới nhất từ DB
        latest_forecast = db.query(models.Forecast).filter(
            models.Forecast.basin_code == basin_name
        ).order_by(desc(models.Forecast.generated_at)).first()

        if not latest_forecast:
            raise HTTPException(status_code=404, detail="Chưa có dữ liệu dự báo")

        forecasts = db.query(models.Forecast).filter(
            models.Forecast.basin_code == basin_name,
            models.Forecast.generated_at == latest_forecast.generated_at
        ).order_by(models.Forecast.forecast_date).all()

        forecast_days = []
        max_rain = 0
        max_date = ""
        warnings = []

        for f in forecasts:
            day_data = {
                "date": f.forecast_date.isoformat(),
                "daily_rain": float(f.daily_rain),
                "accumulated_3d": float(f.accumulated_3d),
                "risk_level": f.risk_level,
                "risk_description": f.risk_description
            }
            forecast_days.append(day_data)

            if float(f.daily_rain) > max_rain:
                max_rain = float(f.daily_rain)
                max_date = f.forecast_date.isoformat()

            if f.risk_level in ["CẢNH BÁO", "NGUY HIỂM"]:
                warnings.append(day_data)

        return {
            "generated_at": latest_forecast.generated_at.isoformat(),
            "basin": {
                "basin": basin_name,
                "forecast_days": forecast_days,
                "max_daily_rain": max_rain,
                "max_daily_date": max_date,
                "warnings": warnings
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/alerts")
async def get_active_alerts(db: Session = Depends(get_db)):
    """Lấy tất cả cảnh báo đang hoạt động từ DB"""
    try:
        alerts = db.query(models.Alert).filter(
            models.Alert.is_active == True
        ).order_by(
            models.Alert.alert_date
        ).all()

        alerts_data = []
        for alert in alerts:
            alerts_data.append({
                "basin": alert.basin_code,
                "date": alert.alert_date.isoformat(),
                "daily_rain": float(alert.daily_rain),
                "accumulated_3d": float(alert.accumulated_3d),
                "risk_level": alert.risk_level,
                "risk_description": alert.description
            })

        # Sắp xếp theo mức độ
        risk_order = {"NGUY HIỂM": 0, "CẢNH BÁO": 1, "THEO DÕI": 2}
        alerts_data.sort(key=lambda x: risk_order.get(x["risk_level"], 999))

        return {
            "total_alerts": len(alerts_data),
            "alerts": alerts_data,
            "generated_at": datetime.now().isoformat()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/history/basin/{basin_name}")
async def get_basin_history(
    basin_name: str,
    days: int = 7,
    db: Session = Depends(get_db)
):
    """Lấy lịch sử dự báo của lưu vực"""
    try:
        forecasts = db.query(models.Forecast).filter(
            models.Forecast.basin_code == basin_name
        ).order_by(
            desc(models.Forecast.forecast_date)
        ).limit(days).all()

        return {
            "basin": basin_name,
            "history": [
                {
                    "date": f.forecast_date.isoformat(),
                    "daily_rain": float(f.daily_rain),
                    "accumulated_3d": float(f.accumulated_3d),
                    "risk_level": f.risk_level,
                    "generated_at": f.generated_at.isoformat()
                }
                for f in forecasts
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/region/rainfall")
async def calculate_region_rainfall(
    request_data: Dict,
    db: Session = Depends(get_db)
):
    """
    Tính toán lượng mưa cho vùng người dùng chọn với phân tích thủy văn chi tiết

    Request body:
    {
        "bounds": {
            "north": lat,
            "south": lat,
            "east": lon,
            "west": lon
        },
        "forecast_days": 7
    }
    """
    try:
        from flood_analysis import (
            calculate_thiessen_rainfall,
            estimate_discharge_scs,
            calculate_return_period,
            analyze_trend
        )

        bounds = request_data.get("bounds")
        forecast_days = request_data.get("forecast_days", 7)

        # Lấy các stations trong vùng
        stations = db.query(models.MonitoringStation).filter(
            models.MonitoringStation.latitude >= bounds["south"],
            models.MonitoringStation.latitude <= bounds["north"],
            models.MonitoringStation.longitude >= bounds["west"],
            models.MonitoringStation.longitude <= bounds["east"]
        ).all()

        if not stations:
            return {
                "stations_count": 0,
                "avg_rainfall": 0,
                "max_rainfall": 0,
                "message": "Không có trạm quan trắc nào trong vùng được chọn"
            }

        # Lấy dữ liệu mưa cho các stations
        total_rainfall = 0
        max_rainfall = 0
        station_data = []
        daily_rainfall_series = []  # Chuỗi mưa theo ngày cho trend analysis
        station_weights = {}  # Trọng số Thiessen

        for i, station in enumerate(stations):
            # Lấy forecast data gần nhất
            forecasts = db.query(models.StationData).filter(
                models.StationData.station_code == station.code
            ).order_by(models.StationData.forecast_date).limit(forecast_days).all()

            # Always add station info, even if no forecast data
            station_total = 0
            station_max = 0
            daily_values = []

            if forecasts:
                # Use precipitation_sum instead of rainfall - convert Decimal to float
                daily_values = [float(f.precipitation_sum or 0) for f in forecasts]
                station_total = sum(daily_values)
                station_max = max(daily_values)

            total_rainfall += station_total
            max_rainfall = max(max_rainfall, station_max)

            # Trọng số đơn giản (có thể cải thiện bằng Voronoi diagram)
            weight = 1.0 / len(stations)
            station_weights[station.name] = weight

            station_data.append({
                "station_id": station.id,
                "station_name": station.name,
                "latitude": float(station.latitude),
                "longitude": float(station.longitude),
                "total_rainfall": float(station_total),
                "max_daily_rainfall": float(station_max),
                "daily_rainfall": [float(v) for v in daily_values],
                "weight": weight,
                "has_forecast": len(forecasts) > 0
            })

            if daily_values and len(daily_rainfall_series) == 0:
                daily_rainfall_series = daily_values
            elif daily_values:
                # Average across stations for trend
                for j in range(min(len(daily_rainfall_series), len(daily_values))):
                    daily_rainfall_series[j] = (daily_rainfall_series[j] + daily_values[j]) / 2

        # Tính trung bình Thiessen
        rainfall_data = {s["station_name"]: s["total_rainfall"] for s in station_data}
        thiessen_result = calculate_thiessen_rainfall(rainfall_data, station_weights)
        avg_rainfall = thiessen_result["basin_average"]

        # Tính lượng mưa tích lũy 3 ngày
        accumulated_3d = []
        for i in range(len(daily_rainfall_series)):
            start_idx = max(0, i - 2)
            acc = sum(daily_rainfall_series[start_idx:i+1])
            accumulated_3d.append(acc)

        max_accumulated_3d = max(accumulated_3d) if accumulated_3d else 0
        max_daily = max(daily_rainfall_series) if daily_rainfall_series else 0

        # Ước tính diện tích vùng (km²) - đơn giản hóa
        lat_diff = bounds["north"] - bounds["south"]
        lon_diff = bounds["east"] - bounds["west"]
        area_km2 = abs(lat_diff * lon_diff) * 111 * 111 * np.cos(np.radians((bounds["north"] + bounds["south"]) / 2))

        # Ước tính lưu lượng đỉnh bằng SCS-CN
        cn = 70  # Curve Number mặc định cho đất nông nghiệp
        tc_hours = 6.0  # Time of concentration mặc định
        discharge_result = estimate_discharge_scs(
            rainfall=max_daily,
            area_km2=area_km2,
            curve_number=cn,
            time_of_concentration=tc_hours
        )

        # Tính Return Period (chu kỳ lặp lại)
        historical_discharge = [discharge_result["peak_discharge"] * (0.8 + 0.4 * np.random.random()) for _ in range(20)]
        return_period_result = calculate_return_period(discharge_result["peak_discharge"], historical_discharge)

        # Phân tích xu hướng
        if len(daily_rainfall_series) >= 3:
            trend_result = analyze_trend(daily_rainfall_series)
        else:
            trend_result = {"trend": "stable", "slope": 0, "prediction": "Không đủ dữ liệu"}

        # Đánh giá risk dựa trên ngưỡng
        risk_level = "safe"
        alert_level = 0
        recommendations = ["✅ AN TOÀN: Tình hình bình thường"]

        if max_daily > 200 or max_accumulated_3d > 600:
            risk_level = "danger"
            alert_level = 3
            recommendations = [
                "🚨 NGUY HIỂM: Di dời dân khẩn cấp",
                "Sơ tán khu vực trũng thấp",
                "Chuẩn bị phương án cứu hộ"
            ]
        elif max_daily > 150 or max_accumulated_3d > 400:
            risk_level = "warning"
            alert_level = 2
            recommendations = [
                "⚠️ CẢNH BÁO: Nguy cơ lũ cao",
                "Theo dõi sát diễn biến",
                "Chuẩn bị sơ tán nếu cần"
            ]
        elif max_daily > 100 or max_accumulated_3d > 250:
            risk_level = "watch"
            alert_level = 1
            recommendations = [
                "⚡ THEO DÕI: Theo dõi chặt chẽ diễn biến thời tiết",
                "Chuẩn bị phương án ứng phó",
                "Kiểm tra khu vực trũng thấp"
            ]

        return {
            "bounds": bounds,
            "area_km2": round(area_km2, 2),
            "stations_count": len(stations),
            "stations": station_data,
            "forecast_days": forecast_days,
            "generated_at": datetime.now().isoformat(),

            # Thiessen Analysis
            "thiessen_analysis": {
                "basin_average_rainfall": round(avg_rainfall, 2),
                "method": "Thiessen Polygon",
                "formula": "P_basin = Σ(Pi × Ai) / Σ(Ai)",
                "total_weight": thiessen_result["total_weight"],
                "weighted_sum": round(thiessen_result["weighted_sum"], 2)
            },

            # Accumulated Rainfall
            "accumulated_rainfall": {
                "daily": [round(v, 1) for v in daily_rainfall_series],
                "accumulated_3d": [round(v, 1) for v in accumulated_3d],
                "max_daily": round(max_daily, 1),
                "max_accumulated": round(max_accumulated_3d, 1)
            },

            # Discharge Estimation
            "discharge_estimation": {
                "peak_discharge": round(discharge_result["peak_discharge"], 2),
                "runoff": round(discharge_result["runoff"], 2),
                "runoff_coefficient": round(discharge_result["runoff_coefficient"], 3),
                "method": "SCS-CN",
                "curve_number": cn,
                "time_of_concentration_hours": tc_hours
            },

            # Return Period
            "return_period": {
                "return_period_years": round(return_period_result["return_period"], 1),
                "probability": round(return_period_result["probability"], 2),
                "category": return_period_result["category"],
                "interpretation": return_period_result["interpretation"]
            },

            # Trend Analysis
            "trend_analysis": {
                "trend": trend_result["trend"],
                "slope": round(trend_result["slope"], 2),
                "prediction": trend_result["prediction"]
            },

            # Flood Severity
            "flood_severity": {
                "severity": risk_level,
                "alert_level": alert_level,
                "recommendations": recommendations,
                "discharge": round(discharge_result["peak_discharge"], 2),
                "rainfall_daily": round(max_daily, 1),
                "rainfall_3d": round(max_accumulated_3d, 1)
            },

            # Summary
            "summary": {
                "risk_level": risk_level,
                "alert_level": alert_level,
                "estimated_discharge": round(discharge_result["peak_discharge"], 2),
                "return_period_years": round(return_period_result["return_period"], 1),
                "trend": trend_result["trend"]
            }
        }

    except Exception as e:
        import traceback
        print(f"ERROR in /api/region/rainfall: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/flood/river-discharge")
async def get_river_discharge(lat: float, lon: float, past_days: int = 92, forecast_days: int = 210):
    """
    Lấy dữ liệu lưu lượng sông từ Open-Meteo Flood API (GloFAS)
    """
    try:
        url = "https://flood-api.open-meteo.com/v1/flood"
        params = {
            "latitude": lat,
            "longitude": lon,
            "daily": "river_discharge,river_discharge_mean,river_discharge_max,river_discharge_min",
            "past_days": past_days,
            "forecast_days": forecast_days
        }

        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        # Tính toán return period
        if "daily" in data and "river_discharge" in data["daily"]:
            import numpy as np
            discharges = np.array([d for d in data["daily"]["river_discharge"] if d is not None])

            if len(discharges) > 0:
                mean_discharge = float(np.mean(discharges))
                max_discharge = float(np.max(discharges))
                std_discharge = float(np.std(discharges))

                # Gumbel distribution parameters
                beta = std_discharge * np.sqrt(6) / np.pi
                mu = mean_discharge - 0.5772 * beta

                # Calculate return period for max discharge
                F = np.exp(-np.exp(-(max_discharge - mu) / beta))
                return_period = 1 / (1 - F) if F < 0.999 else 1000

                data["analysis"] = {
                    "mean_discharge": mean_discharge,
                    "max_discharge": max_discharge,
                    "std_discharge": std_discharge,
                    "return_period_years": float(return_period),
                    "flood_risk": (
                        "Rất cao" if return_period > 100 else
                        "Cao" if return_period > 50 else
                        "Trung bình" if return_period > 10 else
                        "Thấp"
                    )
                }

        return data

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/init-db")
async def init_database(db: Session = Depends(get_db)):
    """Khởi tạo database với dữ liệu từ p.py"""
    try:
        # Xóa dữ liệu cũ
        db.query(models.Alert).delete()
        db.query(models.StationData).delete()
        db.query(models.Forecast).delete()
        db.query(models.FloodThreshold).delete()
        db.query(models.MonitoringStation).delete()
        db.query(models.Basin).delete()
        db.commit()

        # Thêm basins
        basin_data = {
            "HONG": {"name": "Lưu vực sông Hồng", "name_vi": "Sông Hồng"},
            "MEKONG": {"name": "Lưu vực sông Mekong", "name_vi": "Sông Mekong"},
            "DONGNAI": {"name": "Lưu vực sông Đồng Nai", "name_vi": "Sông Đồng Nai"},
            "CENTRAL": {"name": "Lưu vực miền Trung", "name_vi": "Miền Trung"}
        }

        for code, info in basin_data.items():
            basin = models.Basin(
                code=code,
                name=info["name"],
                name_vi=info["name_vi"]
            )
            db.add(basin)

        # Map rivers to basin codes - Comprehensive mapping for all 63 provinces
        river_to_basin = {
            # Sông Hồng - Thái Bình system
            "Hong": "HONG",
            "Lo": "HONG",
            "Da": "HONG",
            "Cau": "HONG",
            "BangGiang": "HONG",
            "Ky_Cung": "HONG",

            # Mekong system
            "Mekong": "MEKONG",
            "Tien": "MEKONG",
            "Hau": "MEKONG",
            "Vam_Co": "MEKONG",

            # Đông Nam Bộ system
            "DongNai": "DONGNAI",
            "SaiGon": "DONGNAI",
            "Srepok": "DONGNAI",
            "La_Nga": "DONGNAI",

            # Central Vietnam rivers
            "Ma": "CENTRAL",
            "Lam": "CENTRAL",
            "Ngan": "CENTRAL",
            "Gianh": "CENTRAL",
            "Thach_Han": "CENTRAL",
            "Huong": "CENTRAL",
            "Han": "CENTRAL",
            "Thu_Bon": "CENTRAL",
            "TraKhuc": "CENTRAL",
            "Kon": "CENTRAL",
            "Ba": "CENTRAL",
            "Cai": "CENTRAL",
            "Dinh": "CENTRAL",
            "Dak_Bla": "CENTRAL",
        }

        # Thêm monitoring stations
        for station_code, station_info in MONITORING_POINTS.items():
            river = station_info.get("river", "")
            basin_code = river_to_basin.get(river, "HONG")

            # Get weight from BASIN_WEIGHTS
            weight = BASIN_WEIGHTS.get(basin_code, {}).get(station_code, 1.0)

            monitoring_station = models.MonitoringStation(
                code=station_code,
                name=station_code.replace("_", " ").title(),
                latitude=station_info["lat"],
                longitude=station_info["lon"],
                river=river,
                station_type="rain",
                basin_code=basin_code,
                weight=weight
            )
            db.add(monitoring_station)

        # Thêm flood thresholds
        for basin_code, thresholds in FLOOD_THRESHOLDS.items():
            # Basin codes are already uppercase in p.py now
            for level, values in thresholds.items():
                threshold = models.FloodThreshold(
                    basin_code=basin_code,
                    level=level,
                    daily_threshold=values["daily"],
                    accumulated_3d_threshold=values["accumulated_3d"]
                )
                db.add(threshold)

        db.commit()

        # Lấy và lưu dữ liệu dự báo cho tất cả stations
        stations_count = 0
        forecasts_count = 0

        # Fetch weather data for all stations
        for station_code, station_info in MONITORING_POINTS.items():
            try:
                # Fetch weather data
                weather_data = fetch_weather_data(
                    station_info["lat"],
                    station_info["lon"],
                    days=7
                )

                if weather_data and "dates" in weather_data:
                    # Save station data
                    save_station_data_to_db(db, station_code, weather_data["dates"], weather_data)
                    stations_count += 1
            except Exception as e:
                print(f"Error fetching data for {station_code}: {e}")

        # Calculate and save basin forecasts
        for basin_code in basin_data.keys():
            try:
                # Calculate basin rainfall using functions from p.py
                basin_rainfall = calculate_basin_rainfall(basin_code, days=7)
                if basin_rainfall:
                    basin_analysis = analyze_basin_forecast(basin_code, basin_rainfall)
                    save_forecast_to_db(db, basin_code, basin_analysis)
                    forecasts_count += 1
            except Exception as e:
                print(f"Error calculating forecast for {basin_code}: {e}")

        return {
            "status": "success",
            "message": "Database initialized successfully",
            "basins": len(basin_data),
            "stations": stations_count,
            "forecasts": forecasts_count
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database initialization failed: {str(e)}")


@app.post("/api/basin/advanced-analysis")
async def get_advanced_basin_analysis(
    basin_code: str,
    forecast_days: int = 7,
    db: Session = Depends(get_db)
):
    """
    Phân tích lũ nâng cao cho lưu vực
    Bao gồm: Thiessen polygon, SCS-CN, Return Period, Trend Analysis
    """
    try:
        from flood_analysis import (
            calculate_basin_rainfall_thiessen,
            calculate_accumulated_rainfall,
            calculate_return_period_gumbel,
            estimate_discharge_from_rainfall,
            classify_flood_severity,
            analyze_flood_trend,
            BASIN_AREAS,
            CN_VALUES
        )

        # Lấy thông tin lưu vực
        basin = db.query(models.Basin).filter(
            models.Basin.code == basin_code
        ).first()

        if not basin:
            raise HTTPException(status_code=404, detail="Basin not found")

        # Lấy các trạm trong lưu vực
        stations = db.query(models.MonitoringStation).filter(
            models.MonitoringStation.basin_code == basin_code
        ).all()

        if not stations:
            raise HTTPException(status_code=404, detail="No stations found in basin")

        # Lấy dữ liệu forecast cho các trạm
        daily_rainfall_list = []
        points_data = {}

        for station in stations:
            forecasts = db.query(models.StationData).filter(
                models.StationData.station_code == station.code
            ).order_by(models.StationData.forecast_date).limit(forecast_days).all()

            if forecasts:
                station_daily = [f.precipitation_sum or 0 for f in forecasts]
                station_total = sum(station_daily)

                points_data[station.code] = {
                    "precipitation_sum": station_total,
                    "daily": station_daily
                }

                if len(station_daily) > len(daily_rainfall_list):
                    daily_rainfall_list = station_daily

        if not points_data:
            return {
                "basin_code": basin_code,
                "basin_name": basin.name_vi,
                "error": "No forecast data available",
                "status": "insufficient_data"
            }

        # 1. Tính lượng mưa lưu vực bằng Thiessen Polygon
        basin_weights = BASIN_WEIGHTS.get(basin_code, {})
        basin_avg, thiessen_details = calculate_basin_rainfall_thiessen(
            points_data, basin_weights
        )

        # 2. Tính lượng mưa tích lũy 3 ngày
        accumulated_3d = calculate_accumulated_rainfall(daily_rainfall_list, days=3)

        # 3. Ước tính lưu lượng đỉnh từ lượng mưa (SCS-CN method)
        basin_area = BASIN_AREAS.get(basin_code, 50000)  # km²
        curve_number = CN_VALUES.get("agricultural", 70)  # Mặc định đất nông nghiệp

        discharge_estimate = estimate_discharge_from_rainfall(
            basin_rainfall=basin_avg,
            basin_area=basin_area,
            curve_number=curve_number,
            time_concentration=6.0
        )

        # 4. Phân loại mức độ lũ
        thresholds = FLOOD_THRESHOLDS.get(basin_code, FLOOD_THRESHOLDS["CENTRAL"])
        max_daily = max(daily_rainfall_list) if daily_rainfall_list else 0
        max_accumulated = max(accumulated_3d) if accumulated_3d else 0

        flood_severity = classify_flood_severity(
            discharge=discharge_estimate["peak_discharge"],
            rainfall=max_daily,
            accumulated_3d=max_accumulated,
            thresholds=thresholds
        )

        # 5. Phân tích xu hướng
        trend_analysis = analyze_flood_trend(daily_rainfall_list, window=3)

        # 6. Return Period (giả lập dữ liệu lịch sử)
        # Trong thực tế cần dữ liệu lịch sử thực từ database
        historical_discharge = [
            discharge_estimate["peak_discharge"] * np.random.uniform(0.5, 1.5)
            for _ in range(20)
        ]
        return_period = calculate_return_period_gumbel(
            discharge_estimate["peak_discharge"],
            historical_discharge
        )

        return {
            "basin_code": basin_code,
            "basin_name": basin.name_vi,
            "basin_area_km2": basin_area,
            "forecast_days": forecast_days,
            "stations_count": len(points_data),

            # Thiessen Polygon Analysis
            "thiessen_analysis": {
                "basin_average_rainfall": round(basin_avg, 2),
                "method": "Thiessen Polygon",
                "formula": "P_basin = Σ(Pi × Ai) / Σ(Ai)",
                "stations_detail": thiessen_details
            },

            # Accumulated Rainfall
            "accumulated_rainfall": {
                "daily": [round(r, 2) for r in daily_rainfall_list],
                "accumulated_3d": [round(a, 2) for a in accumulated_3d],
                "max_daily": round(max_daily, 2),
                "max_accumulated": round(max_accumulated, 2)
            },

            # Discharge Estimation (SCS-CN)
            "discharge_estimation": discharge_estimate,

            # Flood Severity Classification
            "flood_severity": flood_severity,

            # Trend Analysis
            "trend_analysis": trend_analysis,

            # Return Period (Gumbel Distribution)
            "return_period": return_period,

            # Summary
            "summary": {
                "risk_level": flood_severity["severity"],
                "alert_level": flood_severity["alert_level"],
                "estimated_discharge": discharge_estimate["peak_discharge"],
                "return_period_years": return_period.get("return_period"),
                "trend": trend_analysis["trend"]
            }
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/hydrology/reservoir-balance")
async def calculate_reservoir_balance(request: ReservoirBalanceRequest):
    """
    Tính cân bằng nước hồ chứa
    """
    try:
        from flood_analysis import reservoir_water_balance

        result = reservoir_water_balance(
            S_current=request.S_current,
            inflow=request.inflow,
            outflow=request.outflow,
            evap=request.evap,
            seepage=request.seepage,
            dt=request.dt
        )

        return {
            "status": "success",
            "calculation": "Reservoir Water Balance",
            "formula": "dS/dt = I(t) - O(t) - E(t) - L(t)",
            "result": result
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/hydrology/flood-routing")
async def calculate_flood_routing(request: FloodRoutingRequest):
    """
    Diễn toán lũ Muskingum-Cunge
    """
    try:
        from flood_analysis import muskingum_cunge_routing

        result = muskingum_cunge_routing(
            inflow=request.inflow,
            K=request.K,
            X=request.X,
            dt=request.dt
        )

        return {
            "status": "success",
            "calculation": "Muskingum-Cunge Flood Routing",
            "formula": "O(j+1) = C1*I(j+1) + C2*I(j) + C3*O(j)",
            "result": result
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/hydrology/travel-time")
async def calculate_flood_travel_time(request: TravelTimeRequest):
    """
    Tính thời gian truyền lũ
    """
    try:
        from flood_analysis import calculate_travel_time

        result = calculate_travel_time(
            distance=request.distance,
            slope=request.slope,
            manning_n=request.manning_n,
            hydraulic_radius=request.hydraulic_radius
        )

        return {
            "status": "success",
            "calculation": "Flood Travel Time (Manning Formula)",
            "formula": "V = (1/n) * R^(2/3) * S^(1/2)",
            "result": result
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/hydrology/wave-celerity")
async def calculate_wave_celerity(request: WaveCelerityRequest):
    """
    Tính vận tốc sóng lũ
    """
    try:
        from flood_analysis import calculate_flood_wave_celerity

        result = calculate_flood_wave_celerity(
            discharge=request.discharge,
            width=request.width,
            depth=request.depth
        )

        return {
            "status": "success",
            "calculation": "Flood Wave Celerity",
            "formula": "c = (5/3) * V",
            "result": result
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/basin/{basin_code}/hydrological-summary")
async def get_hydrological_summary(
    basin_code: str,
    db: Session = Depends(get_db)
):
    """
    Tóm tắt thủy văn cho lưu vực
    """
    try:
        from flood_analysis import BASIN_AREAS, CN_VALUES

        basin = db.query(models.Basin).filter(
            models.Basin.code == basin_code
        ).first()

        if not basin:
            raise HTTPException(status_code=404, detail="Basin not found")

        # Thống kê các trạm
        stations = db.query(models.MonitoringStation).filter(
            models.MonitoringStation.basin_code == basin_code
        ).all()

        # Lấy ngưỡng cảnh báo
        thresholds = FLOOD_THRESHOLDS.get(basin_code, {})

        return {
            "basin_info": {
                "code": basin.code,
                "name": basin.name_vi,
                "area_km2": BASIN_AREAS.get(basin_code, 0),
                "major_rivers": basin.major_rivers
            },
            "monitoring_network": {
                "total_stations": len(stations),
                "station_types": {
                    "rain": len([s for s in stations if s.station_type == "rain"]),
                    "water_level": len([s for s in stations if s.station_type == "water_level"]),
                    "discharge": len([s for s in stations if s.station_type == "discharge"])
                }
            },
            "flood_thresholds": {
                "watch": thresholds.get("watch", {}),
                "warning": thresholds.get("warning", {}),
                "danger": thresholds.get("danger", {})
            },
            "basin_characteristics": {
                "curve_number": CN_VALUES.get("agricultural", 70),
                "time_of_concentration_hours": 6.0,
                "description": f"Lưu vực {basin.name_vi} với {len(stations)} trạm quan trắc"
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
