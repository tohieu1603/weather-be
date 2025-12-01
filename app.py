#!/usr/bin/env python3
"""
Vietnam Flood Forecast API - Main Application

Cấu trúc:
- controllers/  : API route handlers
- services/     : Business logic layer
- repositories/ : Database access layer
- models/       : Data models/schemas
- config/       : Configuration
"""
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from config import CORS_ORIGINS
from controllers import (
    forecast_router,
    weather_router,
    dam_router,
    alert_router,
    station_router,
    location_router,
    evn_reservoir_router,
    rainfall_router,
)
from repositories.base import BaseRepository
from repositories.ai_cache_repository import AICacheRepository
from repositories.evn_analysis_cache_repository import EVNAnalysisCacheRepository


# Check database availability
DB_AVAILABLE = BaseRepository.check_db_available()
print(f"Database cache: {'enabled' if DB_AVAILABLE else 'disabled'}")


async def cleanup_expired_caches():
    """
    Background task để tự động xóa cache AI hết hạn.
    Chạy mỗi 24 giờ.
    """
    ai_cache_repo = AICacheRepository()
    evn_cache_repo = EVNAnalysisCacheRepository()

    while True:
        try:
            # Cleanup AI analysis cache (hết hạn sau 1 ngày)
            ai_deleted = ai_cache_repo.cleanup_expired()
            if ai_deleted > 0:
                print(f"✓ Đã xóa {ai_deleted} AI analysis cache hết hạn")

            # Cleanup EVN analysis cache (hết hạn sau 1 ngày)
            evn_deleted = evn_cache_repo.cleanup_expired()
            if evn_deleted > 0:
                print(f"✓ Đã xóa {evn_deleted} EVN analysis cache hết hạn")

        except Exception as e:
            print(f"✗ Lỗi cleanup cache: {e}")

        # Chờ 24 giờ trước khi cleanup tiếp
        await asyncio.sleep(24 * 60 * 60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager để quản lý startup/shutdown tasks.
    - Startup: Chạy cleanup cache ngay và khởi động background task
    - Shutdown: Dọn dẹp resources
    """
    # Startup
    print("🚀 Starting background tasks...")

    if DB_AVAILABLE:
        # Cleanup ngay khi khởi động
        try:
            ai_cache_repo = AICacheRepository()
            evn_cache_repo = EVNAnalysisCacheRepository()

            ai_deleted = ai_cache_repo.cleanup_expired()
            evn_deleted = evn_cache_repo.cleanup_expired()

            print(f"✓ Startup cleanup: {ai_deleted} AI + {evn_deleted} EVN cache entries đã xóa")
        except Exception as e:
            print(f"✗ Startup cleanup error: {e}")

        # Khởi động background cleanup task
        cleanup_task = asyncio.create_task(cleanup_expired_caches())
    else:
        cleanup_task = None

    yield

    # Shutdown
    print("🛑 Shutting down...")
    if cleanup_task:
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass


# Create FastAPI app
app = FastAPI(
    title="Hệ thống Dự báo Lũ Lụt Việt Nam",
    description="""
    API cung cấp dữ liệu dự báo thiên tai lũ lụt cho Việt Nam.

    ## Tính năng chính:
    - **Dự báo lũ**: Dự báo 14 ngày cho 4 lưu vực chính
    - **Phân tích AI**: Phân tích chi tiết bằng DeepSeek AI
    - **Cảnh báo thời tiết**: Cảnh báo mưa lớn, gió mạnh, UV cao
    - **Cảnh báo đập**: Thông tin xả lũ từ các đập thủy điện

    ## Lưu vực:
    - HONG: Sông Hồng (Miền Bắc)
    - CENTRAL: Miền Trung
    - MEKONG: Sông Mekong (Miền Nam)
    - DONGNAI: Sông Đồng Nai (Đông Nam Bộ)

    ## Cache AI Analysis:
    - Kết quả phân tích AI được lưu DB và cache 1 ngày
    - Lần request tiếp theo trong ngày sẽ lấy từ DB (không gọi AI)
    - Cache tự động xóa sau 1 ngày
    """,
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(forecast_router)
app.include_router(weather_router)
app.include_router(dam_router)
app.include_router(alert_router)
app.include_router(station_router)
app.include_router(location_router)
app.include_router(evn_reservoir_router)
app.include_router(rainfall_router)


@app.get("/", tags=["Root"])
async def root():
    """Root endpoint - API information"""
    return {
        "name": "Vietnam Flood Forecast API",
        "version": "2.0.0",
        "description": "API dự báo lũ lụt Việt Nam",
        "database": "connected" if DB_AVAILABLE else "disconnected",
        "endpoints": {
            "docs": "/docs",
            "forecast": "/api/forecast/all",
            "basins": "/api/basins/summary",
            "stations": "/api/stations",
            "weather": "/api/weather/realtime",
            "alerts": "/api/alerts/realtime",
            "dam_alerts": "/api/dam-alerts/realtime",
            "rivers": "/api/rivers",
            "flood_zones": "/api/flood-zones",
            "locations": "/api/locations",
            "evn_reservoirs": "/api/evn-reservoirs"
        }
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "database": "connected" if DB_AVAILABLE else "disconnected"
    }


# Entry point
if __name__ == "__main__":
    print("=" * 50)
    print("  HỆ THỐNG DỰ BÁO LŨ LỤT VIỆT NAM - API v2.0")
    print("=" * 50)
    print(f"Database: {'✓ Connected' if DB_AVAILABLE else '✗ Disconnected'}")
    print("API: http://localhost:8000")
    print("Docs: http://localhost:8000/docs")
    print("=" * 50)

    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
