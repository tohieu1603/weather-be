#!/usr/bin/env python3
"""
Weather Controller - API routes for weather data
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from services.weather_service import WeatherService

router = APIRouter(prefix="/api", tags=["Weather"])

# Service instance
weather_service = WeatherService()


@router.get("/weather/realtime")
async def get_realtime_weather():
    """
    Lấy thời tiết realtime cho toàn Việt Nam

    Returns:
        Dữ liệu thời tiết theo vùng miền
    """
    try:
        return weather_service.get_realtime_weather()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/weather/forecast/{location}")
async def get_weather_forecast(
    location: str,
    days: int = Query(7, ge=1, le=16, description="Số ngày dự báo (1-16)")
):
    """
    Lấy dự báo thời tiết cho một địa điểm

    Args:
        location: Mã địa điểm (vd: hanoi, ho_chi_minh, da_nang)
        days: Số ngày dự báo

    Returns:
        Dữ liệu dự báo thời tiết
    """
    try:
        return weather_service.get_forecast_by_location(location, days)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/weather/flood/{location}")
async def get_flood_forecast(location: str):
    """
    Lấy dự báo lũ (GloFAS) cho một địa điểm

    Args:
        location: Mã địa điểm

    Returns:
        Dữ liệu dự báo lưu lượng sông
    """
    try:
        return weather_service.get_flood_forecast(location)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/locations")
async def get_locations(
    region: Optional[str] = Query(None, description="Lọc theo vùng: north, central, highland, south")
):
    """
    Lấy danh sách các địa điểm

    Args:
        region: Vùng miền (tùy chọn)

    Returns:
        Danh sách địa điểm với tọa độ
    """
    try:
        return weather_service.get_locations(region)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
