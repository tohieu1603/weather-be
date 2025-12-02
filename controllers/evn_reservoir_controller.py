#!/usr/bin/env python3
"""
EVN Reservoir Controller - API endpoints for hydropower reservoir data
"""
from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any

from services.evn_reservoir_service import EVNReservoirService
from services.ai_analysis_service import AIAnalysisService
from services.forecast_service import ForecastService

router = APIRouter(prefix="/api/evn-reservoirs", tags=["EVN Reservoirs"])
service = EVNReservoirService()
ai_service = AIAnalysisService()
forecast_service = ForecastService()


@router.get("/")
async def get_all_reservoirs() -> Dict[str, Any]:
    """Get all EVN hydropower reservoir data"""
    try:
        data = service.get_all_reservoirs()
        return {
            "total": len(data),
            "reservoirs": data,
            "source": "EVN Database Cache"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/today")
async def get_today_reservoirs() -> Dict[str, Any]:
    """
    Get EVN reservoir data for today from DB cache.
    Returns empty if no data for today (frontend should scrape).
    Cache duration: 1 day.
    """
    try:
        result = service.get_today_cached()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summary")
async def get_summary() -> Dict[str, Any]:
    """Get reservoir summary statistics"""
    try:
        return service.get_summary()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/basin/{basin_name}")
async def get_by_basin(basin_name: str) -> Dict[str, Any]:
    """Get reservoirs for a specific basin"""
    try:
        data = service.get_by_basin(basin_name)
        return {
            "basin": basin_name.upper(),
            "total": len(data),
            "reservoirs": data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/alerts")
async def get_discharge_alerts() -> Dict[str, Any]:
    """Get reservoirs with active discharge alerts"""
    try:
        alerts = service.get_discharge_alerts()
        return {
            "total": len(alerts),
            "alerts": alerts,
            "severity_counts": {
                "critical": len([a for a in alerts if a.get("severity") == "critical"]),
                "high": len([a for a in alerts if a.get("severity") == "high"]),
                "medium": len([a for a in alerts if a.get("severity") == "medium"]),
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sync")
async def sync_from_frontend(data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Receive and save reservoir data from frontend Puppeteer scraper

    Frontend calls this endpoint after scraping EVN website
    """
    try:
        if not data:
            raise HTTPException(status_code=400, detail="No data provided")

        count = service.save_from_frontend(data)
        return {
            "success": True,
            "saved_count": count,
            "total_received": len(data)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scrape")
async def scrape_evn_data() -> Dict[str, Any]:
    """
    Trigger backend to scrape EVN website directly using Selenium.
    Use this when frontend scraping is not available.

    Requires Chrome/Chromium installed on server.
    """
    try:
        result = service.scrape_and_save()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analysis/{basin_name}")
async def get_comprehensive_analysis(basin_name: str) -> Dict[str, Any]:
    """
    Get comprehensive AI analysis combining EVN reservoir data + weather forecast

    Uses DeepSeek AI to analyze:
    - Weather forecast data from Open-Meteo
    - Real-time reservoir data from EVN

    Returns combined risk assessment and recommendations
    """
    try:
        basin = basin_name.upper()
        if basin not in ["HONG", "CENTRAL", "MEKONG", "DONGNAI"]:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid basin. Use: HONG, CENTRAL, MEKONG, DONGNAI"
            )

        # Get forecast data
        forecast_data = forecast_service.get_basin_forecast(basin)

        # Get comprehensive analysis
        analysis = ai_service.analyze_reservoir_comprehensive(basin, forecast_data)

        # Get current reservoir status for this basin
        reservoirs = service.get_by_basin(basin)

        return {
            "basin": basin,
            "analysis": analysis,
            "reservoir_status": {
                "total": len(reservoirs),
                "reservoirs": reservoirs
            },
            "data_sources": {
                "weather": "Open-Meteo API",
                "reservoirs": "EVN Database (real-time)",
                "analysis": "DeepSeek AI"
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{name}")
async def get_reservoir_by_name(name: str) -> Dict[str, Any]:
    """Get specific reservoir by name"""
    try:
        data = service.get_all_reservoirs()
        reservoir = next((r for r in data if r.get("name") == name), None)

        if not reservoir:
            raise HTTPException(status_code=404, detail=f"Reservoir '{name}' not found")

        return reservoir
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
