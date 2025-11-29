-- Migration: Add cache tables for alerts and reservoir analysis
-- Expires after 1 day

-- 1. EVN Reservoir Analysis Cache
-- Stores comprehensive analysis results per basin
CREATE TABLE IF NOT EXISTS evn_analysis_cache (
    id SERIAL PRIMARY KEY,
    basin_code VARCHAR(20) NOT NULL,
    analysis_date DATE NOT NULL DEFAULT CURRENT_DATE,
    analysis_data JSONB NOT NULL,
    reservoir_status JSONB,
    weather_risk JSONB,
    combined_risk_level VARCHAR(20),
    combined_risk_score INTEGER,
    summary TEXT,
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP DEFAULT (CURRENT_TIMESTAMP + INTERVAL '1 day'),
    UNIQUE(basin_code, analysis_date)
);

-- 2. Combined Alerts Cache
-- Stores all alerts (weather + dam + AI analysis) combined
CREATE TABLE IF NOT EXISTS combined_alerts_cache (
    id SERIAL PRIMARY KEY,
    cache_key VARCHAR(100) NOT NULL,  -- 'all', 'weather', 'dam', 'reservoir_analysis'
    cache_date DATE NOT NULL DEFAULT CURRENT_DATE,
    alerts_data JSONB NOT NULL,
    summary_data JSONB,
    total_count INTEGER DEFAULT 0,
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP DEFAULT (CURRENT_TIMESTAMP + INTERVAL '1 day'),
    UNIQUE(cache_key, cache_date)
);

-- Index for faster queries
CREATE INDEX IF NOT EXISTS idx_evn_analysis_cache_basin_date
ON evn_analysis_cache(basin_code, analysis_date);

CREATE INDEX IF NOT EXISTS idx_evn_analysis_cache_expires
ON evn_analysis_cache(expires_at);

CREATE INDEX IF NOT EXISTS idx_combined_alerts_cache_key_date
ON combined_alerts_cache(cache_key, cache_date);

CREATE INDEX IF NOT EXISTS idx_combined_alerts_cache_expires
ON combined_alerts_cache(expires_at);

-- Cleanup function for expired cache
CREATE OR REPLACE FUNCTION cleanup_expired_evn_analysis_cache()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM evn_analysis_cache WHERE expires_at < CURRENT_TIMESTAMP;
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION cleanup_expired_combined_alerts_cache()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM combined_alerts_cache WHERE expires_at < CURRENT_TIMESTAMP;
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Comments
COMMENT ON TABLE evn_analysis_cache IS 'Cache for EVN reservoir analysis per basin, expires after 1 day';
COMMENT ON TABLE combined_alerts_cache IS 'Cache for combined weather/dam/AI alerts, expires after 1 day';
