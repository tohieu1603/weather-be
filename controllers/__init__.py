#!/usr/bin/env python3
"""
Controller layer - API route handlers
"""
from .forecast_controller import router as forecast_router
from .weather_controller import router as weather_router
from .dam_controller import router as dam_router
from .alert_controller import router as alert_router
from .station_controller import router as station_router
from .location_controller import router as location_router
from .evn_reservoir_controller import router as evn_reservoir_router

__all__ = [
    "forecast_router",
    "weather_router",
    "dam_router",
    "alert_router",
    "station_router",
    "location_router",
    "evn_reservoir_router",
]
