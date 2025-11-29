#!/usr/bin/env python3
"""
Database connection và các hàm cache cho PostgreSQL
"""
import os
import json
from datetime import datetime, date
from typing import Optional, Dict, Any
import psycopg2
from psycopg2.extras import RealDictCursor, Json
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


def get_connection():
    """Tạo kết nối database"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        print(f"Database connection error: {e}")
        return None


def check_db_available() -> bool:
    """Kiểm tra database có sẵn không"""
    conn = get_connection()
    if conn:
        conn.close()
        return True
    return False


# =====================================================
# CACHE CHO KẾT QUẢ PHÂN TÍCH DEEPSEEK AI
# =====================================================

def get_cached_ai_analysis(basin_code: str, analysis_date: date = None) -> Optional[Dict]:
    """
    Lấy kết quả phân tích AI từ cache

    Args:
        basin_code: Mã lưu vực (HONG, CENTRAL, MEKONG, DONGNAI)
        analysis_date: Ngày phân tích (mặc định là hôm nay)

    Returns:
        Dict chứa kết quả phân tích hoặc None nếu không có cache
    """
    if analysis_date is None:
        analysis_date = date.today()

    conn = get_connection()
    if not conn:
        return None

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT * FROM ai_analysis_cache
                WHERE basin_code = %s
                  AND analysis_date = %s
                  AND expires_at > CURRENT_TIMESTAMP
                ORDER BY fetched_at DESC
                LIMIT 1
            """, (basin_code, analysis_date))

            row = cur.fetchone()
            if row:
                result = dict(row)
                return {
                    "peak_rain": result.get("peak_rain"),
                    "flood_timeline": result.get("flood_timeline"),
                    "affected_areas": result.get("affected_areas"),
                    "overall_risk": result.get("overall_risk"),
                    "recommendations": result.get("recommendations"),
                    "summary": result.get("summary"),
                    "cached_at": result.get("fetched_at").isoformat() if result.get("fetched_at") else None,
                    "from_cache": True
                }
            return None
    except Exception as e:
        print(f"Error getting cached AI analysis: {e}")
        return None
    finally:
        conn.close()


def save_ai_analysis_cache(
    basin_code: str,
    analysis: Dict,
    analysis_date: date = None,
    tokens_used: int = None
) -> bool:
    """
    Lưu kết quả phân tích AI vào cache
    """
    if analysis_date is None:
        analysis_date = date.today()

    conn = get_connection()
    if not conn:
        return False

    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO ai_analysis_cache (
                    basin_code, analysis_date,
                    peak_rain, flood_timeline, affected_areas,
                    overall_risk, recommendations, summary,
                    raw_response, tokens_used
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT (basin_code, analysis_date)
                DO UPDATE SET
                    peak_rain = EXCLUDED.peak_rain,
                    flood_timeline = EXCLUDED.flood_timeline,
                    affected_areas = EXCLUDED.affected_areas,
                    overall_risk = EXCLUDED.overall_risk,
                    recommendations = EXCLUDED.recommendations,
                    summary = EXCLUDED.summary,
                    raw_response = EXCLUDED.raw_response,
                    tokens_used = EXCLUDED.tokens_used,
                    fetched_at = CURRENT_TIMESTAMP,
                    expires_at = CURRENT_TIMESTAMP + INTERVAL '1 day'
            """, (
                basin_code,
                analysis_date,
                Json(analysis.get("peak_rain")),
                Json(analysis.get("flood_timeline")),
                Json(analysis.get("affected_areas")),
                Json(analysis.get("overall_risk")),
                Json(analysis.get("recommendations")),
                analysis.get("summary"),
                Json(analysis),
                tokens_used
            ))
            conn.commit()
            print(f"✓ Cached AI analysis for {basin_code} on {analysis_date}")
            return True
    except Exception as e:
        print(f"Error saving AI analysis cache: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


def cleanup_expired_cache() -> int:
    """Xóa các cache đã hết hạn"""
    conn = get_connection()
    if not conn:
        return 0

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT cleanup_expired_ai_cache()")
            result = cur.fetchone()
            conn.commit()
            return result[0] if result else 0
    except Exception as e:
        print(f"Error cleaning up cache: {e}")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    print("Testing database connection...")
    if check_db_available():
        print("✓ Database connected successfully!")
        deleted = cleanup_expired_cache()
        print(f"✓ Cleaned up {deleted} expired cache entries")
    else:
        print("✗ Cannot connect to database")
        print(f"  Config: {DB_CONFIG}")
