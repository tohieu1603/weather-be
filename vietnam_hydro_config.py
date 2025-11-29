#!/usr/bin/env python3
"""
Cấu hình thủy văn chi tiết cho Việt Nam
Dữ liệu từ các nguồn chính thống:
- Tổng cục Khí tượng Thủy văn Việt Nam
- Bộ Nông nghiệp và Phát triển Nông thôn
- Mekong River Commission (MRC)
- USGS, NASA Earth Data
"""

from typing import Dict, List, Tuple
from datetime import datetime

# ============================================================================
# PHẦN 1: LƯU VỰC SÔNG HỒNG - THÁI BÌNH
# ============================================================================

HONG_RIVER_BASIN = {
    "overview": {
        "total_area_km2": 169000,  # Toàn bộ lưu vực (bao gồm TQ)
        "vn_area_km2": 87800,
        "annual_rainfall_mm": 1800,
        "population": 22000000,
        "main_tributaries": ["Sông Hồng", "Sông Đà", "Sông Lô", "Sông Thao"],
    },

    # Các đập thủy điện Việt Nam (Sông Đà)
    "dams": {
        "son_la": {
            "river": "Đà",
            "capacity_million_m3": 9260,
            "normal_level_m": 215.0,
            "flood_level_m": 217.8,
            "dead_level_m": 175.0,
            "max_discharge_m3_s": 35420,
            "turbine_capacity_m3_s": 2400,
            "power_mw": 2400,
            "commissioned_year": 2012,
            "coordinates": (21.3261, 103.9008),
            "catchment_area_km2": 61300,
        },
        "hoa_binh": {
            "river": "Đà",
            "capacity_million_m3": 9450,
            "normal_level_m": 117.0,
            "flood_level_m": 120.0,
            "dead_level_m": 80.0,
            "max_discharge_m3_s": 22700,
            "turbine_capacity_m3_s": 2400,
            "power_mw": 1920,
            "commissioned_year": 1994,
            "coordinates": (20.8167, 105.3167),
            "catchment_area_km2": 75500,
        },
        "lai_chau": {
            "river": "Đà",
            "capacity_million_m3": 1224,
            "normal_level_m": 295.0,
            "flood_level_m": 297.5,
            "dead_level_m": 265.0,
            "max_discharge_m3_s": 15300,
            "turbine_capacity_m3_s": 1200,
            "power_mw": 1200,
            "commissioned_year": 2016,
            "coordinates": (22.3864, 103.4701),
            "catchment_area_km2": 20000,
        },
        "ban_chat": {
            "river": "Đà",
            "capacity_million_m3": 2142,
            "normal_level_m": 475.0,
            "flood_level_m": 477.3,
            "dead_level_m": 445.0,
            "max_discharge_m3_s": 9520,
            "turbine_capacity_m3_s": 800,
            "power_mw": 220,
            "commissioned_year": 2009,
            "coordinates": (21.8, 103.7),
            "catchment_area_km2": 8500,
        },
    },

    # Trạm khí tượng thủy văn chính
    "gauging_stations": {
        "lao_cai": {
            "river": "Hồng (Thao)",
            "coordinates": (22.4856, 103.9707),
            "alert_level_1_m": 79.0,
            "alert_level_2_m": 80.0,
            "alert_level_3_m": 81.0,
            "historical_max_m": 82.14,
            "historical_max_year": 1971,
            "zero_datum_m": 57.0,  # Mốc không
            "catchment_area_km2": 52600,
        },
        "yen_bai": {
            "river": "Hồng (Thao)",
            "coordinates": (21.7168, 104.8987),
            "alert_level_1_m": 29.0,
            "alert_level_2_m": 30.0,
            "alert_level_3_m": 31.0,
            "historical_max_m": 35.0,
            "historical_max_year": 1971,
            "zero_datum_m": 13.0,
            "catchment_area_km2": 61000,
        },
        "viet_tri": {
            "river": "Hồng (Hợp lưu Lô, Đà, Thao)",
            "coordinates": (21.31, 105.4019),
            "alert_level_1_m": 15.0,
            "alert_level_2_m": 16.5,
            "alert_level_3_m": 17.5,
            "historical_max_m": 20.79,
            "historical_max_year": 1971,
            "zero_datum_m": 2.0,
            "catchment_area_km2": 87800,
            "importance": "KEY_STATION",  # Trạm khóa - hợp lưu 3 sông
        },
        "son_tay": {
            "river": "Hồng",
            "coordinates": (21.1333, 105.5),
            "alert_level_1_m": 11.5,
            "alert_level_2_m": 12.5,
            "alert_level_3_m": 13.5,
            "historical_max_m": 14.13,
            "historical_max_year": 1971,
            "design_flood_level_m": 14.22,  # Mực nước thiết kế (lũ 500 năm)
            "zero_datum_m": -1.0,
            "importance": "CRITICAL",  # Quyết định vận hành đê Hà Nội
        },
        "hanoi_long_bien": {
            "river": "Hồng",
            "coordinates": (21.0285, 105.8542),
            "alert_level_1_m": 9.5,
            "alert_level_2_m": 10.5,
            "alert_level_3_m": 11.5,
            "historical_max_m": 14.13,
            "historical_max_year": 1971,
            "design_flood_level_m": 13.40,
            "zero_datum_m": -1.77,
            "importance": "CAPITAL",
        },
    },

    # Phân vùng ngập lụt chi tiết
    "flood_zones": {
        "zone_1_upper_basin": {
            "name": "Thượng nguồn (Lào Cai - Yên Bái)",
            "provinces": ["Lào Cai", "Yên Bái", "Hà Giang phần Tây"],
            "area_km2": 12500,
            "population": 1800000,
            "elevation_range_m": [100, 3143],  # Đến đỉnh Fansipan
            "flood_types": ["Lũ quét", "Sạt lở đất", "Ngập thung lũng"],
            "lead_time_hours": {
                "from_china_border": [0, 12],
                "flash_flood": [2, 6],
            },
            "flood_depth_return_periods": {
                "2_year": 0.5,
                "5_year": 1.0,
                "10_year": 1.5,
                "20_year": 2.0,
                "50_year": 2.8,
                "100_year": 3.5,
            },
            "critical_infrastructure": [
                "QL 70 (Yên Bái - Lào Cai)",
                "Đường sắt Hà Nội - Lào Cai",
                "Sa Pa tourism area",
                "Thủy điện Lai Châu, Bản Chát",
            ],
        },

        "zone_2_midstream": {
            "name": "Trung lưu (Việt Trì - Vĩnh Phúc)",
            "provinces": ["Phú Thọ", "Vĩnh Phúc", "Tuyên Quang"],
            "area_km2": 15000,
            "population": 2500000,
            "elevation_range_m": [5, 200],
            "flood_types": ["Lũ sông chính", "Ngập vùng trũng"],
            "lead_time_hours": {
                "from_china_border": [24, 48],
                "from_yen_bai": [12, 18],
            },
            "flood_depth_return_periods": {
                "2_year": 0.3,
                "5_year": 0.8,
                "10_year": 1.2,
                "20_year": 1.5,
                "50_year": 2.0,
                "100_year": 2.5,
            },
            "critical_infrastructure": [
                "TP Việt Trì",
                "Khu công nghiệp Phú Thọ",
                "Cầu Việt Trì",
                "Cảng Việt Trì",
            ],
        },

        "zone_3_hanoi": {
            "name": "Hà Nội",
            "area_km2": 3360,
            "population_total": 8000000,
            "population_at_flood_risk": 3500000,
            "elevation_range_m": [2, 20],
            "districts_high_risk": [
                "Ba Vì", "Sơn Tây", "Phúc Thọ", "Đan Phượng",
                "Hoài Đức", "Thanh Trì", "Gia Lâm", "Đông Anh",
                "Long Biên", "Hoàng Mai", "Tây Hồ", "Hà Đông",
            ],
            "flood_types": ["Ngập lụt nội đô", "Vỡ đê", "Úng ngập"],
            "lead_time_hours": {
                "from_son_tay": [6, 12],
                "from_viet_tri": [18, 24],
                "from_china_border": [48, 72],
            },
            "flood_depth_return_periods": {
                "2_year": 0.2,
                "5_year": 0.5,
                "10_year": 0.8,
                "20_year": 1.0,
                "50_year": 1.5,
                "100_year": 2.0,
                "dike_breach_scenario": 4.0,
            },
            "dike_system": {
                "huu_hong_right_bank": {
                    "length_km": 143,
                    "grade": "SPECIAL",  # Cấp đặc biệt
                    "design_flood_return_period": 500,
                    "design_level_m": 14.22,
                },
                "ta_hong_left_bank": {
                    "length_km": 128,
                    "grade": "SPECIAL",
                    "design_flood_return_period": 500,
                    "design_level_m": 14.22,
                },
            },
            "flood_diversion_areas": [
                {"name": "Vân Cốc", "capacity_million_m3": 40},
                {"name": "Tam Thanh", "capacity_million_m3": 35},
                {"name": "Lương Phú", "capacity_million_m3": 30},
            ],
            "pumping_stations": [
                {"name": "Yên Sở", "capacity_m3_s": 150},
                {"name": "Yên Xá", "capacity_m3_s": 120},
                {"name": "Thanh Liệt", "capacity_m3_s": 100},
            ],
        },

        "zone_4_delta": {
            "name": "Đồng bằng sông Hồng",
            "provinces": [
                "Hưng Yên", "Hà Nam", "Nam Định", "Thái Bình",
                "Hải Dương", "Hải Phòng", "Ninh Bình", "Quảng Ninh phần Tây",
            ],
            "area_km2": 10500,
            "population": 8500000,
            "elevation_avg_m": 1.5,  # Rất thấp!
            "elevation_range_m": [0, 10],
            "flood_types": [
                "Ngập diện rộng",
                "Xâm nhập mặn",
                "Thiệt hại nông nghiệp",
                "Kết hợp lũ + triều",
            ],
            "lead_time_hours": {
                "from_hanoi": [24, 48],
                "from_china_border": [72, 120],
            },
            "agricultural_area_km2": 7500,
            "rice_area_km2": 5000,
            "aquaculture_area_km2": 1200,
        },
    },

    # Thời gian truyền lũ
    "flood_routing_time": {
        "china_border_to_yen_bai": {"distance_km": 150, "time_hours": [18, 24]},
        "yen_bai_to_viet_tri": {"distance_km": 120, "time_hours": [15, 20]},
        "viet_tri_to_son_tay": {"distance_km": 50, "time_hours": [8, 12]},
        "son_tay_to_hanoi": {"distance_km": 40, "time_hours": [6, 10]},
        "hanoi_to_sea": {"distance_km": 120, "time_hours": [18, 24]},
        "total_china_to_hanoi": {"distance_km": 360, "time_hours": [47, 66]},
    },
}


