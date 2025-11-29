#!/usr/bin/env python3
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, List
import requests
from datetime import datetime
import sys
import os

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

app = FastAPI(
    title="Hệ thống Dự báo Lũ Lụt API",
    description="API cung cấp dữ liệu dự báo thiên tai lũ lụt cho Việt Nam",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "online",
        "service": "Flood Forecast API",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat()
    }


@app.get("/api/monitoring-points")
async def get_monitoring_points():
    """Lấy danh sách tất cả điểm quan trắc"""
    return {
        "total": len(MONITORING_POINTS),
        "points": MONITORING_POINTS
    }


@app.get("/api/basins")
async def get_basins():
    """Lấy danh sách các lưu vực"""
    basins = []
    for basin_name, weights in BASIN_WEIGHTS.items():
        basins.append({
            "name": basin_name,
            "stations": list(weights.keys()),
            "station_count": len(weights),
            "thresholds": FLOOD_THRESHOLDS.get(basin_name, FLOOD_THRESHOLDS["Central"])
        })
    return {"basins": basins}


@app.get("/api/forecast/all")
async def get_all_forecasts():
    """Lấy dự báo cho tất cả lưu vực"""
    try:
        # Bước 1: Lấy dữ liệu từ API
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

        if not dates_ref:
            raise HTTPException(status_code=500, detail="Không lấy được dữ liệu từ API")

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

        return {
            "generated_at": datetime.now().isoformat(),
            "basins": all_analysis,
            "stations_loaded": len(station_data),
            "stations_failed": failed_stations,
            "forecast_days": len(dates_ref)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/forecast/basin/{basin_name}")
async def get_basin_forecast(basin_name: str):
    """Lấy dự báo cho một lưu vực cụ thể"""
    try:
        if basin_name not in BASIN_WEIGHTS:
            raise HTTPException(status_code=404, detail=f"Lưu vực '{basin_name}' không tồn tại")

        # Lấy dữ liệu
        station_data = {}
        dates_ref = None
        weights = BASIN_WEIGHTS[basin_name]

        for code in weights.keys():
            if code not in MONITORING_POINTS:
                continue
            info = MONITORING_POINTS[code]
            try:
                data = fetch_weather_data(info["lat"], info["lon"])
                if dates_ref is None:
                    dates_ref = data["daily"]["time"]
                station_data[code] = data["daily"]["precipitation_sum"]
            except Exception as e:
                print(f"Error fetching {code}: {e}")

        if not dates_ref:
            raise HTTPException(status_code=500, detail="Không lấy được dữ liệu")

        # Tính lượng mưa lưu vực
        basin_rainfall = []
        for idx in range(len(dates_ref)):
            day_points = {
                st: {"precipitation_sum": station_data.get(st, [0] * len(dates_ref))[idx]}
                for st in weights.keys()
            }
            basin_rain = calculate_basin_rainfall(day_points, weights)
            basin_rainfall.append(basin_rain)

        # Phân tích
        thresholds = FLOOD_THRESHOLDS.get(basin_name, FLOOD_THRESHOLDS["Central"])
        analysis = analyze_basin_forecast(basin_name, basin_rainfall, dates_ref, thresholds)

        return {
            "generated_at": datetime.now().isoformat(),
            "basin": analysis,
            "stations_count": len(station_data)
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/station/{station_code}")
async def get_station_forecast(station_code: str):
    """Lấy dự báo cho một trạm cụ thể"""
    try:
        if station_code not in MONITORING_POINTS:
            raise HTTPException(status_code=404, detail=f"Trạm '{station_code}' không tồn tại")

        info = MONITORING_POINTS[station_code]
        data = fetch_weather_data(info["lat"], info["lon"])

        return {
            "station": station_code,
            "info": info,
            "forecast": {
                "dates": data["daily"]["time"],
                "precipitation_sum": data["daily"]["precipitation_sum"],
                "precipitation_hours": data["daily"]["precipitation_hours"],
                "precipitation_probability_max": data["daily"]["precipitation_probability_max"]
            },
            "generated_at": datetime.now().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/alerts")
async def get_active_alerts():
    """Lấy tất cả cảnh báo đang hoạt động"""
    try:
        # Lấy dữ liệu tất cả lưu vực
        forecast_data = await get_all_forecasts()

        all_alerts = []
        for basin_name, analysis in forecast_data["basins"].items():
            for warning in analysis["warnings"]:
                all_alerts.append({
                    "basin": basin_name,
                    **warning
                })

        # Sắp xếp theo mức độ nguy hiểm
        risk_order = {"NGUY HIỂM": 0, "CẢNH BÁO": 1, "THEO DÕI": 2}
        all_alerts.sort(key=lambda x: risk_order.get(x["risk_level"], 999))

        return {
            "total_alerts": len(all_alerts),
            "alerts": all_alerts,
            "generated_at": datetime.now().isoformat()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
