#!/usr/bin/env python3
"""
Forecast Controller - API routes for flood forecasts

Supports both sync and async AI analysis modes:
- Sync (blocking): include_ai=true, async_mode=false
- Async (non-blocking): include_ai=true, async_mode=true -> returns job_id

IMPORTANT: All heavy synchronous operations are wrapped with run_in_executor()
to prevent blocking the FastAPI event loop.
"""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from services.forecast_service import ForecastService
from services.ai_analysis_service import AIAnalysisService

router = APIRouter(prefix="/api", tags=["Forecast"])

# Thread pool for running sync operations without blocking event loop
_executor = ThreadPoolExecutor(max_workers=4)

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
        # Run in thread pool to avoid blocking event loop
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(_executor, forecast_service.get_all_forecasts)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/forecast/basin/{basin_name}")
async def get_basin_forecast(
    basin_name: str,
    include_ai: bool = Query(False, description="Bao gồm phân tích AI"),
    async_mode: bool = Query(True, description="Chạy AI phân tích ở background (không block)")
):
    """
    Lấy dự báo cho một lưu vực cụ thể

    Args:
        basin_name: Mã lưu vực (HONG, CENTRAL, MEKONG, DONGNAI)
        include_ai: Bao gồm phân tích AI
        async_mode: True = non-blocking (trả về job_id), False = blocking (chờ kết quả)

    Returns:
        - Nếu async_mode=True và đang processing:
          {"data": {...}, "ai_status": "processing", "job_id": "xxx"}
        - Nếu async_mode=True và có cache:
          {"data": {...}, "ai_analysis": {...}}
        - Nếu async_mode=False:
          {"data": {...}, "ai_analysis": {...}} (chờ đến khi xong)
    """
    try:
        # Run forecast fetch in thread pool to avoid blocking event loop
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            _executor,
            forecast_service.get_basin_forecast,
            basin_name
        )

        # Add AI analysis if requested
        if include_ai:
            if async_mode:
                # Non-blocking mode - return immediately
                # This is already non-blocking (checks cache first, spawns thread if needed)
                job_id, cached_result = ai_service.analyze_forecast_async(
                    basin_name.upper(),
                    result["data"]
                )

                if cached_result:
                    # Have cached data - return immediately
                    result["ai_analysis"] = cached_result
                    result["ai_status"] = "completed"
                else:
                    # Processing in background
                    result["ai_status"] = "processing"
                    result["job_id"] = job_id
            else:
                # Blocking mode - run in thread pool to avoid blocking event loop
                ai_analysis = await loop.run_in_executor(
                    _executor,
                    ai_service.analyze_forecast,
                    basin_name.upper(),
                    result["data"]
                )
                result["ai_analysis"] = ai_analysis
                result["ai_status"] = "completed"

        return result

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/forecast/job/{job_id}")
async def get_job_status(job_id: str):
    """
    Kiểm tra trạng thái job AI analysis

    Args:
        job_id: ID của job từ /forecast/basin response

    Returns:
        {
            "job_id": "xxx",
            "status": "pending" | "processing" | "completed" | "failed",
            "progress": 0-100,
            "result": {...} // chỉ có khi completed
            "error": "..." // chỉ có khi failed
        }
    """
    try:
        status = ai_service.get_job_status(job_id)

        if status is None:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found or expired")

        return status

    except HTTPException:
        raise
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
        # Run in thread pool to avoid blocking event loop
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(_executor, forecast_service.get_basins_summary)
        return result
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
