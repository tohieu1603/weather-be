#!/usr/bin/env python3
"""
Data models / Pydantic schemas
"""
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import date, datetime
from enum import Enum


class AlertLevel(str, Enum):
    EMERGENCY = "emergency"
    WARNING = "warning"
    WATCH = "watch"
    SAFE = "safe"


class RiskLevel(str, Enum):
    VERY_HIGH = "Rất cao"
    HIGH = "Cao"
    MEDIUM = "Trung bình"
    LOW = "Thấp"
    VERY_LOW = "Rất thấp"


# =====================================================
# Request/Response Models
# =====================================================

class BasinSummary(BaseModel):
    basin_id: int
    basin_name: str
    total_stations: int
    danger_count: int
    warning_count: int
    watch_count: int
    safe_count: int


class ForecastDay(BaseModel):
    date: str
    daily_rain: float
    accumulated_3d: float
    river_discharge: float
    risk_level: str
    warning_message: Optional[str] = None


class BasinForecast(BaseModel):
    basin: str
    data: Dict[str, Any]
    ai_analysis: Optional[Dict[str, Any]] = None
    generated_at: str


# =====================================================
# AI Analysis Models
# =====================================================

class PeakRain(BaseModel):
    date: str
    amount_mm: float
    intensity: str


class FloodTimeline(BaseModel):
    rising_start: Optional[str] = None
    rising_end: Optional[str] = None
    peak_date: Optional[str] = None
    receding_start: Optional[str] = None
    receding_end: Optional[str] = None


class DistrictImpact(BaseModel):
    name: str
    impact_level: str
    water_level_cm: Optional[int] = None
    flood_area_km2: Optional[float] = None
    affected_wards: List[str] = []
    evacuation_needed: bool = False
    notes: Optional[str] = None


class ProvinceImpact(BaseModel):
    province: str
    impact_level: str
    water_level_cm: Optional[int] = None
    flood_area_km2: Optional[float] = None
    reason: Optional[str] = None
    districts: List[DistrictImpact] = []


class OverallRisk(BaseModel):
    level: str
    score: int
    description: str


class Recommendations(BaseModel):
    government: List[str] = []
    citizens: List[str] = []


class AIAnalysis(BaseModel):
    peak_rain: Optional[PeakRain] = None
    flood_timeline: Optional[FloodTimeline] = None
    affected_areas: List[ProvinceImpact] = []
    overall_risk: Optional[OverallRisk] = None
    recommendations: Optional[Recommendations] = None
    summary: Optional[str] = None
    from_cache: bool = False
    cached_at: Optional[str] = None


# =====================================================
# Dam Models
# =====================================================

class Dam(BaseModel):
    code: str
    name: str
    river: Optional[str] = None
    province: Optional[str] = None
    basin: Optional[str] = None
    capacity_mw: Optional[int] = None
    reservoir_volume_million_m3: Optional[float] = None
    max_discharge_m3s: Optional[float] = None
    normal_level_m: Optional[float] = None
    flood_level_m: Optional[float] = None
    spillway_gates: Optional[int] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    warning_time_hours: Optional[int] = None
    downstream_areas: List[str] = []


class DamAlert(BaseModel):
    dam_code: str
    dam_name: str
    alert_level: str
    alert_date: date
    rainfall_mm: Optional[float] = None
    estimated_discharge_m3s: Optional[float] = None
    spillway_gates_open: Optional[int] = None
    description: Optional[str] = None
    recommendations: List[str] = []


# =====================================================
# Weather Models
# =====================================================

class WeatherForecast(BaseModel):
    location: str
    date: str
    temperature_max: Optional[float] = None
    temperature_min: Optional[float] = None
    precipitation_sum: Optional[float] = None
    precipitation_probability: Optional[int] = None
    wind_speed_max: Optional[float] = None
    weather_code: Optional[int] = None
    weather_description: Optional[str] = None


class WeatherAlert(BaseModel):
    alert_id: str
    alert_type: str
    title: str
    severity: str
    region: Optional[str] = None
    provinces: List[str] = []
    description: Optional[str] = None
    recommendations: List[str] = []
    source: str = "Open-Meteo"


class Location(BaseModel):
    code: str
    name: str
    latitude: float
    longitude: float
    region: Optional[str] = None
    province: Optional[str] = None
