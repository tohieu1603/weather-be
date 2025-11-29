#!/usr/bin/env python3
"""
Vietnam geographic and infrastructure constants
"""

# Map basin codes to display names
BASIN_NAMES = {
    "HONG": "Sông Hồng",
    "MEKONG": "Sông Mekong",
    "DONGNAI": "Sông Đồng Nai",
    "CENTRAL": "Miền Trung"
}

BASIN_ID_MAP = {"HONG": 1, "MEKONG": 2, "DONGNAI": 3, "CENTRAL": 4}

# Major monitoring stations for each basin
MAJOR_STATIONS = {
    "HONG": [
        {"name": "Hà Nội", "lat": 21.0285, "lon": 105.8542},
        {"name": "Sơn Tây", "lat": 21.1333, "lon": 105.5000},
        {"name": "Việt Trì", "lat": 21.3100, "lon": 105.4019},
        {"name": "Phú Thọ", "lat": 21.4200, "lon": 105.2000},
        {"name": "Hải Phòng", "lat": 20.8449, "lon": 106.6881},
    ],
    "MEKONG": [
        {"name": "Cần Thơ", "lat": 10.0452, "lon": 105.7469},
        {"name": "Tân Châu", "lat": 10.8000, "lon": 105.2333},
        {"name": "Châu Đốc", "lat": 10.7000, "lon": 105.1167},
        {"name": "Long An", "lat": 10.5333, "lon": 106.4167},
        {"name": "An Giang", "lat": 10.5216, "lon": 105.1258},
    ],
    "DONGNAI": [
        {"name": "TP Hồ Chí Minh", "lat": 10.7769, "lon": 106.7009},
        {"name": "Đồng Nai", "lat": 10.9574, "lon": 106.8426},
        {"name": "Bình Dương", "lat": 11.3254, "lon": 106.4770},
        {"name": "Bà Rịa-Vũng Tàu", "lat": 10.5417, "lon": 107.2429},
    ],
    "CENTRAL": [
        {"name": "Đà Nẵng", "lat": 16.0544, "lon": 108.2022},
        {"name": "Huế", "lat": 16.4637, "lon": 107.5909},
        {"name": "Quảng Nam", "lat": 15.5393, "lon": 108.0192},
        {"name": "Quảng Ngãi", "lat": 15.1214, "lon": 108.8044},
        {"name": "Nghệ An", "lat": 18.6793, "lon": 105.6811},
    ],
}

