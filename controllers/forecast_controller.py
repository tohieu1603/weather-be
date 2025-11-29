#!/usr/bin/env python3
"""
Forecast Controller - API routes for flood forecasts
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from services.forecast_service import ForecastService
from services.ai_analysis_service import AIAnalysisService

router = APIRouter(prefix="/api", tags=["Forecast"])

# Service instances
forecast_service = ForecastService()
ai_service = AIAnalysisService()


@router.get("/forecast/all")
async def get_all_forecasts():
    """
    Lấy dự báo lũ cho tất cả các lưu vực

    Returns:
        Dữ liệu dự báo cho các lưu vực HONG, CENTRAL, MEKONG, DONGNAI
    """
    try:
        return forecast_service.get_all_forecasts()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/forecast/basin/{basin_name}")
async def get_basin_forecast(
    basin_name: str,
    include_ai: bool = Query(False, description="Bao gồm phân tích AI")
):
    """
    Lấy dự báo cho một lưu vực cụ thể

    Args:
        basin_name: Mã lưu vực (HONG, CENTRAL, MEKONG, DONGNAI)
        include_ai: Bao gồm phân tích AI (mất thời gian hơn)

    Returns:
        Dữ liệu dự báo và phân tích (nếu có)
    """
    try:
        result = forecast_service.get_basin_forecast(basin_name)

        # Add AI analysis if requested
        if include_ai:
            ai_analysis = ai_service.analyze_forecast(
                basin_name.upper(),
                result["data"]
            )
            result["ai_analysis"] = ai_analysis

        return result

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/basins/summary")
async def get_basins_summary():
    """
    Lấy tóm tắt tình trạng các lưu vực

    Returns:
        Danh sách các lưu vực với số lượng cảnh báo theo mức độ
    """
    try:
        return forecast_service.get_basins_summary()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/forecast/refresh")
async def refresh_forecasts():
    """
    Làm mới dữ liệu dự báo (xóa cache)

    Returns:
        Thông báo thành công
    """
    try:
        forecast_service.invalidate_cache()
        return {"message": "Cache cleared, next request will fetch fresh data"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
