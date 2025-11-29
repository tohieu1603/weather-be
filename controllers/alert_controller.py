#!/usr/bin/env python3
"""
Alert Controller - API routes for weather and flood alerts
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from services.alert_service import AlertService

router = APIRouter(prefix="/api", tags=["Alerts"])

# Service instance
alert_service = AlertService()


@router.get("/alerts")
async def get_alerts(
    severity: Optional[str] = Query(None, description="Lọc theo mức độ: critical, high, medium, low")
):
    """
    Lấy tất cả cảnh báo thời tiết

    Args:
        severity: Mức độ nghiêm trọng (tùy chọn)

    Returns:
        Danh sách cảnh báo
    """
    try:
        return alert_service.get_all_alerts(severity=severity)
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
        return alert_service.get_realtime_alerts()
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
        return alert_service.get_alerts_by_region(region)
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
        return alert_service.get_combined_alerts()
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
