#!/usr/bin/env python3
"""
Configuration module
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Database config
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "5433")),
    "database": os.getenv("DB_NAME", "flood_forecast"),
    "user": os.getenv("DB_USER", "flooduser"),
    "password": os.getenv("DB_PASSWORD", "floodpass123"),
}

# DeepSeek AI config
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"

# Cache settings
CACHE_TTL_SECONDS = 3600  # 1 hour for weather data
AI_CACHE_TTL_DAYS = 1  # 1 day for AI analysis

# API settings
CORS_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:3001",
    "http://localhost:3002",
]