# ============================================================================
# PHẦN 2: LƯU VỰC SÔNG MEKONG (CỬU LONG)
# ============================================================================

MEKONG_RIVER_BASIN = {
    "overview": {
        "total_length_km": 4909,  # Sông dài thứ 12 thế giới
        "total_area_km2": 795000,
        "vn_delta_area_km2": 39000,
        "annual_rainfall_mm": 1600,
        "population": 17500000,
        "average_discharge_m3_s": 15000,
    },

    # Cascade đập Trung Quốc (Sông Lan Thương - Lancang)
    "china_dams_cascade": {
        "nuozhadu": {
            "capacity_million_m3": 21700,
            "power_mw": 5850,
            "commissioned": 2014,
            "height_m": 261.5,
            "coordinates": (22.65, 100.43),
        },
        "xiaowan": {
            "capacity_million_m3": 15000,
            "power_mw": 4200,
            "commissioned": 2010,
            "height_m": 292,
            "coordinates": (24.69, 100.08),
        },
        "manwan": {
            "capacity_million_m3": 920,
            "power_mw": 1500,
            "commissioned": 1996,
            "coordinates": (24.98, 100.23),
        },
        "dachaoshan": {
            "capacity_million_m3": 940,
            "power_mw": 1350,
            "commissioned": 2003,
            "coordinates": (24.55, 100.27),
        },
        "jinghong": {
            "capacity_million_m3": 1240,
            "power_mw": 1750,
            "commissioned": 2009,
            "coordinates": (21.97, 100.80),
        },
        "gongguoqiao": {
            "capacity_million_m3": 570,
            "power_mw": 750,
            "commissioned": 2011,
            "coordinates": (23.55, 100.68),
        },
        "total_cascade": {
            "total_capacity_million_m3": 44000,  # Khổng lồ!
            "total_power_mw": 22000,
            "number_of_dams": 11,
            "impact_on_downstream": "Kiểm soát ~70% dòng chảy mùa khô",
        },
    },

    # Trạm quan trắc Mekong
    "gauging_stations": {
        "chiang_saen_thailand": {
            "river": "Mekong",
            "country": "Thailand",
            "coordinates": (20.2667, 100.0833),
            "distance_from_source_km": 1750,
            "catchment_area_km2": 189000,
            "data_source": "MRC (Mekong River Commission)",
            "average_discharge_m3_s": 2300,
        },
        "vientiane_laos": {
            "river": "Mekong",
            "country": "Laos",
            "coordinates": (17.9757, 102.6331),
            "distance_from_source_km": 2250,
            "catchment_area_km2": 299000,
            "average_discharge_m3_s": 3900,
        },
        "pakse_laos": {
            "river": "Mekong",
            "country": "Laos",
            "coordinates": (15.12, 105.78),
            "distance_from_source_km": 3320,
            "catchment_area_km2": 545000,
            "average_discharge_m3_s": 8500,
        },
        "stung_treng_cambodia": {
            "river": "Mekong",
            "country": "Cambodia",
            "coordinates": (13.5167, 106.0167),
            "distance_from_source_km": 3620,
            "catchment_area_km2": 635000,
            "average_discharge_m3_s": 11000,
        },
        "kratie_cambodia": {
            "river": "Mekong",
            "country": "Cambodia",
            "coordinates": (12.48, 106.02),
            "distance_from_source_km": 3750,
            "catchment_area_km2": 646000,
            "average_discharge_m3_s": 12500,
            "importance": "KEY_STATION",  # Trạm dự báo chính cho VN
        },
        "tan_chau_vietnam": {
            "river": "Tiền Giang",
            "country": "Vietnam",
            "coordinates": (10.8, 105.2333),
            "alert_level_1_m": 3.5,
            "alert_level_2_m": 4.0,
            "alert_level_3_m": 4.5,
            "historical_max_m": 5.2,
            "historical_max_year": 2000,
            "average_discharge_m3_s": 11500,
            "max_discharge_m3_s": 26400,
        },
        "chau_doc_vietnam": {
            "river": "Hậu Giang",
            "country": "Vietnam",
            "coordinates": (10.7, 105.1167),
            "alert_level_1_m": 3.0,
            "alert_level_2_m": 3.5,
            "alert_level_3_m": 4.0,
            "historical_max_m": 4.8,
            "historical_max_year": 2000,
            "average_discharge_m3_s": 3200,
            "max_discharge_m3_s": 8500,
        },
        "can_tho_vietnam": {
            "river": "Hậu Giang",
            "country": "Vietnam",
            "coordinates": (10.0452, 105.7469),
            "alert_level_1_m": 1.8,
            "alert_level_2_m": 2.0,
            "alert_level_3_m": 2.2,
            "historical_max_m": 2.5,
            "historical_max_year": 2000,
            "average_discharge_m3_s": 8500,
            "tidal_influence": True,
        },
    },

    # Phân vùng lũ Đồng bằng sông Cửu Long
    "flood_zones": {
        "zone_a_upper_delta": {
            "name": "Đầu nguồn đồng bằng",
            "provinces": ["An Giang", "Đồng Tháp"],
            "area_km2": 7500,
            "population": 3800000,
            "entry_points": ["Tân Châu", "Châu Đốc"],
            "characteristics": [
                "Nhận nước lũ đầu tiên",
                "Vùng trữ lũ tự nhiên - Đồng Tháp Mười",
                "Ruộng lúa nổi truyền thống",
            ],
            "lead_time_hours": {
                "from_kratie": [72, 96],
                "from_phnom_penh": [24, 48],
            },
            "flood_depth_return_periods": {
                "annual_flood": 2.0,  # Lũ hàng năm
                "2_year": 2.5,
                "5_year": 3.5,
                "10_year": 4.0,
                "20_year": 4.5,
                "2000_extreme": 5.0,  # Đại hồng thủy 2000
            },
            "dike_system": {
                "high_dikes_km2": 1400,  # Đê bao cao - 3 vụ lúa
                "semi_dikes_km2": 3200,  # Đê bao lửng - lúa nổi
                "open_fields_km2": 2900,  # Không đê - ngập tự nhiên
            },
            "economic_value": {
                "rice_production_tons_year": 4500000,
                "aquaculture_tons_year": 380000,
            },
        },

        "zone_b_central_delta": {
            "name": "Trung tâm đồng bằng",
            "provinces": ["Cần Thơ", "Vĩnh Long", "Tiền Giang", "Long An"],
            "area_km2": 8500,
            "population": 5500000,
            "characteristics": [
                "Giao thoa lũ và triều",
                "Vựa lúa chính",
                "Đô thị hóa cao",
            ],
            "lead_time_hours": {
                "from_tan_chau": [48, 96],
            },
            "flood_depth_return_periods": {
                "annual_flood": 1.0,
                "2_year": 1.5,
                "5_year": 2.0,
                "10_year": 2.5,
                "20_year": 3.0,
            },
            "tidal_range_m": [2.5, 3.8],  # Biên độ triều
            "saltwater_intrusion_risk": "HIGH",
            "critical_infrastructure": [
                "TP Cần Thơ (1.2M người)",
                "Cầu Cần Thơ, Mỹ Thuận, Rạch Miễu",
                "Cảng Cần Thơ",
                "KCN Trà Nóc",
            ],
        },

        "zone_c_coastal": {
            "name": "Vùng ven biển",
            "provinces": ["Sóc Trăng", "Bạc Liêu", "Cà Mau", "Kiên Giang"],
            "area_km2": 12000,
            "population": 4200000,
            "elevation_avg_m": 0.8,  # Cực thấp!
            "characteristics": [
                "Xâm nhập mặn nghiêm trọng",
                "Nuôi tôm",
                "Sụt lún đất",
                "Nước biển dâng",
            ],
            "subsidence_rate_mm_year": 25,  # Sụt lún 2.5cm/năm
            "sea_level_rise_mm_year": 3.3,
            "saltwater_intrusion_km_inland": {
                "normal_year": 40,
                "dry_year": 70,
                "extreme_drought_2016": 90,
            },
            "flood_risk": "Combined: flood + tide + sea level rise",
            "aquaculture_area_km2": 4200,
            "mangrove_area_km2": 350,
        },

        "zone_d_northeast": {
            "name": "Đông Bắc (Long An, Tây Ninh)",
            "provinces": ["Long An", "Tây Ninh", "Bình Dương phần Tây"],
            "area_km2": 6500,
            "population": 2800000,
            "characteristics": [
                "Vùng chuyển tiếp TP.HCM",
                "Khu công nghiệp phát triển",
                "Thoát lũ sang sông Vàm Cỏ",
            ],
            "flood_depth_return_periods": {
                "annual_flood": 1.5,
                "5_year": 2.5,
                "20_year": 3.5,
            },
        },
    },

    # Thời gian truyền lũ Mekong
    "flood_routing_time": {
        "chiang_saen_to_vientiane": {"distance_km": 600, "time_hours": [72, 96]},
        "vientiane_to_pakse": {"distance_km": 650, "time_hours": [84, 108]},
        "pakse_to_stung_treng": {"distance_km": 300, "time_hours": [36, 48]},
        "stung_treng_to_phnom_penh": {"distance_km": 220, "time_hours": [30, 40]},
        "phnom_penh_to_tan_chau": {"distance_km": 130, "time_hours": [24, 36]},
        "total_china_to_vietnam": {"distance_km": 2000, "time_hours": [252, 342]},  # ~10-14 ngày
    },
}


