-- Migration: Add AI job queue for background processing
-- This allows non-blocking AI analysis

-- AI Analysis Job Queue
-- Stores job status for background AI processing
CREATE TABLE IF NOT EXISTS ai_analysis_jobs (
    id SERIAL PRIMARY KEY,
    job_id VARCHAR(50) UNIQUE NOT NULL,
    basin_code VARCHAR(20) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',  -- pending, processing, completed, failed
    progress INTEGER DEFAULT 0,  -- 0-100

    -- Input data (stored for retry)
    forecast_data JSONB,

    -- Output data (populated when completed)
    result JSONB,
    error_message TEXT,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,

    -- Expiry (auto-cleanup after 1 hour)
    expires_at TIMESTAMP DEFAULT (CURRENT_TIMESTAMP + INTERVAL '1 hour')
);

-- Index for fast job lookup
CREATE INDEX IF NOT EXISTS idx_ai_jobs_job_id ON ai_analysis_jobs(job_id);
CREATE INDEX IF NOT EXISTS idx_ai_jobs_basin_status ON ai_analysis_jobs(basin_code, status);
CREATE INDEX IF NOT EXISTS idx_ai_jobs_expires ON ai_analysis_jobs(expires_at);

-- Cleanup function for expired jobs
CREATE OR REPLACE FUNCTION cleanup_expired_ai_jobs()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM ai_analysis_jobs WHERE expires_at < CURRENT_TIMESTAMP;
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Comment
COMMENT ON TABLE ai_analysis_jobs IS 'Background job queue for AI analysis, expires after 1 hour';
