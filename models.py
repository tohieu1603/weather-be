from sqlalchemy import Column, Integer, String, Numeric, Date, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.sql import func
from database import Base

class Basin(Base):
    __tablename__ = "basins"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, nullable=False)
    name = Column(String(200), nullable=False)
    name_vi = Column(String(200), nullable=False)
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class MonitoringStation(Base):
    __tablename__ = "monitoring_stations"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, nullable=False)
    name = Column(String(200), nullable=False)
    latitude = Column(Numeric(10, 7), nullable=False)
    longitude = Column(Numeric(10, 7), nullable=False)
    river = Column(String(100))
    station_type = Column(String(50))
    basin_code = Column(String(50), ForeignKey("basins.code"))
    weight = Column(Numeric(5, 3), default=1.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class FloodThreshold(Base):
    __tablename__ = "flood_thresholds"

    id = Column(Integer, primary_key=True, index=True)
    basin_code = Column(String(50), ForeignKey("basins.code"))
    level = Column(String(20), nullable=False)
    daily_threshold = Column(Numeric(10, 2), nullable=False)
    accumulated_3d_threshold = Column(Numeric(10, 2), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Forecast(Base):
    __tablename__ = "forecasts"

    id = Column(Integer, primary_key=True, index=True)
    basin_code = Column(String(50), ForeignKey("basins.code"))
    forecast_date = Column(Date, nullable=False)
    daily_rain = Column(Numeric(10, 2))
    accumulated_3d = Column(Numeric(10, 2))
    risk_level = Column(String(20))
    risk_description = Column(Text)
    generated_at = Column(DateTime(timezone=True), server_default=func.now())


class StationData(Base):
    __tablename__ = "station_data"

    id = Column(Integer, primary_key=True, index=True)
    station_code = Column(String(50), ForeignKey("monitoring_stations.code"))
    forecast_date = Column(Date, nullable=False)
    precipitation_sum = Column(Numeric(10, 2))
    precipitation_hours = Column(Integer)
    precipitation_probability_max = Column(Integer)
    generated_at = Column(DateTime(timezone=True), server_default=func.now())


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    basin_code = Column(String(50), ForeignKey("basins.code"))
    alert_date = Column(Date, nullable=False)
    risk_level = Column(String(20), nullable=False)
    daily_rain = Column(Numeric(10, 2))
    accumulated_3d = Column(Numeric(10, 2))
    description = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