# ============================================================================
# PHẦN 3: CÁC SÔNG MIỀN TRUNG
# ============================================================================

CENTRAL_VIETNAM_RIVERS = {
    "vu_gia_thu_bon": {
        "name": "Hệ thống Vũ Gia - Thu Bồn",
        "provinces": ["Quảng Nam", "Đà Nẵng"],
        "total_length_km": 205,
        "basin_area_km2": 10350,
        "population_at_risk": 1500000,
        "characteristics": [
            "Lũ lên cực nhanh (6-12 giờ)",
            "Mưa lớn tập trung (có thể 500-800mm/24h)",
            "Lũ quét miền núi nghiêm trọng",
        ],
        "flood_peak_time_hours": [6, 12],
        "historical_floods": [
            {"year": 1999, "peak_discharge_m3_s": 15000, "casualties": 572},
            {"year": 2009, "peak_discharge_m3_s": 13500, "casualties": 163},
            {"year": 2017, "peak_discharge_m3_s": 12000, "casualties": 123},
            {"year": 2020, "peak_discharge_m3_s": 14500, "casualties": 136},
        ],
        "gauging_stations": {
            "nong_son": {
                "river": "Thu Bồn",
                "coordinates": (15.65, 107.91),
                "alert_level_1_m": 3.0,
                "alert_level_2_m": 4.0,
                "alert_level_3_m": 5.0,
                "historical_max_m": 7.68,
                "historical_max_year": 2009,
            },
            "thanh_my": {
                "river": "Vũ Gia",
                "coordinates": (15.87, 108.13),
                "alert_level_1_m": 2.5,
                "alert_level_2_m": 3.5,
                "alert_level_3_m": 4.5,
                "historical_max_m": 6.12,
                "historical_max_year": 2009,
            },
        },
    },

    "song_huong": {
        "name": "Sông Hương",
        "provinces": ["Thừa Thiên Huế"],
        "length_km": 104,
        "basin_area_km2": 2830,
        "population_at_risk": 800000,
        "characteristics": [
            "Lũ kép: sông + đầm phá (lagoon)",
            "Đô thị di sản Huế",
            "Mưa lớn tập trung",
        ],
        "flood_peak_time_hours": [8, 15],
        "dams": [
            {"name": "Tả Trạch", "capacity_million_m3": 31.9, "power_mw": 6.6},
            {"name": "Hương Điền", "capacity_million_m3": 33.4, "power_mw": 12},
            {"name": "Bình Điền", "capacity_million_m3": 221, "power_mw": 27},
        ],
        "gauging_stations": {
            "kim_long": {
                "river": "Hương",
                "coordinates": (16.46, 107.58),
                "alert_level_1_m": 2.0,
                "alert_level_2_m": 2.5,
                "alert_level_3_m": 3.0,
                "historical_max_m": 4.28,
                "historical_max_year": 1999,
            },
        },
    },

    "song_ca": {
        "name": "Sông Cả",
        "provinces": ["Nghệ An", "Hà Tĩnh"],
        "length_km": 531,
        "basin_area_km2": 27200,
        "population_at_risk": 2200000,
        "characteristics": [
            "Lưu vực lớn nhất Miền Trung",
            "Lũ kéo dài",
            "Thiệt hại nông nghiệp lớn",
        ],
        "flood_peak_time_hours": [18, 36],
        "gauging_stations": {
            "dua": {
                "river": "Cả",
                "coordinates": (18.67, 105.44),
                "alert_level_1_m": 10.0,
                "alert_level_2_m": 11.0,
                "alert_level_3_m": 12.0,
                "historical_max_m": 15.27,
                "historical_max_year": 2010,
            },
        },
    },

    "song_tra_khuc": {
        "name": "Sông Trà Khúc",
        "provinces": ["Quảng Ngãi"],
        "length_km": 135,
        "basin_area_km2": 3240,
        "population_at_risk": 600000,
        "characteristics": [
            "Lũ cực nhanh",
            "Sạt lở nghiêm trọng",
            "Thiệt hại cơ sở hạ tầng",
        ],
        "flood_peak_time_hours": [4, 8],
        "gauging_stations": {
            "tra_khuc": {
                "river": "Trà Khúc",
                "coordinates": (15.12, 108.78),
                "alert_level_1_m": 2.5,
                "alert_level_2_m": 3.5,
                "alert_level_3_m": 4.5,
                "historical_max_m": 6.8,
                "historical_max_year": 2009,
            },
        },
    },
}


