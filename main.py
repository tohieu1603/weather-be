#!/usr/bin/env python3
"""
Main FastAPI application - Flood Forecast System
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime

from config import CORS_ORIGINS
from controllers import (
    forecast_router,
    weather_router,
    dam_router,
    alert_router,
    station_router,
    location_router,
    evn_reservoir_router,
)

app = FastAPI(
    title="Hệ thống Dự báo Lũ Lụt API",
    description="API cung cấp dữ liệu dự báo thiên tai lũ lụt cho Việt Nam",
    version="2.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS + ["http://localhost:3000", "http://localhost:3001", "http://localhost:3002"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(forecast_router)
app.include_router(weather_router)
app.include_router(dam_router)
app.include_router(alert_router)
app.include_router(station_router)
app.include_router(location_router)
app.include_router(evn_reservoir_router)


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "online",
        "service": "Flood Forecast API",
        "version": "2.0.0",
        "timestamp": datetime.now().isoformat()
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
