#!/usr/bin/env python3
"""
Dam Controller - API routes for dam and dam alerts
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from services.dam_service import DamService

router = APIRouter(prefix="/api", tags=["Dams"])

# Service instance
dam_service = DamService()


@router.get("/dams")
async def get_all_dams():
    """
    Lấy danh sách tất cả các đập thủy điện

    Returns:
        Danh sách đập với thông tin chi tiết
    """
    try:
        return dam_service.get_all_dams()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dams/{basin}")
async def get_dams_by_basin(basin: str):
    """
    Lấy danh sách đập theo lưu vực

    Args:
        basin: Mã lưu vực (HONG, CENTRAL, MEKONG, DONGNAI)

    Returns:
        Danh sách đập trong lưu vực
    """
    try:
        dams = dam_service.get_dams_by_basin(basin)
        if not dams:
            raise HTTPException(status_code=404, detail=f"No dams found for basin: {basin}")
        return dams
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dam-alerts")
async def get_dam_alerts(
    basin: Optional[str] = Query(None, description="Lọc theo lưu vực")
):
    """
    Lấy cảnh báo xả lũ từ các đập

    Args:
        basin: Lưu vực (tùy chọn)

    Returns:
        Danh sách cảnh báo xả lũ
    """
    try:
        return dam_service.get_dam_alerts(basin)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dam-alerts/realtime")
async def get_realtime_dam_alerts():
    """
    Lấy cảnh báo xả lũ realtime (trong ngày)

    Returns:
        Danh sách cảnh báo xả lũ hiện tại
    """
    try:
        return dam_service.get_realtime_dam_alerts()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dam-alerts/{basin}")
async def get_dam_alerts_by_basin(basin: str):
    """
    Lấy cảnh báo xả lũ theo lưu vực

    Args:
        basin: Mã lưu vực

    Returns:
        Danh sách cảnh báo trong lưu vực
    """
    try:
        alerts = dam_service.get_dam_alerts(basin)
        return alerts
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
