"""initial_schema

Revision ID: e2eac27365a9
Revises:
Create Date: 2025-12-01 10:46:48.506427

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'e2eac27365a9'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - Create all tables."""

    # === Core Tables ===

    # Basins - Lưu vực sông
    op.execute("""
        CREATE TABLE IF NOT EXISTS basins (
            id SERIAL PRIMARY KEY,
            code VARCHAR(50) UNIQUE NOT NULL,
            name VARCHAR(255) NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Monitoring Stations - Trạm quan trắc
    op.execute("""
        CREATE TABLE IF NOT EXISTS monitoring_stations (
            id SERIAL PRIMARY KEY,
            code VARCHAR(50) UNIQUE NOT NULL,
            name VARCHAR(255) NOT NULL,
            latitude DECIMAL(10, 6) NOT NULL,
            longitude DECIMAL(10, 6) NOT NULL,
            basin_id INTEGER REFERENCES basins(id),
            station_type VARCHAR(50),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Dams - Đập/Hồ chứa
    op.execute("""
        CREATE TABLE IF NOT EXISTS dams (
            id SERIAL PRIMARY KEY,
            code VARCHAR(50) UNIQUE NOT NULL,
            name VARCHAR(255) NOT NULL,
            latitude DECIMAL(10, 6),
            longitude DECIMAL(10, 6),
            basin_id INTEGER REFERENCES basins(id),
            capacity DECIMAL(15, 2),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Locations - Địa điểm
    op.execute("""
        CREATE TABLE IF NOT EXISTS locations (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            latitude DECIMAL(10, 6) NOT NULL,
            longitude DECIMAL(10, 6) NOT NULL,
            location_type VARCHAR(50),
            province VARCHAR(100),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Flood Thresholds - Ngưỡng cảnh báo lũ
    op.execute("""
        CREATE TABLE IF NOT EXISTS flood_thresholds (
            id SERIAL PRIMARY KEY,
            basin_id INTEGER REFERENCES basins(id),
            station_id INTEGER REFERENCES monitoring_stations(id),
            warning_level DECIMAL(10, 2),
            danger_level DECIMAL(10, 2),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # === Forecast & Data Tables ===

    # Forecasts - Dự báo
    op.execute("""
        CREATE TABLE IF NOT EXISTS forecasts (
            id SERIAL PRIMARY KEY,
            basin_id INTEGER REFERENCES basins(id),
            forecast_date DATE NOT NULL,
            daily_rain DECIMAL(10, 2),
            accumulated_rain DECIMAL(10, 2),
            risk_level VARCHAR(50),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Latest Forecasts View/Table
    op.execute("""
        CREATE TABLE IF NOT EXISTS latest_forecasts (
            id SERIAL PRIMARY KEY,
            basin_code VARCHAR(50) NOT NULL,
            forecast_data JSONB,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Station Data - Dữ liệu trạm
    op.execute("""
        CREATE TABLE IF NOT EXISTS station_data (
            id SERIAL PRIMARY KEY,
            station_id INTEGER REFERENCES monitoring_stations(id),
            recorded_at TIMESTAMP NOT NULL,
            water_level DECIMAL(10, 2),
            rainfall DECIMAL(10, 2),
            temperature DECIMAL(5, 2),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # === Alert Tables ===

    # Alerts - Cảnh báo
    op.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id SERIAL PRIMARY KEY,
            alert_type VARCHAR(50) NOT NULL,
            severity VARCHAR(20) NOT NULL,
            title VARCHAR(255) NOT NULL,
            description TEXT,
            location VARCHAR(255),
            latitude DECIMAL(10, 6),
            longitude DECIMAL(10, 6),
            start_time TIMESTAMP,
            end_time TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Active Alerts - Cảnh báo đang hoạt động
    op.execute("""
        CREATE TABLE IF NOT EXISTS active_alerts (
            id SERIAL PRIMARY KEY,
            alert_id INTEGER REFERENCES alerts(id),
            is_active BOOLEAN DEFAULT TRUE,
            acknowledged_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # === Cache Tables ===

    # AI Analysis Cache
    op.execute("""
        CREATE TABLE IF NOT EXISTS ai_analysis_cache (
            id SERIAL PRIMARY KEY,
            basin_code VARCHAR(50) NOT NULL,
            analysis_date DATE NOT NULL,
            analysis_data JSONB NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(basin_code, analysis_date)
        )
    """)

    # AI Analysis Jobs
    op.execute("""
        CREATE TABLE IF NOT EXISTS ai_analysis_jobs (
            id SERIAL PRIMARY KEY,
            job_id VARCHAR(100) UNIQUE NOT NULL,
            basin_code VARCHAR(50) NOT NULL,
            status VARCHAR(20) DEFAULT 'pending',
            progress INTEGER DEFAULT 0,
            result JSONB,
            error TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Forecast Cache
    op.execute("""
        CREATE TABLE IF NOT EXISTS forecast_cache (
            id SERIAL PRIMARY KEY,
            forecast_date DATE NOT NULL UNIQUE,
            basins_data JSONB NOT NULL,
            stations_loaded INTEGER DEFAULT 0,
            stations_failed JSONB DEFAULT '[]',
            fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Weather Alerts Cache
    op.execute("""
        CREATE TABLE IF NOT EXISTS weather_alerts_cache (
            id SERIAL PRIMARY KEY,
            cache_date DATE NOT NULL UNIQUE,
            alerts_data JSONB NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Dam Alerts Cache
    op.execute("""
        CREATE TABLE IF NOT EXISTS dam_alerts_cache (
            id SERIAL PRIMARY KEY,
            cache_date DATE NOT NULL UNIQUE,
            alerts_data JSONB NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Combined Alerts Cache
    op.execute("""
        CREATE TABLE IF NOT EXISTS combined_alerts_cache (
            id SERIAL PRIMARY KEY,
            cache_date DATE NOT NULL UNIQUE,
            alerts_data JSONB NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Weather Forecast Cache
    op.execute("""
        CREATE TABLE IF NOT EXISTS weather_forecast_cache (
            id SERIAL PRIMARY KEY,
            cache_date DATE NOT NULL UNIQUE,
            forecast_data JSONB NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Flood Forecast Cache
    op.execute("""
        CREATE TABLE IF NOT EXISTS flood_forecast_cache (
            id SERIAL PRIMARY KEY,
            cache_date DATE NOT NULL UNIQUE,
            forecast_data JSONB NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # === EVN Reservoir Tables ===

    # EVN Reservoirs - Hồ chứa EVN
    op.execute("""
        CREATE TABLE IF NOT EXISTS evn_reservoirs (
            id SERIAL PRIMARY KEY,
            reservoir_id VARCHAR(50),
            name VARCHAR(255) NOT NULL,
            river VARCHAR(100),
            province VARCHAR(100),
            capacity DECIMAL(15, 2),
            dead_capacity DECIMAL(15, 2),
            current_level DECIMAL(10, 2),
            current_volume DECIMAL(15, 2),
            inflow DECIMAL(10, 2),
            outflow DECIMAL(10, 2),
            recorded_date DATE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # EVN Analysis Cache
    op.execute("""
        CREATE TABLE IF NOT EXISTS evn_analysis_cache (
            id SERIAL PRIMARY KEY,
            reservoir_id VARCHAR(50) NOT NULL,
            analysis_date DATE NOT NULL,
            analysis_data JSONB NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(reservoir_id, analysis_date)
        )
    """)

    # === Today's Alert Views ===

    # Today Weather Alerts
    op.execute("""
        CREATE TABLE IF NOT EXISTS today_weather_alerts (
            id SERIAL PRIMARY KEY,
            alert_data JSONB NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Today Dam Alerts
    op.execute("""
        CREATE TABLE IF NOT EXISTS today_dam_alerts (
            id SERIAL PRIMARY KEY,
            alert_data JSONB NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Valid AI Analysis View
    op.execute("""
        CREATE TABLE IF NOT EXISTS valid_ai_analysis (
            id SERIAL PRIMARY KEY,
            basin_code VARCHAR(50) NOT NULL,
            analysis_date DATE NOT NULL,
            is_valid BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # === Indexes ===
    op.execute("CREATE INDEX IF NOT EXISTS idx_ai_cache_basin_date ON ai_analysis_cache(basin_code, analysis_date)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_forecast_cache_date ON forecast_cache(forecast_date)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_evn_reservoirs_date ON evn_reservoirs(recorded_date)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_alerts_type ON alerts(alert_type)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_station_data_time ON station_data(recorded_at)")


def downgrade() -> None:
    """Downgrade schema - Drop all tables."""

    # Drop in reverse order (dependencies first)
    tables = [
        'valid_ai_analysis',
        'today_dam_alerts',
        'today_weather_alerts',
        'evn_analysis_cache',
        'evn_reservoirs',
        'flood_forecast_cache',
        'weather_forecast_cache',
        'combined_alerts_cache',
        'dam_alerts_cache',
        'weather_alerts_cache',
        'forecast_cache',
        'ai_analysis_jobs',
        'ai_analysis_cache',
        'active_alerts',
        'alerts',
        'station_data',
        'latest_forecasts',
        'forecasts',
        'flood_thresholds',
        'locations',
        'dams',
        'monitoring_stations',
        'basins',
    ]

    for table in tables:
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
