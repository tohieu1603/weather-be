#!/usr/bin/env python3
"""
AI Job Repository - Database operations for AI analysis job queue
"""
import uuid
from datetime import datetime
from typing import Optional, Dict, Any
from psycopg2.extras import Json

from .base import BaseRepository


class AIJobRepository(BaseRepository):
    """Repository for AI analysis job queue operations"""

    def create_job(
        self,
        basin_code: str,
        forecast_data: Dict[str, Any]
    ) -> str:
        """
        Create a new AI analysis job

        Args:
            basin_code: Basin code (HONG, CENTRAL, MEKONG, DONGNAI)
            forecast_data: Forecast data for analysis

        Returns:
            job_id: Unique job identifier
        """
        job_id = f"ai_{basin_code.lower()}_{uuid.uuid4().hex[:8]}"

        query = """
            INSERT INTO ai_analysis_jobs (
                job_id, basin_code, status, progress, forecast_data
            ) VALUES (%s, %s, 'pending', 0, %s)
            ON CONFLICT (job_id) DO NOTHING
        """

        success = self.execute_insert(query, (job_id, basin_code, Json(forecast_data)))
        if success:
            print(f"[AIJob] Created job {job_id} for {basin_code}")
        return job_id

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get job status by job_id

        Args:
            job_id: Unique job identifier

        Returns:
            Job data dict or None
        """
        query = """
            SELECT job_id, basin_code, status, progress,
                   result, error_message,
                   created_at, started_at, completed_at
            FROM ai_analysis_jobs
            WHERE job_id = %s AND expires_at > CURRENT_TIMESTAMP
        """

        row = self.execute_query(query, (job_id,), fetch_one=True)
        if row:
            return dict(row)
        return None

    def get_pending_job(self, basin_code: str) -> Optional[Dict[str, Any]]:
        """
        Get existing pending/processing job for a basin

        Args:
            basin_code: Basin code

        Returns:
            Job data dict or None
        """
        query = """
            SELECT job_id, basin_code, status, progress,
                   forecast_data, created_at
            FROM ai_analysis_jobs
            WHERE basin_code = %s
              AND status IN ('pending', 'processing')
              AND expires_at > CURRENT_TIMESTAMP
            ORDER BY created_at DESC
            LIMIT 1
        """

        row = self.execute_query(query, (basin_code,), fetch_one=True)
        if row:
            return dict(row)
        return None

    def update_status(
        self,
        job_id: str,
        status: str,
        progress: int = None,
        result: Dict[str, Any] = None,
        error_message: str = None
    ) -> bool:
        """
        Update job status

        Args:
            job_id: Job identifier
            status: New status (pending, processing, completed, failed)
            progress: Progress percentage (0-100)
            result: Analysis result (for completed status)
            error_message: Error message (for failed status)

        Returns:
            True if updated successfully
        """
        updates = ["status = %s"]
        params = [status]

        if progress is not None:
            updates.append("progress = %s")
            params.append(progress)

        if status == "processing":
            updates.append("started_at = CURRENT_TIMESTAMP")

        if status == "completed":
            updates.append("completed_at = CURRENT_TIMESTAMP")
            updates.append("progress = 100")
            if result:
                updates.append("result = %s")
                params.append(Json(result))

        if status == "failed":
            updates.append("completed_at = CURRENT_TIMESTAMP")
            if error_message:
                updates.append("error_message = %s")
                params.append(error_message)

        params.append(job_id)

        query = f"""
            UPDATE ai_analysis_jobs
            SET {', '.join(updates)}
            WHERE job_id = %s
        """

        return self.execute_insert(query, tuple(params))

    def cleanup_expired(self) -> int:
        """
        Delete expired jobs

        Returns:
            Number of deleted jobs
        """
        query = "SELECT cleanup_expired_ai_jobs()"
        result = self.execute_query(query, fetch_one=True)
        return result[0] if result else 0

    def get_recent_completed(self, basin_code: str, hours: int = 6) -> Optional[Dict[str, Any]]:
        """
        Get recently completed job result for a basin

        Args:
            basin_code: Basin code
            hours: How many hours back to look

        Returns:
            Job with result or None
        """
        query = """
            SELECT job_id, basin_code, result, completed_at
            FROM ai_analysis_jobs
            WHERE basin_code = %s
              AND status = 'completed'
              AND result IS NOT NULL
              AND completed_at > CURRENT_TIMESTAMP - INTERVAL '%s hours'
            ORDER BY completed_at DESC
            LIMIT 1
        """

        row = self.execute_query(query, (basin_code, hours), fetch_one=True)
        if row:
            return dict(row)
        return None
