#!/usr/bin/env python3
"""
Station Controller - API routes for monitoring stations
"""
from fastapi import APIRouter, HTTPException

from services.station_service import StationService

router = APIRouter(prefix="/api", tags=["Stations"])

# Service instance
station_service = StationService()


@router.get("/stations")
async def get_all_stations():
    """
    Lấy danh sách tất cả trạm quan trắc với mức độ rủi ro

    Returns:
        Danh sách trạm quan trắc
    """
    try:
        return station_service.get_all_stations()
    except Exception as e:
        print(f"Error in /api/stations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stations/{basin}")
async def get_stations_by_basin(basin: str):
    """
    Lấy danh sách trạm quan trắc theo lưu vực

    Args:
        basin: Mã lưu vực (HONG, CENTRAL, MEKONG, DONGNAI)

    Returns:
        Danh sách trạm trong lưu vực
    """
    try:
        result = station_service.get_stations_by_basin(basin)
        if result is None:
            raise HTTPException(status_code=404, detail=f"Không tìm thấy lưu vực: {basin}")
        return result
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in /api/stations/{basin}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
