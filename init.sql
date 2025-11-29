-- Schema khởi tạo cho Hệ thống Dự báo Lũ Lụt

-- Bảng lưu vực
CREATE TABLE IF NOT EXISTS basins (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(200) NOT NULL,
    name_vi VARCHAR(200) NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Bảng điểm quan trắc
CREATE TABLE IF NOT EXISTS monitoring_stations (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(200) NOT NULL,
    latitude DECIMAL(10, 7) NOT NULL,
    longitude DECIMAL(10, 7) NOT NULL,
    river VARCHAR(100),
    station_type VARCHAR(50),
    basin_code VARCHAR(50) REFERENCES basins(code),
    weight DECIMAL(5, 3) DEFAULT 1.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Bảng ngưỡng cảnh báo
CREATE TABLE IF NOT EXISTS flood_thresholds (
    id SERIAL PRIMARY KEY,
    basin_code VARCHAR(50) REFERENCES basins(code),
    level VARCHAR(20) NOT NULL, -- watch, warning, danger
    daily_threshold DECIMAL(10, 2) NOT NULL,
    accumulated_3d_threshold DECIMAL(10, 2) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(basin_code, level)
);

-- Bảng dữ liệu dự báo
CREATE TABLE IF NOT EXISTS forecasts (
    id SERIAL PRIMARY KEY,
    basin_code VARCHAR(50) REFERENCES basins(code),
    forecast_date DATE NOT NULL,
    daily_rain DECIMAL(10, 2),
    accumulated_3d DECIMAL(10, 2),
    risk_level VARCHAR(20),
    risk_description TEXT,
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(basin_code, forecast_date, generated_at)
);

-- Bảng dữ liệu thô từ trạm
CREATE TABLE IF NOT EXISTS station_data (
    id SERIAL PRIMARY KEY,
    station_code VARCHAR(50) REFERENCES monitoring_stations(code),
    forecast_date DATE NOT NULL,
    precipitation_sum DECIMAL(10, 2),
    precipitation_hours INTEGER,
    precipitation_probability_max INTEGER,
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(station_code, forecast_date, generated_at)
);

-- Bảng cảnh báo
CREATE TABLE IF NOT EXISTS alerts (
    id SERIAL PRIMARY KEY,
    basin_code VARCHAR(50) REFERENCES basins(code),
    alert_date DATE NOT NULL,
    risk_level VARCHAR(20) NOT NULL,
    daily_rain DECIMAL(10, 2),
    accumulated_3d DECIMAL(10, 2),
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index cho query nhanh hơn
CREATE INDEX idx_forecasts_basin_date ON forecasts(basin_code, forecast_date);
CREATE INDEX idx_station_data_station_date ON station_data(station_code, forecast_date);
CREATE INDEX idx_alerts_active ON alerts(is_active, basin_code);
CREATE INDEX idx_forecasts_generated ON forecasts(generated_at DESC);

-- Insert dữ liệu mẫu cho basins
INSERT INTO basins (code, name, name_vi, description) VALUES
    ('Hong', 'Red River', 'Sông Hồng', 'Lưu vực sông Hồng - Thái Bình'),
    ('Mekong', 'Mekong River', 'Sông Mekong', 'Lưu vực sông Mekong/Cửu Long'),
    ('DongNai', 'Dong Nai River', 'Sông Đồng Nai', 'Lưu vực sông Đồng Nai'),
    ('Central', 'Central Rivers', 'Miền Trung', 'Các sông miền Trung')
ON CONFLICT (code) DO NOTHING;

-- Insert monitoring stations
INSERT INTO monitoring_stations (code, name, latitude, longitude, river, station_type, basin_code, weight) VALUES
    -- Sông Hồng
    ('lao_cai', 'Lào Cai', 22.4856, 103.9707, 'Hong', 'border', 'Hong', 1.0),
    ('yen_bai', 'Yên Bái', 21.7168, 104.8987, 'Hong', 'upstream', 'Hong', 1.0),
    ('ha_giang', 'Hà Giang', 22.8333, 104.9833, 'Lo', 'border', 'Hong', 0.8),
    ('tuyen_quang', 'Tuyên Quang', 21.8167, 105.2167, 'Lo', 'upstream', 'Hong', 0.8),
    ('viet_tri', 'Việt Trì', 21.3100, 105.4019, 'Hong', 'confluence', 'Hong', 0.6),
    ('son_tay', 'Sơn Tây', 21.1333, 105.5000, 'Hong', 'key_gauge', 'Hong', 0.6),
    ('hanoi', 'Hà Nội', 21.0285, 105.8542, 'Hong', 'capital', 'Hong', 0.6),
    ('hoa_binh_dam', 'Hồ Hòa Bình', 20.8167, 105.3167, 'Da', 'dam', 'Hong', 0.7),
    ('son_la_dam', 'Hồ Sơn La', 21.3261, 103.9008, 'Da', 'dam', 'Hong', 0.7),

    -- Mekong
    ('chiang_saen', 'Chiang Saen', 20.2667, 100.0833, 'Mekong', 'thai_gauge', 'Mekong', 1.0),
    ('vientiane', 'Vientiane', 17.9757, 102.6331, 'Mekong', 'lao_gauge', 'Mekong', 1.0),
    ('stung_treng', 'Stung Treng', 13.5167, 106.0167, 'Mekong', 'cambodia', 'Mekong', 0.8),
    ('tan_chau', 'Tân Châu', 10.8000, 105.2333, 'Tien', 'vn_entry', 'Mekong', 1.0),
    ('chau_doc', 'Châu Đốc', 10.7000, 105.1167, 'Hau', 'vn_entry', 'Mekong', 1.0),
    ('can_tho', 'Cần Thơ', 10.0452, 105.7469, 'Hau', 'delta_center', 'Mekong', 0.8),
    ('my_tho', 'Mỹ Tho', 10.3600, 106.3600, 'Tien', 'delta', 'Mekong', 0.8),

    -- Đồng Nai
    ('da_lat', 'Đà Lạt', 11.9404, 108.4583, 'DongNai', 'upstream', 'DongNai', 1.0),
    ('tri_an_dam', 'Hồ Trị An', 11.0833, 107.0167, 'DongNai', 'dam', 'DongNai', 1.0),
    ('bien_hoa', 'Biên Hòa', 10.9574, 106.8426, 'DongNai', 'downstream', 'DongNai', 0.8),

    -- Miền Trung
    ('hue', 'Huế', 16.4637, 107.5909, 'Huong', 'central', 'Central', 1.0),
    ('da_nang', 'Đà Nẵng', 16.0544, 108.2022, 'Han', 'central', 'Central', 1.0),
    ('quang_ngai', 'Quảng Ngãi', 15.1214, 108.8044, 'TraKhuc', 'central', 'Central', 1.0)
ON CONFLICT (code) DO NOTHING;

-- Insert flood thresholds
INSERT INTO flood_thresholds (basin_code, level, daily_threshold, accumulated_3d_threshold) VALUES
    -- Hong
    ('Hong', 'watch', 100, 250),
    ('Hong', 'warning', 150, 400),
    ('Hong', 'danger', 200, 600),

    -- Mekong
    ('Mekong', 'watch', 80, 200),
    ('Mekong', 'warning', 120, 350),
    ('Mekong', 'danger', 180, 550),

    -- DongNai
    ('DongNai', 'watch', 100, 250),
    ('DongNai', 'warning', 150, 400),
    ('DongNai', 'danger', 200, 600),

    -- Central
    ('Central', 'watch', 120, 300),
    ('Central', 'warning', 200, 500),
    ('Central', 'danger', 300, 800)
ON CONFLICT (basin_code, level) DO NOTHING;

-- Tạo function để tự động cập nhật updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger cho bảng alerts
CREATE TRIGGER update_alerts_updated_at BEFORE UPDATE ON alerts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- View để lấy dữ liệu dự báo mới nhất
CREATE OR REPLACE VIEW latest_forecasts AS
SELECT DISTINCT ON (basin_code, forecast_date)
    id,
    basin_code,
    forecast_date,
    daily_rain,
    accumulated_3d,
    risk_level,
    risk_description,
    generated_at
FROM forecasts
ORDER BY basin_code, forecast_date, generated_at DESC;

-- View để lấy cảnh báo đang hoạt động
CREATE OR REPLACE VIEW active_alerts AS
SELECT
    a.*,
    b.name_vi as basin_name
FROM alerts a
JOIN basins b ON a.basin_code = b.code
WHERE a.is_active = TRUE
ORDER BY
    CASE a.risk_level
        WHEN 'NGUY HIỂM' THEN 1
        WHEN 'CẢNH BÁO' THEN 2
        WHEN 'THEO DÕI' THEN 3
        ELSE 4
    END,
    a.alert_date;

COMMENT ON TABLE basins IS 'Danh sách các lưu vực sông';
COMMENT ON TABLE monitoring_stations IS 'Các điểm quan trắc thủy văn';
COMMENT ON TABLE flood_thresholds IS 'Ngưỡng cảnh báo lũ theo lưu vực';
COMMENT ON TABLE forecasts IS 'Dữ liệu dự báo lũ';
COMMENT ON TABLE station_data IS 'Dữ liệu thô từ các trạm quan trắc';
COMMENT ON TABLE alerts IS 'Các cảnh báo lũ đang hoạt động';

-- =====================================================
-- BẢNG CACHE DỮ LIỆU THỜI TIẾT TỪ OPEN-METEO
-- Cập nhật 1 lần/ngày để query nhanh
-- =====================================================

-- Bảng địa điểm Việt Nam
CREATE TABLE IF NOT EXISTS locations (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(200) NOT NULL,
    latitude DECIMAL(10, 7) NOT NULL,
    longitude DECIMAL(10, 7) NOT NULL,
    region VARCHAR(50), -- north, central, highland, south
    province VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Bảng cache dự báo thời tiết (Open-Meteo)
CREATE TABLE IF NOT EXISTS weather_forecast_cache (
    id SERIAL PRIMARY KEY,
    location_code VARCHAR(50) REFERENCES locations(code),
    forecast_date DATE NOT NULL,
    temperature_max DECIMAL(5, 2),
    temperature_min DECIMAL(5, 2),
    precipitation_sum DECIMAL(10, 2),
    rain_sum DECIMAL(10, 2),
    precipitation_hours INTEGER,
    precipitation_probability_max INTEGER,
    wind_speed_max DECIMAL(6, 2),
    wind_gusts_max DECIMAL(6, 2),
    uv_index_max DECIMAL(4, 2),
    weather_code INTEGER,
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(location_code, forecast_date)
);

-- Bảng cache dự báo lũ (GloFAS)
CREATE TABLE IF NOT EXISTS flood_forecast_cache (
    id SERIAL PRIMARY KEY,
    location_code VARCHAR(50) REFERENCES locations(code),
    forecast_date DATE NOT NULL,
    river_discharge DECIMAL(12, 2), -- m³/s
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(location_code, forecast_date)
);

-- Bảng thông tin đập thủy điện
CREATE TABLE IF NOT EXISTS dams (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(200) NOT NULL,
    river VARCHAR(100),
    province VARCHAR(100),
    basin VARCHAR(50),
    capacity_mw INTEGER,
    reservoir_volume_million_m3 DECIMAL(10, 2),
    max_discharge_m3s DECIMAL(10, 2),
    normal_level_m DECIMAL(6, 2),
    flood_level_m DECIMAL(6, 2),
    dead_level_m DECIMAL(6, 2),
    spillway_gates INTEGER,
    latitude DECIMAL(10, 7),
    longitude DECIMAL(10, 7),
    warning_time_hours INTEGER,
    downstream_areas TEXT[], -- PostgreSQL array
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Bảng cache cảnh báo xả lũ đập
CREATE TABLE IF NOT EXISTS dam_alerts_cache (
    id SERIAL PRIMARY KEY,
    dam_code VARCHAR(50) REFERENCES dams(code),
    alert_date DATE NOT NULL,
    alert_level VARCHAR(20), -- emergency, warning, watch
    rainfall_mm DECIMAL(10, 2),
    rainfall_accumulated_mm DECIMAL(10, 2),
    estimated_discharge_m3s DECIMAL(10, 2),
    estimated_water_level_m DECIMAL(6, 2),
    spillway_gates_open INTEGER,
    river_discharge_glofas DECIMAL(12, 2),
    description TEXT,
    recommendations TEXT[],
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(dam_code, alert_date)
);

-- Bảng cache cảnh báo thời tiết tổng hợp
CREATE TABLE IF NOT EXISTS weather_alerts_cache (
    id SERIAL PRIMARY KEY,
    alert_id VARCHAR(100) UNIQUE NOT NULL,
    alert_type VARCHAR(50), -- heavy_rain, heat_wave, strong_wind, high_uv, flood
    category VARCHAR(50),
    title VARCHAR(300),
    severity VARCHAR(20), -- critical, high, medium, low
    alert_date DATE NOT NULL,
    location_code VARCHAR(50),
    region VARCHAR(100),
    provinces TEXT[],
    description TEXT,
    data JSONB,
    recommendations TEXT[],
    source VARCHAR(100),
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index cho query nhanh
CREATE INDEX IF NOT EXISTS idx_weather_cache_location_date ON weather_forecast_cache(location_code, forecast_date);
CREATE INDEX IF NOT EXISTS idx_flood_cache_location_date ON flood_forecast_cache(location_code, forecast_date);
CREATE INDEX IF NOT EXISTS idx_dam_alerts_date ON dam_alerts_cache(alert_date);
CREATE INDEX IF NOT EXISTS idx_weather_alerts_date ON weather_alerts_cache(alert_date, severity);
CREATE INDEX IF NOT EXISTS idx_weather_alerts_fetched ON weather_alerts_cache(fetched_at DESC);

-- View lấy cảnh báo mới nhất (trong ngày)
CREATE OR REPLACE VIEW today_weather_alerts AS
SELECT * FROM weather_alerts_cache
WHERE fetched_at >= CURRENT_DATE
ORDER BY
    CASE severity
        WHEN 'critical' THEN 1
        WHEN 'high' THEN 2
        WHEN 'medium' THEN 3
        WHEN 'low' THEN 4
        ELSE 5
    END,
    alert_date;

-- View lấy cảnh báo xả lũ mới nhất
CREATE OR REPLACE VIEW today_dam_alerts AS
SELECT
    d.*,
    dm.name as dam_name,
    dm.river,
    dm.province,
    dm.max_discharge_m3s,
    dm.spillway_gates as total_gates,
    dm.warning_time_hours,
    dm.downstream_areas
FROM dam_alerts_cache d
JOIN dams dm ON d.dam_code = dm.code
WHERE d.fetched_at >= CURRENT_DATE
ORDER BY
    CASE d.alert_level
        WHEN 'emergency' THEN 1
        WHEN 'warning' THEN 2
        WHEN 'watch' THEN 3
        ELSE 4
    END,
    d.alert_date;

-- Insert các địa điểm Việt Nam (63 tỉnh thành)
INSERT INTO locations (code, name, latitude, longitude, region, province) VALUES
    -- Miền Bắc
    ('hanoi', 'Hà Nội', 21.0285, 105.8542, 'north', 'Hà Nội'),
    ('hai_phong', 'Hải Phòng', 20.8449, 106.6881, 'north', 'Hải Phòng'),
    ('quang_ninh', 'Quảng Ninh', 21.0064, 107.2925, 'north', 'Quảng Ninh'),
    ('bac_ninh', 'Bắc Ninh', 21.1861, 106.0763, 'north', 'Bắc Ninh'),
    ('hai_duong', 'Hải Dương', 20.9373, 106.3145, 'north', 'Hải Dương'),
    ('hung_yen', 'Hưng Yên', 20.6464, 106.0511, 'north', 'Hưng Yên'),
    ('thai_binh', 'Thái Bình', 20.4463, 106.3365, 'north', 'Thái Bình'),
    ('nam_dinh', 'Nam Định', 20.4388, 106.1621, 'north', 'Nam Định'),
    ('ninh_binh', 'Ninh Bình', 20.2506, 105.9745, 'north', 'Ninh Bình'),
    ('ha_nam', 'Hà Nam', 20.5835, 105.9230, 'north', 'Hà Nam'),
    ('vinh_phuc', 'Vĩnh Phúc', 21.3609, 105.5474, 'north', 'Vĩnh Phúc'),
    ('bac_giang', 'Bắc Giang', 21.2819, 106.1946, 'north', 'Bắc Giang'),
    ('phu_tho', 'Phú Thọ', 21.4200, 105.2000, 'north', 'Phú Thọ'),
    ('thai_nguyen', 'Thái Nguyên', 21.5671, 105.8252, 'north', 'Thái Nguyên'),
    ('bac_kan', 'Bắc Kạn', 22.1471, 105.8348, 'north', 'Bắc Kạn'),
    ('cao_bang', 'Cao Bằng', 22.6667, 106.2500, 'north', 'Cao Bằng'),
    ('lang_son', 'Lạng Sơn', 21.8536, 106.7610, 'north', 'Lạng Sơn'),
    ('tuyen_quang', 'Tuyên Quang', 21.8167, 105.2167, 'north', 'Tuyên Quang'),
    ('ha_giang', 'Hà Giang', 22.8333, 104.9833, 'north', 'Hà Giang'),
    ('yen_bai', 'Yên Bái', 21.7168, 104.8987, 'north', 'Yên Bái'),
    ('lao_cai', 'Lào Cai', 22.4856, 103.9707, 'north', 'Lào Cai'),
    ('lai_chau', 'Lai Châu', 22.3864, 103.4701, 'north', 'Lai Châu'),
    ('dien_bien', 'Điện Biên', 21.3833, 103.0167, 'north', 'Điện Biên'),
    ('son_la', 'Sơn La', 21.3261, 103.9008, 'north', 'Sơn La'),
    ('hoa_binh', 'Hòa Bình', 20.8167, 105.3167, 'north', 'Hòa Bình'),
    -- Miền Trung
    ('thanh_hoa', 'Thanh Hóa', 19.8067, 105.7851, 'central', 'Thanh Hóa'),
    ('nghe_an', 'Nghệ An', 18.6793, 105.6811, 'central', 'Nghệ An'),
    ('ha_tinh', 'Hà Tĩnh', 18.3430, 105.9050, 'central', 'Hà Tĩnh'),
    ('quang_binh', 'Quảng Bình', 17.4676, 106.6222, 'central', 'Quảng Bình'),
    ('quang_tri', 'Quảng Trị', 16.7943, 107.1859, 'central', 'Quảng Trị'),
    ('thua_thien_hue', 'Thừa Thiên Huế', 16.4637, 107.5909, 'central', 'Thừa Thiên Huế'),
    ('da_nang', 'Đà Nẵng', 16.0544, 108.2022, 'central', 'Đà Nẵng'),
    ('quang_nam', 'Quảng Nam', 15.5393, 108.0192, 'central', 'Quảng Nam'),
    ('quang_ngai', 'Quảng Ngãi', 15.1214, 108.8044, 'central', 'Quảng Ngãi'),
    ('binh_dinh', 'Bình Định', 13.7830, 109.2192, 'central', 'Bình Định'),
    ('phu_yen', 'Phú Yên', 13.0955, 109.0929, 'central', 'Phú Yên'),
    ('khanh_hoa', 'Khánh Hòa', 12.2585, 109.0526, 'central', 'Khánh Hòa'),
    ('ninh_thuan', 'Ninh Thuận', 11.6739, 108.8629, 'central', 'Ninh Thuận'),
    ('binh_thuan', 'Bình Thuận', 10.9273, 108.1017, 'central', 'Bình Thuận'),
    -- Tây Nguyên
    ('kon_tum', 'Kon Tum', 14.3497, 108.0005, 'highland', 'Kon Tum'),
    ('gia_lai', 'Gia Lai', 13.9833, 108.0000, 'highland', 'Gia Lai'),
    ('dak_lak', 'Đắk Lắk', 12.6667, 108.0500, 'highland', 'Đắk Lắk'),
    ('dak_nong', 'Đắk Nông', 12.2646, 107.6098, 'highland', 'Đắk Nông'),
    ('lam_dong', 'Lâm Đồng', 11.9404, 108.4583, 'highland', 'Lâm Đồng'),
    -- Miền Nam
    ('ho_chi_minh', 'TP.HCM', 10.7769, 106.7009, 'south', 'TP.HCM'),
    ('binh_duong', 'Bình Dương', 11.3254, 106.4770, 'south', 'Bình Dương'),
    ('dong_nai', 'Đồng Nai', 10.9574, 106.8426, 'south', 'Đồng Nai'),
    ('binh_phuoc', 'Bình Phước', 11.7511, 106.7234, 'south', 'Bình Phước'),
    ('tay_ninh', 'Tây Ninh', 11.3351, 106.0987, 'south', 'Tây Ninh'),
    ('ba_ria_vung_tau', 'Bà Rịa-Vũng Tàu', 10.5417, 107.2429, 'south', 'Bà Rịa-Vũng Tàu'),
    ('long_an', 'Long An', 10.5333, 106.4167, 'south', 'Long An'),
    ('tien_giang', 'Tiền Giang', 10.3600, 106.3600, 'south', 'Tiền Giang'),
    ('ben_tre', 'Bến Tre', 10.2333, 106.3833, 'south', 'Bến Tre'),
    ('tra_vinh', 'Trà Vinh', 9.8128, 106.2992, 'south', 'Trà Vinh'),
    ('vinh_long', 'Vĩnh Long', 10.2395, 105.9572, 'south', 'Vĩnh Long'),
    ('dong_thap', 'Đồng Tháp', 10.4938, 105.6881, 'south', 'Đồng Tháp'),
    ('an_giang', 'An Giang', 10.5216, 105.1258, 'south', 'An Giang'),
    ('kien_giang', 'Kiên Giang', 10.0125, 105.0808, 'south', 'Kiên Giang'),
    ('can_tho', 'Cần Thơ', 10.0452, 105.7469, 'south', 'Cần Thơ'),
    ('hau_giang', 'Hậu Giang', 9.7577, 105.6412, 'south', 'Hậu Giang'),
    ('soc_trang', 'Sóc Trăng', 9.6024, 105.9739, 'south', 'Sóc Trăng'),
    ('bac_lieu', 'Bạc Liêu', 9.2840, 105.7244, 'south', 'Bạc Liêu'),
    ('ca_mau', 'Cà Mau', 9.1767, 105.1524, 'south', 'Cà Mau')
ON CONFLICT (code) DO NOTHING;

-- =====================================================
-- BẢNG CACHE KẾT QUẢ PHÂN TÍCH DEEPSEEK AI
-- Cache 1 ngày để không gọi lại AI
-- =====================================================

-- Bảng cache kết quả phân tích AI theo vùng
CREATE TABLE IF NOT EXISTS ai_analysis_cache (
    id SERIAL PRIMARY KEY,
    basin_code VARCHAR(50) NOT NULL, -- HONG, CENTRAL, MEKONG, DONGNAI
    analysis_date DATE NOT NULL,

    -- Kết quả phân tích (JSON)
    peak_rain JSONB, -- {date, amount_mm, intensity}
    flood_timeline JSONB, -- {rising_start, peak_date, receding_end}
    affected_areas JSONB, -- [{province, impact_level, districts: [...]}]
    overall_risk JSONB, -- {level, score, description}
    recommendations JSONB, -- {government: [], citizens: []}
    summary TEXT,

    -- Raw JSON response từ AI
    raw_response JSONB,

    -- Metadata
    model_used VARCHAR(50) DEFAULT 'deepseek-chat',
    tokens_used INTEGER,
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP DEFAULT (CURRENT_TIMESTAMP + INTERVAL '1 day'),

    UNIQUE(basin_code, analysis_date)
);

-- Index cho query nhanh
CREATE INDEX IF NOT EXISTS idx_ai_cache_basin_date ON ai_analysis_cache(basin_code, analysis_date);
CREATE INDEX IF NOT EXISTS idx_ai_cache_expires ON ai_analysis_cache(expires_at);

-- View lấy phân tích còn hiệu lực (chưa hết hạn)
CREATE OR REPLACE VIEW valid_ai_analysis AS
SELECT * FROM ai_analysis_cache
WHERE expires_at > CURRENT_TIMESTAMP
ORDER BY fetched_at DESC;

-- Function xóa cache hết hạn
CREATE OR REPLACE FUNCTION cleanup_expired_ai_cache()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM ai_analysis_cache WHERE expires_at < CURRENT_TIMESTAMP;
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Insert các đập thủy điện chính
INSERT INTO dams (code, name, river, province, basin, capacity_mw, reservoir_volume_million_m3, max_discharge_m3s, normal_level_m, flood_level_m, dead_level_m, spillway_gates, latitude, longitude, warning_time_hours, downstream_areas) VALUES
    ('hoa_binh', 'Thủy điện Hòa Bình', 'Sông Đà', 'Hòa Bình', 'HONG', 1920, 9450, 27000, 117, 120, 80, 12, 20.8167, 105.3167, 6, ARRAY['Thành phố Hòa Bình', 'Hà Nội', 'Hà Nam', 'Nam Định']),
    ('son_la', 'Thủy điện Sơn La', 'Sông Đà', 'Sơn La', 'HONG', 2400, 9260, 35640, 215, 217.83, 175, 12, 21.2833, 103.9500, 8, ARRAY['Thành phố Sơn La', 'Hòa Bình', 'Hà Nội', 'Phú Thọ']),
    ('lai_chau', 'Thủy điện Lai Châu', 'Sông Đà', 'Lai Châu', 'HONG', 1200, 1215, 15300, 295, 297, 270, 8, 22.0500, 103.1833, 10, ARRAY['Thành phố Lai Châu', 'Điện Biên', 'Sơn La']),
    ('a_vuong', 'Thủy điện A Vương', 'Sông Vu Gia', 'Quảng Nam', 'CENTRAL', 210, 343, 4500, 380, 381, 340, 4, 15.8500, 107.5833, 4, ARRAY['Đà Nẵng', 'Quảng Nam', 'Hội An']),
    ('song_tranh_2', 'Thủy điện Sông Tranh 2', 'Sông Tranh', 'Quảng Nam', 'CENTRAL', 190, 730, 5000, 175, 178, 140, 5, 15.4167, 108.0333, 3, ARRAY['Quảng Nam', 'Tam Kỳ', 'Núi Thành']),
    ('tri_an', 'Thủy điện Trị An', 'Sông Đồng Nai', 'Đồng Nai', 'DONGNAI', 400, 2765, 8000, 62, 63.9, 50, 8, 11.0833, 107.0167, 5, ARRAY['Biên Hòa', 'TP.HCM', 'Long Thành']),
    ('dau_tieng', 'Hồ Dầu Tiếng', 'Sông Sài Gòn', 'Tây Ninh', 'DONGNAI', 0, 1580, 2800, 24.4, 25, 17, 6, 11.2833, 106.3167, 4, ARRAY['Tây Ninh', 'Củ Chi', 'TP.HCM']),
    ('yali', 'Thủy điện Yaly', 'Sông Sê San', 'Gia Lai', 'HIGHLAND', 720, 1037, 12500, 515, 516, 490, 6, 14.2000, 107.8167, 6, ARRAY['Gia Lai', 'Kon Tum'])
ON CONFLICT (code) DO NOTHING;