# ============================================================================
# PHẦN 4: NGUỒN DỮ LIỆU VÀ API
# ============================================================================

DATA_SOURCES = {
    "vietnam_national": {
        "nchmf": {
            "name": "National Center for Hydro-Meteorological Forecasting",
            "website": "http://www.nchmf.gov.vn",
            "api_available": False,
            "data_types": ["Rainfall", "Water level", "Forecast"],
            "update_frequency": "6 hours",
            "coverage": "Nationwide",
        },
        "imh": {
            "name": "Institute of Meteorology and Hydrology",
            "website": "http://www.imh.ac.vn",
            "api_available": False,
            "data_types": ["Historical data", "Research"],
        },
        "monre": {
            "name": "Ministry of Natural Resources and Environment",
            "website": "http://www.monre.gov.vn",
            "api_available": False,
            "data_types": ["Water resources", "Environmental data"],
        },
    },

    "international": {
        "open_meteo": {
            "name": "Open-Meteo",
            "api_url": "https://api.open-meteo.com/v1/forecast",
            "api_available": True,
            "free": True,
            "data_types": ["Rainfall forecast", "Temperature", "Wind"],
            "forecast_days": 16,
            "spatial_resolution_km": 11,
            "update_frequency": "1 hour",
            "recommended": True,
        },
        "mrc": {
            "name": "Mekong River Commission",
            "website": "https://www.mrcmekong.org",
            "api_url": "https://portal.mrcmekong.org/api",
            "api_available": True,
            "free": True,
            "data_types": ["Mekong water level", "Discharge", "Forecast"],
            "update_frequency": "Daily",
            "coverage": "Mekong Basin only",
            "recommended": True,
        },
        "gfs_noaa": {
            "name": "NOAA Global Forecast System",
            "api_url": "https://nomads.ncep.noaa.gov/pub/data/nccf/com/gfs/prod/",
            "api_available": True,
            "free": True,
            "data_types": ["Global weather forecast"],
            "forecast_days": 16,
            "spatial_resolution_km": 25,
            "update_frequency": "6 hours",
        },
        "nasa_gpm": {
            "name": "NASA GPM (Global Precipitation Measurement)",
            "api_url": "https://gpm.nasa.gov/data/imerg",
            "api_available": True,
            "data_types": ["Satellite rainfall estimates"],
            "spatial_resolution_km": 10,
            "temporal_resolution": "30 minutes",
            "delay_hours": 4,  # Near real-time
        },
    },
}


