#!/usr/bin/env python3
"""
Alert Controller - API routes for weather and flood alerts

IMPORTANT: All heavy synchronous operations are wrapped with run_in_executor()
to prevent blocking the FastAPI event loop.
"""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from services.alert_service import AlertService

router = APIRouter(prefix="/api", tags=["Alerts"])

# Thread pool for running sync operations without blocking event loop
_executor = ThreadPoolExecutor(max_workers=4)

# Service instance
alert_service = AlertService()


@router.get("/alerts")
async def get_alerts(
    severity: Optional[str] = Query(None, description="Lọc theo mức độ: critical, high, medium, low"),
    async_mode: bool = Query(False, description="Non-blocking mode - trả về job_id thay vì chờ kết quả")
):
    """
    Lấy tất cả cảnh báo thời tiết

    Args:
        severity: Mức độ nghiêm trọng (tùy chọn)
        async_mode: True = non-blocking (trả về job_id), False = blocking (chờ kết quả)

    Returns:
        - Nếu async_mode=True và đang processing: {"status": "processing", "job_id": "xxx"}
        - Nếu async_mode=True và có cache: {"alerts": [...], ...}
        - Nếu async_mode=False: {"alerts": [...], ...} (chờ đến khi xong)
    """
    try:
        loop = asyncio.get_event_loop()

        if async_mode:
            # This is already designed to be non-blocking (checks cache first)
            job_id, cached_result = alert_service.get_realtime_alerts_async()
            if cached_result:
                # Apply severity filter if specified
                if severity:
                    cached_result["alerts"] = [a for a in cached_result["alerts"] if a.get("severity") == severity]
                    cached_result["total"] = len(cached_result["alerts"])
                return cached_result
            else:
                return {"status": "processing", "job_id": job_id}
        else:
            # Run in thread pool to avoid blocking event loop
            result = await loop.run_in_executor(
                _executor,
                alert_service.get_all_alerts,
                None,  # alert_date
                severity
            )
            return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/alerts/realtime")
async def get_realtime_alerts():
    """
    Lấy cảnh báo thời tiết realtime (trong ngày)

    Returns:
        Danh sách cảnh báo hiện tại
    """
    try:
        # Run in thread pool to avoid blocking event loop
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(_executor, alert_service.get_realtime_alerts)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/alerts/region/{region}")
async def get_alerts_by_region(region: str):
    """
    Lấy cảnh báo theo vùng miền

    Args:
        region: Vùng miền (north, central, highland, south)

    Returns:
        Danh sách cảnh báo trong vùng
    """
    try:
        # Run in thread pool to avoid blocking event loop
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(_executor, alert_service.get_alerts_by_region, region)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/alerts/combined")
async def get_combined_alerts():
    """
    Lấy tất cả loại cảnh báo (thời tiết + đập thủy điện)

    Returns:
        Object chứa weather_alerts và dam_alerts
    """
    try:
        # Run in thread pool to avoid blocking event loop
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(_executor, alert_service.get_combined_alerts)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/alerts/cleanup")
async def cleanup_old_alerts(
    days: int = Query(7, ge=1, le=30, description="Xóa cảnh báo cũ hơn N ngày")
):
    """
    Dọn dẹp cảnh báo cũ

    Args:
        days: Số ngày (mặc định 7)

    Returns:
        Số lượng cảnh báo đã xóa
    """
    try:
        deleted = alert_service.cleanup_old_alerts(days)
        return {"deleted_count": deleted, "message": f"Deleted alerts older than {days} days"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/alerts/job/{job_id}")
async def get_alert_job_status(job_id: str):
    """
    Kiểm tra trạng thái job alerts

    Args:
        job_id: ID của job từ /alerts response

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
        status = alert_service.get_alert_job_status(job_id)

        if status is None:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found or expired")

        return status

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
