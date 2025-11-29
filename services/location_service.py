#!/usr/bin/env python3
"""
Location Service - Business logic for rivers, flood zones, locations
"""
from typing import Dict, List, Optional

from data import VIETNAM_RIVERS
from weather_api import VIETNAM_LOCATIONS


class LocationService:
    """Service for location-related data (rivers, flood zones, provinces)"""

    def get_all_rivers(self) -> Dict:
        """Get all rivers from all basins"""
        all_rivers = []
        for basin, rivers in VIETNAM_RIVERS.items():
            for river in rivers:
                river_info = river.copy()
                river_info["basin"] = basin
                all_rivers.append(river_info)

        return {
            "total": len(all_rivers),
            "rivers": all_rivers,
            "basins": list(VIETNAM_RIVERS.keys())
        }

    def get_rivers_by_basin(self, basin: str) -> Optional[Dict]:
        """Get rivers for a specific basin"""
        basin_upper = basin.upper()
        if basin_upper not in VIETNAM_RIVERS:
            return None

        return {
            "basin": basin_upper,
            "total": len(VIETNAM_RIVERS[basin_upper]),
            "rivers": VIETNAM_RIVERS[basin_upper]
        }

    def get_all_flood_zones(self) -> Dict:
        """Get all potential flood zones"""
        all_zones = []
        for basin, rivers in VIETNAM_RIVERS.items():
            for river in rivers:
                for zone in river.get("flood_prone_areas", []):
                    zone_info = {
                        "basin": basin,
                        "river": river["name"],
                        "province": zone["name"],
                        "districts": zone["districts"],
                        "risk": zone["risk"],
                        "alert_levels": river.get("alert_levels", {})
                    }
                    all_zones.append(zone_info)

        # Sort by risk level
        risk_order = {"Rất cao": 0, "Cao": 1, "Trung bình": 2, "Thấp": 3}
        all_zones.sort(key=lambda x: risk_order.get(x["risk"], 4))

        return {
            "total": len(all_zones),
            "zones": all_zones,
            "risk_summary": {
                "Rất cao": len([z for z in all_zones if z["risk"] == "Rất cao"]),
                "Cao": len([z for z in all_zones if z["risk"] == "Cao"]),
                "Trung bình": len([z for z in all_zones if z["risk"] == "Trung bình"]),
                "Thấp": len([z for z in all_zones if z["risk"] == "Thấp"])
            }
        }

    def get_flood_zones_by_basin(self, basin: str) -> Optional[Dict]:
        """Get flood zones for a specific basin"""
        basin_upper = basin.upper()
        if basin_upper not in VIETNAM_RIVERS:
            return None

        zones = []
        for river in VIETNAM_RIVERS[basin_upper]:
            for zone in river.get("flood_prone_areas", []):
                zone_info = {
                    "basin": basin_upper,
                    "river": river["name"],
                    "province": zone["name"],
                    "districts": zone["districts"],
                    "risk": zone["risk"],
                    "alert_levels": river.get("alert_levels", {})
                }
                zones.append(zone_info)

        risk_order = {"Rất cao": 0, "Cao": 1, "Trung bình": 2, "Thấp": 3}
        zones.sort(key=lambda x: risk_order.get(x["risk"], 4))

        return {
            "basin": basin_upper,
            "total": len(zones),
            "zones": zones
        }

    def get_all_locations(self) -> Dict:
        """Get all weather locations grouped by region"""
        locations_by_region = {
            "north": [],
            "central": [],
            "highland": [],
            "south": []
        }

        for code, info in VIETNAM_LOCATIONS.items():
            region = info.get("region", "other")
            if region in locations_by_region:
                locations_by_region[region].append({
                    "code": code,
                    "name": info["name"],
                    "lat": info["lat"],
                    "lon": info["lon"]
                })

        return {
            "total": len(VIETNAM_LOCATIONS),
            "by_region": locations_by_region,
            "regions": {
                "north": "Miền Bắc",
                "central": "Miền Trung",
                "highland": "Tây Nguyên",
                "south": "Miền Nam"
            }
        }

    def get_location_by_code(self, code: str) -> Optional[Dict]:
        """Get a specific location by code"""
        loc_info = VIETNAM_LOCATIONS.get(code)
        if not loc_info:
            return None

        return {
            "code": code,
            "name": loc_info["name"],
            "lat": loc_info["lat"],
            "lon": loc_info["lon"],
            "region": loc_info.get("region", "other")
        }

    def get_locations_by_region(self, region: str) -> Optional[Dict]:
        """Get locations for a specific region"""
        valid_regions = ["north", "central", "highland", "south"]
        region_lower = region.lower()
        if region_lower not in valid_regions:
            return None

        locations = []
        for code, info in VIETNAM_LOCATIONS.items():
            if info.get("region") == region_lower:
                locations.append({
                    "code": code,
                    "name": info["name"],
                    "lat": info["lat"],
                    "lon": info["lon"]
                })

        region_names = {
            "north": "Miền Bắc",
            "central": "Miền Trung",
            "highland": "Tây Nguyên",
            "south": "Miền Nam"
        }

        return {
            "region": region_lower,
            "region_name": region_names.get(region_lower, region_lower),
            "total": len(locations),
            "locations": locations
        }