# ============================================================================
# PHẦN 5: CÔNG THỨC TÍNH TOÁN CHUẨN
# ============================================================================

HYDROLOGICAL_FORMULAS = {
    "thiessen_polygon": {
        "description": "Tính lượng mưa trung bình lưu vực theo Thiessen",
        "formula": "P_basin = Σ(Pi × Ai) / Σ(Ai)",
        "variables": {
            "P_basin": "Lượng mưa trung bình lưu vực (mm)",
            "Pi": "Lượng mưa tại trạm i (mm)",
            "Ai": "Diện tích ảnh hưởng của trạm i (km²)",
        },
        "application": "Phù hợp cho lưu vực lớn, phân bố trạm không đều",
    },

    "scs_cn_method": {
        "description": "Phương pháp SCS Curve Number",
        "formula": "Q = ((P - Ia)²) / (P - Ia + S)",
        "variables": {
            "Q": "Lượng dòng chảy (mm)",
            "P": "Lượng mưa (mm)",
            "Ia": "Initial abstraction = 0.2S (mm)",
            "S": "Potential maximum retention = (1000/CN) - 10 (mm)",
            "CN": "Curve Number (40-100)",
        },
        "cn_values": {
            "forest_good": 30,
            "forest_fair": 55,
            "pasture_good": 61,
            "residential_low": 77,
            "residential_medium": 85,
            "residential_high": 92,
            "paved_roads": 98,
            "water_bodies": 100,
        },
        "application": "Ước tính dòng chảy từ mưa",
    },

    "manning_equation": {
        "description": "Công thức Manning cho dòng chảy kênh hở",
        "formula": "V = (1/n) × R^(2/3) × S^(1/2)",
        "variables": {
            "V": "Vận tốc dòng chảy (m/s)",
            "n": "Hệ số nhám Manning",
            "R": "Bán kính thủy lực (m)",
            "S": "Độ dốc đáy sông",
        },
        "manning_n_values": {
            "natural_clean": 0.030,
            "natural_weeds": 0.035,
            "natural_dense_weeds": 0.050,
            "mountain_stream": 0.040,
            "flood_plain": 0.060,
            "concrete_channel": 0.013,
        },
        "application": "Tính vận tốc và lưu lượng dòng chảy",
    },

    "rational_method": {
        "description": "Phương pháp Hữu tỷ (Rational Method)",
        "formula": "Q = 0.278 × C × i × A",
        "variables": {
            "Q": "Lưu lượng đỉnh (m³/s)",
            "C": "Hệ số dòng chảy (0-1)",
            "i": "Cường độ mưa (mm/h)",
            "A": "Diện tích lưu vực (km²)",
        },
        "runoff_coefficients": {
            "forest": 0.15,
            "pasture": 0.25,
            "residential_low": 0.40,
            "residential_medium": 0.60,
            "residential_high": 0.75,
            "industrial": 0.80,
            "asphalt": 0.90,
        },
        "limitations": "Chỉ áp dụng cho lưu vực < 20 km²",
    },

    "muskingum_routing": {
        "description": "Phương pháp Muskingum truyền lũ",
        "formula": "O[t+1] = C0×I[t+1] + C1×I[t] + C2×O[t]",
        "variables": {
            "O": "Lưu lượng ra (m³/s)",
            "I": "Lưu lượng vào (m³/s)",
            "K": "Thời gian truyền (giờ)",
            "X": "Hệ số trọng lượng (0-0.5)",
            "dt": "Bước thời gian (giờ)",
        },
        "typical_X_values": {
            "natural_stream": 0.25,
            "reservoir": 0.0,
        },
        "application": "Dự báo lưu lượng hạ lưu từ thượng nguồn",
    },

    "gumbel_distribution": {
        "description": "Phân phối Gumbel cho tần suất lũ",
        "formula": "T = 1 / (1 - F(x))",
        "variables": {
            "T": "Chu kỳ lặp lại (năm)",
            "F(x)": "Hàm phân phối tích lũy",
            "x": "Lưu lượng/mực nước",
        },
        "application": "Tính tần suất xuất hiện lũ",
    },
}


