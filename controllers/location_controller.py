#!/usr/bin/env python3
"""
Location Controller - API routes for rivers, flood zones, and locations
"""
from fastapi import APIRouter, HTTPException

from services.location_service import LocationService

router = APIRouter(prefix="/api", tags=["Locations"])

# Service instance
location_service = LocationService()


# ============ Rivers Endpoints ============

@router.get("/rivers")
async def get_all_rivers():
    """
    Lấy danh sách tất cả sông chính

    Returns:
        Danh sách sông theo lưu vực
    """
    try:
        return location_service.get_all_rivers()
    except Exception as e:
        print(f"Error in /api/rivers: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rivers/{basin}")
async def get_rivers_by_basin(basin: str):
    """
    Lấy danh sách sông theo lưu vực

    Args:
        basin: Mã lưu vực (HONG, CENTRAL, MEKONG, DONGNAI)

    Returns:
        Danh sách sông trong lưu vực
    """
    try:
        result = location_service.get_rivers_by_basin(basin)
        if result is None:
            raise HTTPException(status_code=404, detail=f"Không tìm thấy lưu vực: {basin}")
        return result
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in /api/rivers/{basin}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ Flood Zones Endpoints ============

@router.get("/flood-zones")
async def get_all_flood_zones():
    """
    Lấy danh sách tất cả vùng ngập lụt tiềm năng

    Returns:
        Danh sách vùng ngập lụt với mức độ rủi ro
    """
    try:
        return location_service.get_all_flood_zones()
    except Exception as e:
        print(f"Error in /api/flood-zones: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/flood-zones/{basin}")
async def get_flood_zones_by_basin(basin: str):
    """
    Lấy vùng ngập lụt theo lưu vực

    Args:
        basin: Mã lưu vực

    Returns:
        Danh sách vùng ngập lụt trong lưu vực
    """
    try:
        result = location_service.get_flood_zones_by_basin(basin)
        if result is None:
            raise HTTPException(status_code=404, detail=f"Không tìm thấy lưu vực: {basin}")
        return result
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in /api/flood-zones/{basin}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# NOTE: /api/locations endpoints are in weather_controller.py