# Vietnam Dams Data
VIETNAM_DAMS = {
    "HONG": [
        {
            "id": "hoa_binh",
            "name": "Thủy điện Hòa Bình",
            "river": "Sông Đà",
            "province": "Hòa Bình",
            "capacity_mw": 1920,
            "reservoir_volume_million_m3": 9450,
            "max_discharge_m3s": 27000,
            "normal_level_m": 117,
            "flood_level_m": 120,
            "dead_level_m": 80,
            "spillway_gates": 12,
            "coordinates": {"lat": 20.8167, "lon": 105.3167},
            "downstream_areas": ["Thành phố Hòa Bình", "Hà Nội (Ba Vì, Đan Phượng)", "Hà Nam", "Nam Định"],
            "affected_rivers": ["Sông Đà", "Sông Hồng"],
            "warning_time_hours": 6,
            "description": "Đập thủy điện lớn nhất Đông Nam Á khi hoàn thành (1994)"
        },
        {
            "id": "son_la",
            "name": "Thủy điện Sơn La",
            "river": "Sông Đà",
            "province": "Sơn La",
            "capacity_mw": 2400,
            "reservoir_volume_million_m3": 9260,
            "max_discharge_m3s": 35640,
            "normal_level_m": 215,
            "flood_level_m": 217.83,
            "dead_level_m": 175,
            "spillway_gates": 12,
            "coordinates": {"lat": 21.2833, "lon": 103.9500},
            "downstream_areas": ["Thành phố Sơn La", "Hòa Bình", "Hà Nội", "Phú Thọ"],
            "affected_rivers": ["Sông Đà"],
            "warning_time_hours": 8,
            "description": "Nhà máy thủy điện lớn nhất Việt Nam và Đông Nam Á"
        },
        {
            "id": "lai_chau",
            "name": "Thủy điện Lai Châu",
            "river": "Sông Đà",
            "province": "Lai Châu",
            "capacity_mw": 1200,
            "reservoir_volume_million_m3": 1215,
            "max_discharge_m3s": 15300,
            "normal_level_m": 295,
            "flood_level_m": 297,
            "dead_level_m": 270,
            "spillway_gates": 8,
            "coordinates": {"lat": 22.0500, "lon": 103.1833},
            "downstream_areas": ["Thành phố Lai Châu", "Điện Biên", "Sơn La"],
            "affected_rivers": ["Sông Đà"],
            "warning_time_hours": 10,
            "description": "Bậc thang thủy điện cao nhất trên sông Đà"
        },
        {
            "id": "thac_ba",
            "name": "Thủy điện Thác Bà",
            "river": "Sông Chảy",
            "province": "Yên Bái",
            "capacity_mw": 120,
            "reservoir_volume_million_m3": 2940,
            "max_discharge_m3s": 3500,
            "normal_level_m": 58,
            "flood_level_m": 60,
            "dead_level_m": 46,
            "spillway_gates": 6,
            "coordinates": {"lat": 21.8333, "lon": 104.8333},
            "downstream_areas": ["Yên Bái", "Phú Thọ", "Vĩnh Phúc"],
            "affected_rivers": ["Sông Chảy", "Sông Lô"],
            "warning_time_hours": 5,
            "description": "Nhà máy thủy điện đầu tiên của Việt Nam (1971)"
        },
        {
            "id": "tuyen_quang",
            "name": "Thủy điện Tuyên Quang",
            "river": "Sông Gâm",
            "province": "Tuyên Quang",
            "capacity_mw": 342,
            "reservoir_volume_million_m3": 2260,
            "max_discharge_m3s": 5000,
            "normal_level_m": 120,
            "flood_level_m": 122,
            "dead_level_m": 90,
            "spillway_gates": 5,
            "coordinates": {"lat": 22.1167, "lon": 105.2167},
            "downstream_areas": ["Tuyên Quang", "Hà Giang"],
            "affected_rivers": ["Sông Gâm", "Sông Lô"],
            "warning_time_hours": 6,
            "description": "Thủy điện lớn trên sông Gâm"
        },
    ],
    "CENTRAL": [
        {
            "id": "a_vuong",
            "name": "Thủy điện A Vương",
            "river": "Sông Vu Gia",
            "province": "Quảng Nam",
            "capacity_mw": 210,
            "reservoir_volume_million_m3": 343,
            "max_discharge_m3s": 3500,
            "normal_level_m": 380,
            "flood_level_m": 382,
            "dead_level_m": 340,
            "spillway_gates": 4,
            "coordinates": {"lat": 15.8500, "lon": 107.5000},
            "downstream_areas": ["Đại Lộc", "Điện Bàn", "Hội An", "Đà Nẵng"],
            "affected_rivers": ["Sông Vu Gia", "Sông Thu Bồn"],
            "warning_time_hours": 4,
            "description": "Thủy điện lớn nhất miền Trung"
        },
        {
            "id": "song_tranh_2",
            "name": "Thủy điện Sông Tranh 2",
            "river": "Sông Tranh",
            "province": "Quảng Nam",
            "capacity_mw": 190,
            "reservoir_volume_million_m3": 730,
            "max_discharge_m3s": 6540,
            "normal_level_m": 175,
            "flood_level_m": 178,
            "dead_level_m": 140,
            "spillway_gates": 6,
            "coordinates": {"lat": 15.3500, "lon": 108.0500},
            "downstream_areas": ["Bắc Trà My", "Tiên Phước", "Núi Thành"],
            "affected_rivers": ["Sông Tranh", "Sông Thu Bồn"],
            "warning_time_hours": 3,
            "description": "Thủy điện trên sông Tranh"
        },
        {
            "id": "binh_dien",
            "name": "Thủy điện Bình Điền",
            "river": "Sông Hương",
            "province": "Thừa Thiên Huế",
            "capacity_mw": 44,
            "reservoir_volume_million_m3": 423,
            "max_discharge_m3s": 2800,
            "normal_level_m": 85,
            "flood_level_m": 88,
            "dead_level_m": 60,
            "spillway_gates": 4,
            "coordinates": {"lat": 16.3000, "lon": 107.4000},
            "downstream_areas": ["TP Huế", "Hương Trà", "Phú Vang"],
            "affected_rivers": ["Sông Hương"],
            "warning_time_hours": 3,
            "description": "Thủy điện trên sông Hương"
        },
    ],
    "DONGNAI": [
        {
            "id": "tri_an",
            "name": "Thủy điện Trị An",
            "river": "Sông Đồng Nai",
            "province": "Đồng Nai",
            "capacity_mw": 400,
            "reservoir_volume_million_m3": 2765,
            "max_discharge_m3s": 2800,
            "normal_level_m": 62,
            "flood_level_m": 63.9,
            "dead_level_m": 50,
            "spillway_gates": 8,
            "coordinates": {"lat": 11.0833, "lon": 107.0333},
            "downstream_areas": ["Biên Hòa", "TP.HCM (Thủ Đức, Quận 9)", "Long Thành"],
            "affected_rivers": ["Sông Đồng Nai"],
            "warning_time_hours": 6,
            "description": "Thủy điện lớn nhất miền Nam"
        },
        {
            "id": "thac_mo",
            "name": "Thủy điện Thác Mơ",
            "river": "Sông Bé",
            "province": "Bình Phước",
            "capacity_mw": 150,
            "reservoir_volume_million_m3": 1360,
            "max_discharge_m3s": 3000,
            "normal_level_m": 218,
            "flood_level_m": 220,
            "dead_level_m": 195,
            "spillway_gates": 5,
            "coordinates": {"lat": 11.8167, "lon": 107.0167},
            "downstream_areas": ["Phước Long", "Bù Đăng", "Đồng Xoài"],
            "affected_rivers": ["Sông Bé"],
            "warning_time_hours": 5,
            "description": "Thủy điện lớn trên sông Bé"
        },
        {
            "id": "can_don",
            "name": "Thủy điện Cần Đơn",
            "river": "Sông Bé",
            "province": "Bình Phước",
            "capacity_mw": 78,
            "reservoir_volume_million_m3": 165,
            "max_discharge_m3s": 1500,
            "normal_level_m": 115,
            "flood_level_m": 117,
            "dead_level_m": 105,
            "spillway_gates": 4,
            "coordinates": {"lat": 11.6500, "lon": 106.8500},
            "downstream_areas": ["Phú Giáo", "Bến Cát", "Dĩ An"],
            "affected_rivers": ["Sông Bé"],
            "warning_time_hours": 4,
            "description": "Thủy điện trên sông Bé"
        },
        {
            "id": "dau_tieng",
            "name": "Hồ Dầu Tiếng",
            "river": "Sông Sài Gòn",
            "province": "Tây Ninh",
            "capacity_mw": 0,
            "reservoir_volume_million_m3": 1580,
            "max_discharge_m3s": 2700,
            "normal_level_m": 24.4,
            "flood_level_m": 25.1,
            "dead_level_m": 17,
            "spillway_gates": 6,
            "coordinates": {"lat": 11.3333, "lon": 106.3333},
            "downstream_areas": ["Củ Chi", "Hóc Môn", "Bình Chánh", "TP.HCM"],
            "affected_rivers": ["Sông Sài Gòn"],
            "warning_time_hours": 8,
            "description": "Hồ chứa nước lớn nhất Đông Nam Bộ (công trình thủy lợi)"
        },
    ],
    "MEKONG": [
        {
            "id": "yaly",
            "name": "Thủy điện Yaly",
            "river": "Sông Sê San",
            "province": "Gia Lai",
            "capacity_mw": 720,
            "reservoir_volume_million_m3": 1037,
            "max_discharge_m3s": 6100,
            "normal_level_m": 515,
            "flood_level_m": 517,
            "dead_level_m": 490,
            "spillway_gates": 6,
            "coordinates": {"lat": 14.2000, "lon": 107.8167},
            "downstream_areas": ["Ia Grai", "Chư Păh", "Đức Cơ", "Kon Tum"],
            "affected_rivers": ["Sông Sê San"],
            "warning_time_hours": 6,
            "description": "Thủy điện lớn nhất Tây Nguyên"
        },
        {
            "id": "sesan_4",
            "name": "Thủy điện Sê San 4",
            "river": "Sông Sê San",
            "province": "Gia Lai",
            "capacity_mw": 360,
            "reservoir_volume_million_m3": 264,
            "max_discharge_m3s": 5000,
            "normal_level_m": 215,
            "flood_level_m": 217,
            "dead_level_m": 210,
            "spillway_gates": 5,
            "coordinates": {"lat": 13.9500, "lon": 107.6833},
            "downstream_areas": ["Ia Grai", "Chư Păh"],
            "affected_rivers": ["Sông Sê San"],
            "warning_time_hours": 4,
            "description": "Thủy điện bậc thang trên sông Sê San"
        },
        {
            "id": "buon_kuop",
            "name": "Thủy điện Buôn Kuốp",
            "river": "Sông Srêpốk",
            "province": "Đắk Lắk",
            "capacity_mw": 280,
            "reservoir_volume_million_m3": 200,
            "max_discharge_m3s": 3500,
            "normal_level_m": 412,
            "flood_level_m": 414,
            "dead_level_m": 395,
            "spillway_gates": 4,
            "coordinates": {"lat": 12.7500, "lon": 108.0500},
            "downstream_areas": ["Buôn Đôn", "Ea Súp", "Krông Ana"],
            "affected_rivers": ["Sông Srêpốk"],
            "warning_time_hours": 5,
            "description": "Thủy điện lớn trên sông Srêpốk"
        },
        {
            "id": "srepok_3",
            "name": "Thủy điện Srêpốk 3",
            "river": "Sông Srêpốk",
            "province": "Đắk Lắk",
            "capacity_mw": 220,
            "reservoir_volume_million_m3": 370,
            "max_discharge_m3s": 3000,
            "normal_level_m": 272,
            "flood_level_m": 274,
            "dead_level_m": 255,
            "spillway_gates": 4,
            "coordinates": {"lat": 12.5000, "lon": 107.8333},
            "downstream_areas": ["Buôn Đôn", "Cư M'gar"],
            "affected_rivers": ["Sông Srêpốk"],
            "warning_time_hours": 4,
            "description": "Thủy điện bậc thang trên sông Srêpốk"
        },
    ],
}