# ============================================================================
# PHẦN 6: NGƯỠNG CẢNH BÁO CHUẨN
# ============================================================================

FLOOD_THRESHOLDS_STANDARD = {
    "HONG": {
        "safe": {"daily_rainfall_mm": [0, 50], "accumulated_3d_mm": [0, 150]},
        "watch": {"daily_rainfall_mm": [50, 100], "accumulated_3d_mm": [150, 250]},
        "warning": {"daily_rainfall_mm": [100, 150], "accumulated_3d_mm": [250, 400]},
        "danger": {"daily_rainfall_mm": [150, 999], "accumulated_3d_mm": [400, 999]},
        "water_level_son_tay": {
            "normal": 11.0,
            "alert_1": 11.5,
            "alert_2": 12.5,
            "alert_3": 13.5,
            "design_level": 14.22,
        },
    },

    "MEKONG": {
        "safe": {"daily_rainfall_mm": [0, 40], "accumulated_3d_mm": [0, 120]},
        "watch": {"daily_rainfall_mm": [40, 80], "accumulated_3d_mm": [120, 200]},
        "warning": {"daily_rainfall_mm": [80, 120], "accumulated_3d_mm": [200, 350]},
        "danger": {"daily_rainfall_mm": [120, 999], "accumulated_3d_mm": [350, 999]},
        "water_level_tan_chau": {
            "normal": 3.0,
            "alert_1": 3.5,
            "alert_2": 4.0,
            "alert_3": 4.5,
        },
    },

    "CENTRAL": {
        "safe": {"daily_rainfall_mm": [0, 80], "accumulated_3d_mm": [0, 200]},
        "watch": {"daily_rainfall_mm": [80, 120], "accumulated_3d_mm": [200, 300]},
        "warning": {"daily_rainfall_mm": [120, 200], "accumulated_3d_mm": [300, 500]},
        "danger": {"daily_rainfall_mm": [200, 999], "accumulated_3d_mm": [500, 999]},
        "flash_flood_criteria": {
            "rainfall_intensity_mm_h": 30,  # >30mm/h = nguy cơ lũ quét
            "duration_hours": 3,
        },
    },
}


# Export tất cả
__all__ = [
    'HONG_RIVER_BASIN',
    'MEKONG_RIVER_BASIN',
    'CENTRAL_VIETNAM_RIVERS',
    'DATA_SOURCES',
    'HYDROLOGICAL_FORMULAS',
    'FLOOD_THRESHOLDS_STANDARD',
]