# Vietnam Rivers Data
VIETNAM_RIVERS = {
    "HONG": [
        {
            "name": "Sông Hồng",
            "length_km": 1149,
            "basin_area_km2": 155000,
            "provinces": ["Lào Cai", "Yên Bái", "Phú Thọ", "Vĩnh Phúc", "Hà Nội", "Hưng Yên", "Hà Nam", "Nam Định", "Thái Bình"],
            "flood_prone_areas": [
                {"name": "Hà Nội", "districts": ["Ba Vì", "Đan Phượng", "Phúc Thọ", "Thường Tín"], "risk": "Cao"},
                {"name": "Nam Định", "districts": ["Mỹ Lộc", "Vụ Bản", "Ý Yên", "Nam Trực"], "risk": "Cao"},
                {"name": "Thái Bình", "districts": ["Vũ Thư", "Kiến Xương", "Tiền Hải"], "risk": "Trung bình"},
            ],
            "alert_levels": {"level_1": 9.5, "level_2": 10.5, "level_3": 11.5}
        },
        {
            "name": "Sông Đà",
            "length_km": 527,
            "basin_area_km2": 52900,
            "provinces": ["Lai Châu", "Điện Biên", "Sơn La", "Hòa Bình", "Phú Thọ"],
            "flood_prone_areas": [
                {"name": "Sơn La", "districts": ["Mường La", "Quỳnh Nhai", "TP Sơn La"], "risk": "Cao"},
                {"name": "Hòa Bình", "districts": ["Mai Châu", "Đà Bắc", "TP Hòa Bình"], "risk": "Cao"},
            ],
            "alert_levels": {"level_1": 15.0, "level_2": 17.0, "level_3": 19.0}
        },
        {
            "name": "Sông Lô",
            "length_km": 470,
            "basin_area_km2": 39000,
            "provinces": ["Hà Giang", "Tuyên Quang", "Phú Thọ", "Vĩnh Phúc"],
            "flood_prone_areas": [
                {"name": "Tuyên Quang", "districts": ["Chiêm Hóa", "Yên Sơn", "TP Tuyên Quang"], "risk": "Trung bình"},
                {"name": "Phú Thọ", "districts": ["Đoan Hùng", "Phù Ninh"], "risk": "Trung bình"},
            ],
            "alert_levels": {"level_1": 17.0, "level_2": 19.0, "level_3": 21.0}
        },
    ],
    "CENTRAL": [
        {
            "name": "Sông Thu Bồn",
            "length_km": 205,
            "basin_area_km2": 10350,
            "provinces": ["Quảng Nam"],
            "flood_prone_areas": [
                {"name": "Quảng Nam", "districts": ["Đại Lộc", "Duy Xuyên", "Điện Bàn", "Hội An"], "risk": "Rất cao"},
            ],
            "alert_levels": {"level_1": 5.0, "level_2": 7.0, "level_3": 9.0}
        },
        {
            "name": "Sông Vu Gia",
            "length_km": 204,
            "basin_area_km2": 5180,
            "provinces": ["Quảng Nam", "Đà Nẵng"],
            "flood_prone_areas": [
                {"name": "Đà Nẵng", "districts": ["Hòa Vang", "Cẩm Lệ", "Liên Chiểu"], "risk": "Cao"},
                {"name": "Quảng Nam", "districts": ["Đại Lộc", "Điện Bàn"], "risk": "Cao"},
            ],
            "alert_levels": {"level_1": 4.5, "level_2": 6.0, "level_3": 8.0}
        },
        {
            "name": "Sông Hương",
            "length_km": 104,
            "basin_area_km2": 2830,
            "provinces": ["Thừa Thiên Huế"],
            "flood_prone_areas": [
                {"name": "Thừa Thiên Huế", "districts": ["TP Huế", "Hương Trà", "Phú Vang", "Quảng Điền"], "risk": "Rất cao"},
            ],
            "alert_levels": {"level_1": 2.0, "level_2": 3.0, "level_3": 4.0}
        },
        {
            "name": "Sông Cả (Sông Lam)",
            "length_km": 531,
            "basin_area_km2": 27200,
            "provinces": ["Nghệ An", "Hà Tĩnh"],
            "flood_prone_areas": [
                {"name": "Nghệ An", "districts": ["TP Vinh", "Hưng Nguyên", "Nam Đàn", "Thanh Chương"], "risk": "Cao"},
                {"name": "Hà Tĩnh", "districts": ["Đức Thọ", "Hương Sơn"], "risk": "Trung bình"},
            ],
            "alert_levels": {"level_1": 4.0, "level_2": 6.0, "level_3": 8.0}
        },
        {
            "name": "Sông Mã",
            "length_km": 512,
            "basin_area_km2": 28400,
            "provinces": ["Thanh Hóa", "Sơn La"],
            "flood_prone_areas": [
                {"name": "Thanh Hóa", "districts": ["TP Thanh Hóa", "Thiệu Hóa", "Yên Định", "Vĩnh Lộc"], "risk": "Cao"},
            ],
            "alert_levels": {"level_1": 7.0, "level_2": 9.0, "level_3": 11.0}
        },
    ],
    "DONGNAI": [
        {
            "name": "Sông Đồng Nai",
            "length_km": 586,
            "basin_area_km2": 38600,
            "provinces": ["Lâm Đồng", "Đắk Nông", "Bình Phước", "Đồng Nai", "Bình Dương", "TP.HCM"],
            "flood_prone_areas": [
                {"name": "Đồng Nai", "districts": ["Biên Hòa", "Vĩnh Cửu", "Trảng Bom", "Long Thành"], "risk": "Cao"},
                {"name": "TP.HCM", "districts": ["Thủ Đức", "Quận 9", "Quận 2"], "risk": "Trung bình"},
            ],
            "alert_levels": {"level_1": 2.5, "level_2": 3.5, "level_3": 4.5}
        },
        {
            "name": "Sông Sài Gòn",
            "length_km": 256,
            "basin_area_km2": 4717,
            "provinces": ["Tây Ninh", "Bình Dương", "Bình Phước", "TP.HCM"],
            "flood_prone_areas": [
                {"name": "TP.HCM", "districts": ["Củ Chi", "Hóc Môn", "Bình Chánh", "Quận 12"], "risk": "Cao"},
                {"name": "Bình Dương", "districts": ["Dĩ An", "Thuận An", "Tân Uyên"], "risk": "Trung bình"},
            ],
            "alert_levels": {"level_1": 1.4, "level_2": 1.6, "level_3": 1.8}
        },
        {
            "name": "Sông Bé",
            "length_km": 350,
            "basin_area_km2": 7650,
            "provinces": ["Bình Phước", "Bình Dương", "Đồng Nai"],
            "flood_prone_areas": [
                {"name": "Bình Phước", "districts": ["Phước Long", "Bù Đăng", "Đồng Phú"], "risk": "Trung bình"},
                {"name": "Bình Dương", "districts": ["Phú Giáo", "Bến Cát"], "risk": "Trung bình"},
            ],
            "alert_levels": {"level_1": 3.0, "level_2": 4.5, "level_3": 6.0}
        },
    ],
    "MEKONG": [
        {
            "name": "Sông Mekong (Cửu Long)",
            "length_km": 4350,
            "basin_area_km2": 795000,
            "provinces": ["An Giang", "Đồng Tháp", "Vĩnh Long", "Cần Thơ", "Hậu Giang", "Sóc Trăng", "Trà Vinh", "Bến Tre", "Tiền Giang", "Long An"],
            "flood_prone_areas": [
                {"name": "An Giang", "districts": ["Tân Châu", "An Phú", "Châu Phú", "Châu Đốc"], "risk": "Rất cao"},
                {"name": "Đồng Tháp", "districts": ["Hồng Ngự", "Tân Hồng", "Tam Nông", "Thanh Bình"], "risk": "Rất cao"},
                {"name": "Long An", "districts": ["Tân Hưng", "Vĩnh Hưng", "Mộc Hóa", "Tân Thạnh"], "risk": "Cao"},
            ],
            "alert_levels": {"level_1": 3.5, "level_2": 4.0, "level_3": 4.5}
        },
        {
            "name": "Sông Tiền",
            "length_km": 234,
            "basin_area_km2": 15000,
            "provinces": ["An Giang", "Đồng Tháp", "Tiền Giang", "Vĩnh Long", "Bến Tre"],
            "flood_prone_areas": [
                {"name": "Tiền Giang", "districts": ["Cai Lậy", "Cái Bè", "Châu Thành"], "risk": "Cao"},
                {"name": "Bến Tre", "districts": ["Châu Thành", "Chợ Lách", "Mỏ Cày"], "risk": "Cao"},
            ],
            "alert_levels": {"level_1": 2.8, "level_2": 3.5, "level_3": 4.2}
        },
        {
            "name": "Sông Hậu",
            "length_km": 200,
            "basin_area_km2": 16000,
            "provinces": ["An Giang", "Cần Thơ", "Hậu Giang", "Sóc Trăng", "Trà Vinh"],
            "flood_prone_areas": [
                {"name": "Cần Thơ", "districts": ["Thốt Nốt", "Vĩnh Thạnh", "Cờ Đỏ", "Phong Điền"], "risk": "Cao"},
                {"name": "Sóc Trăng", "districts": ["Kế Sách", "Long Phú", "Cù Lao Dung"], "risk": "Cao"},
            ],
            "alert_levels": {"level_1": 2.5, "level_2": 3.2, "level_3": 4.0}
        },
        {
            "name": "Sông Sê San",
            "length_km": 237,
            "basin_area_km2": 11450,
            "provinces": ["Kon Tum", "Gia Lai"],
            "flood_prone_areas": [
                {"name": "Gia Lai", "districts": ["Ia Grai", "Chư Păh", "Đức Cơ"], "risk": "Trung bình"},
                {"name": "Kon Tum", "districts": ["Sa Thầy", "Ngọc Hồi"], "risk": "Trung bình"},
            ],
            "alert_levels": {"level_1": 380.0, "level_2": 400.0, "level_3": 420.0}
        },
        {
            "name": "Sông Srêpốk",
            "length_km": 315,
            "basin_area_km2": 12000,
            "provinces": ["Đắk Lắk", "Đắk Nông"],
            "flood_prone_areas": [
                {"name": "Đắk Lắk", "districts": ["Buôn Đôn", "Ea Súp", "Krông Ana"], "risk": "Trung bình"},
            ],
            "alert_levels": {"level_1": 400.0, "level_2": 420.0, "level_3": 440.0}
        },
    ]
}
