#!/usr/bin/env python3
"""
AI Analysis Service - Business logic for DeepSeek AI analysis

Support 2 modes:
1. Synchronous (blocking): analyze_forecast() - direct call, blocks until done
2. Asynchronous (non-blocking): analyze_forecast_async() - returns job_id, runs in background

Uses global semaphore to prevent server overload when multiple heavy tasks run concurrently.
"""
import json
import threading
from datetime import date
from typing import Dict, Any, Optional, Tuple
from openai import OpenAI

from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL
from repositories.ai_cache_repository import AICacheRepository
from repositories.evn_reservoir_repository import EVNReservoirRepository
from repositories.evn_analysis_cache_repository import EVNAnalysisCacheRepository
from repositories.ai_job_repository import AIJobRepository
from services.request_manager import acquire_heavy_task, release_heavy_task


class AIAnalysisService:
    """Service for AI-powered flood analysis"""

    # Basin info with provinces and districts
    BASIN_INFO = {
        "HONG": {
            "region_name": "Miền Bắc",
            "provinces": {
                "Hà Nội": ["Ba Vì", "Chương Mỹ", "Đan Phượng", "Hoài Đức", "Mỹ Đức", "Phú Xuyên", "Quốc Oai", "Thường Tín"],
                "Hải Phòng": ["An Dương", "An Lão", "Kiến Thụy", "Thủy Nguyên", "Tiên Lãng", "Vĩnh Bảo"],
                "Thái Bình": ["Đông Hưng", "Hưng Hà", "Kiến Xương", "Quỳnh Phụ", "Thái Thụy", "Tiền Hải", "Vũ Thư"],
                "Nam Định": ["Giao Thủy", "Hải Hậu", "Mỹ Lộc", "Nam Trực", "Nghĩa Hưng", "Trực Ninh", "Vụ Bản"],
                "Phú Thọ": ["Cẩm Khê", "Đoan Hùng", "Hạ Hòa", "Lâm Thao", "Phù Ninh", "Tam Nông", "Thanh Ba"],
            },
        },
        "CENTRAL": {
            "region_name": "Miền Trung",
            "provinces": {
                "Đà Nẵng": ["Hải Châu", "Thanh Khê", "Sơn Trà", "Ngũ Hành Sơn", "Liên Chiểu", "Cẩm Lệ", "Hòa Vang"],
                "Quảng Nam": ["Tam Kỳ", "Hội An", "Điện Bàn", "Duy Xuyên", "Đại Lộc", "Núi Thành", "Thăng Bình"],
                "Thừa Thiên Huế": ["TP Huế", "Hương Thủy", "Hương Trà", "Phong Điền", "Quảng Điền", "Phú Lộc"],
                "Quảng Ngãi": ["TP Quảng Ngãi", "Bình Sơn", "Sơn Tịnh", "Tư Nghĩa", "Nghĩa Hành", "Mộ Đức"],
                "Bình Định": ["Quy Nhơn", "An Nhơn", "Tuy Phước", "Phù Cát", "Phù Mỹ", "Hoài Nhơn"],
            },
        },
        "MEKONG": {
            "region_name": "Miền Nam",
            "provinces": {
                "An Giang": ["Long Xuyên", "Châu Đốc", "Tân Châu", "Châu Phú", "Chợ Mới", "Phú Tân"],
                "Đồng Tháp": ["Cao Lãnh", "Sa Đéc", "Hồng Ngự", "Tân Hồng", "Tam Nông", "Thanh Bình"],
                "Cần Thơ": ["Ninh Kiều", "Bình Thủy", "Cái Răng", "Ô Môn", "Thốt Nốt", "Phong Điền"],
                "Long An": ["Tân An", "Kiến Tường", "Bến Lức", "Đức Hòa", "Đức Huệ", "Thủ Thừa"],
                "Tiền Giang": ["Mỹ Tho", "Gò Công", "Cai Lậy", "Châu Thành", "Chợ Gạo"],
            },
        },
        "DONGNAI": {
            "region_name": "Đông Nam Bộ",
            "provinces": {
                "TP.HCM": ["Thủ Đức", "Quận 7", "Bình Chánh", "Nhà Bè", "Cần Giờ", "Hóc Môn", "Củ Chi"],
                "Đồng Nai": ["Biên Hòa", "Long Khánh", "Nhơn Trạch", "Long Thành", "Trảng Bom", "Vĩnh Cửu"],
                "Bình Dương": ["Thủ Dầu Một", "Dĩ An", "Thuận An", "Tân Uyên", "Bến Cát", "Bàu Bàng"],
                "Bà Rịa-Vũng Tàu": ["Vũng Tàu", "Bà Rịa", "Long Điền", "Đất Đỏ", "Xuyên Mộc", "Châu Đức"],
            },
        }
    }

    # Mapping huyện -> xã/phường (dữ liệu thật cho các vùng hay ngập)
    DISTRICT_WARDS = {
        # Đà Nẵng
        "Hải Châu": ["Hải Châu 1", "Hải Châu 2", "Thanh Bình", "Thuận Phước", "Phước Ninh", "Hòa Thuận Tây", "Nam Dương"],
        "Thanh Khê": ["Tam Thuận", "An Khê", "Thạc Gián", "Chính Gián", "Xuân Hà", "Thanh Khê Đông", "Hòa Khê"],
        "Sơn Trà": ["An Hải Bắc", "An Hải Đông", "Phước Mỹ", "Thọ Quang", "Mân Thái", "Nại Hiên Đông"],
        "Ngũ Hành Sơn": ["Mỹ An", "Khuê Mỹ", "Hòa Hải", "Hòa Quý"],
        "Liên Chiểu": ["Hòa Khánh Bắc", "Hòa Khánh Nam", "Hòa Minh"],
        "Cẩm Lệ": ["Hòa Thọ Đông", "Hòa Thọ Tây", "Khuê Trung", "Hòa An", "Hòa Phát"],
        "Hòa Vang": ["Hòa Bắc", "Hòa Liên", "Hòa Ninh", "Hòa Phong", "Hòa Khương", "Hòa Tiến"],
        # Quảng Nam
        "Tam Kỳ": ["An Mỹ", "An Sơn", "An Xuân", "Hòa Hương", "Phước Hòa", "Tân Thạnh", "Trường Xuân"],
        "Hội An": ["Cẩm An", "Cẩm Châu", "Cẩm Kim", "Cẩm Nam", "Cẩm Phô", "Minh An", "Tân An"],
        "Điện Bàn": ["Điện An", "Điện Dương", "Điện Hòa", "Điện Minh", "Điện Nam Bắc", "Điện Nam Trung"],
        "Duy Xuyên": ["Duy Châu", "Duy Hải", "Duy Hòa", "Duy Nghĩa", "Duy Phú", "Duy Tân"],
        "Đại Lộc": ["Đại An", "Đại Cường", "Đại Hiệp", "Đại Hòa", "Đại Lãnh", "Đại Minh"],
        # Thừa Thiên Huế
        "TP Huế": ["Phú Hòa", "Phú Nhuận", "Vĩnh Ninh", "Phường Đúc", "Kim Long", "An Hòa", "Hương Sơ"],
        "Hương Thủy": ["Thủy Bằng", "Thủy Dương", "Thủy Phù", "Thủy Thanh", "Thủy Vân"],
        "Hương Trà": ["Hương An", "Hương Chữ", "Hương Phong", "Hương Văn", "Hương Xuân"],
        "Phong Điền": ["Phong An", "Phong Bình", "Phong Chương", "Phong Hòa", "Phong Thu"],
        # Hà Nội
        "Ba Vì": ["Cam Thượng", "Cẩm Lĩnh", "Chu Minh", "Cổ Đô", "Đông Quang", "Minh Châu"],
        "Chương Mỹ": ["Đại Yên", "Đồng Phú", "Hoàng Văn Thụ", "Hợp Đồng", "Lam Điền"],
        "Đan Phượng": ["Đan Phượng", "Đồng Tháp", "Hạ Mỗ", "Liên Hà", "Liên Trung"],
        "Hoài Đức": ["An Khánh", "An Thượng", "Đắc Sở", "Di Trạch", "Đông La", "Đức Giang"],
        # Long An
        "Tân An": ["Khánh Hậu", "Lợi Bình Nhơn", "An Vĩnh Ngãi", "Bình Tâm", "Hướng Thọ Phú"],
        "Bến Lức": ["Bình Đức", "Lương Bình", "Lương Hòa", "Mỹ Yên", "Nhựt Chánh"],
        "Đức Hòa": ["Đức Hòa Đông", "Đức Hòa Hạ", "Hòa Khánh Đông", "Hòa Khánh Tây"],
        # An Giang
        "Long Xuyên": ["Mỹ Bình", "Mỹ Long", "Mỹ Phước", "Mỹ Quý", "Mỹ Thạnh", "Mỹ Thới"],
        "Châu Đốc": ["Châu Phú A", "Châu Phú B", "Núi Sam", "Vĩnh Mỹ", "Vĩnh Ngươn"],
        # Cần Thơ
        "Ninh Kiều": ["An Bình", "An Cư", "An Hòa", "An Nghiệp", "An Phú", "Cái Khế", "Hưng Lợi"],
        "Bình Thủy": ["Bình Thủy", "Long Hòa", "Long Tuyền", "Thới An Đông", "Trà An", "Trà Nóc"],
        "Cái Răng": ["Ba Láng", "Hưng Phú", "Hưng Thạnh", "Lê Bình", "Phú Thứ", "Tân Phú"],
        # TP.HCM
        "Thủ Đức": ["An Khánh", "An Phú", "Bình Chiểu", "Bình Thọ", "Cát Lái", "Hiệp Bình Chánh"],
        "Quận 7": ["Bình Thuận", "Phú Mỹ", "Phú Thuận", "Tân Hưng", "Tân Kiểng", "Tân Phong"],
        "Bình Chánh": ["Bình Hưng", "Bình Lợi", "Đa Phước", "Hưng Long", "Lê Minh Xuân", "Phong Phú"],
        "Nhà Bè": ["Hiệp Phước", "Long Thới", "Nhơn Đức", "Phú Xuân", "Phước Kiểng"],
    }

    # Mapping hồ chứa -> lưu vực
    RESERVOIR_BASINS = {
        "Tuyên Quang": "HONG", "Lai Châu": "HONG", "Bản Chát": "HONG",
        "Sơn La": "HONG", "Hòa Bình": "HONG", "Thác Bà": "HONG",
        "Huội Quảng": "HONG", "Nậm Chiến": "HONG",
        "A Vương": "CENTRAL", "Sông Tranh 2": "CENTRAL", "Đắk Mi 4": "CENTRAL",
        "Sông Bung 4": "CENTRAL", "Bình Điền": "CENTRAL", "Hương Điền": "CENTRAL",
        "Rào Quán": "CENTRAL", "Sông Ba Hạ": "CENTRAL", "Krông H'năng": "CENTRAL",
        "Sê San 4": "CENTRAL", "Sê San 4A": "CENTRAL", "Ialy": "CENTRAL",
        "Plei Krông": "CENTRAL", "Kanak": "CENTRAL", "Đại Ninh": "CENTRAL",
        "Đồng Nai 3": "CENTRAL", "Đồng Nai 4": "CENTRAL",
        "Trị An": "DONGNAI", "Thác Mơ": "DONGNAI", "Cần Đơn": "DONGNAI",
        "Srok Phu Miêng": "DONGNAI",
        "Buôn Kuốp": "MEKONG", "Buôn Tua Srah": "MEKONG",
        "Srêpốk 3": "MEKONG", "Srêpốk 4": "MEKONG", "Đrây H'linh": "MEKONG",
    }

    def __init__(self):
        self.cache_repo = AICacheRepository()
        self.evn_repo = EVNReservoirRepository()
        self.evn_analysis_cache = EVNAnalysisCacheRepository()
        self.job_repo = AIJobRepository()
        self.client = OpenAI(
            api_key=DEEPSEEK_API_KEY,
            base_url=DEEPSEEK_BASE_URL
        ) if DEEPSEEK_API_KEY else None
        # Track running background jobs
        self._running_jobs = set()

    def analyze_forecast(
        self,
        basin_name: str,
        forecast_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Phân tích dự báo lũ lụt bằng DeepSeek AI.

        Logic đơn giản:
        1. Kiểm tra DB có dữ liệu phân tích của ngày hôm nay không
        2. Nếu CÓ -> trả về từ DB (không gọi AI)
        3. Nếu KHÔNG CÓ (chưa phân tích hoặc ngày cũ) -> gọi AI phân tích mới và lưu DB

        Sau 1 ngày, khi gọi API sẽ tự động phân tích mới vì analysis_date = today

        Args:
            basin_name: Basin code
            forecast_data: Forecast data dict

        Returns:
            AI analysis result từ DB
        """
        today = date.today()
        print(f"\n{'='*50}")
        print(f"[AI Service] analyze_forecast() called for {basin_name}")
        print(f"[AI Service] Today: {today}")

        # Bước 1: Kiểm tra DB có data của ngày hôm nay không
        print(f"[AI Service] Step 1: Checking DB cache...")
        cached = self.cache_repo.get_cached_analysis(basin_name, today)

        if cached:
            # Có data ngày hôm nay -> trả về từ DB
            print(f"[AI Service] ✓ CACHE HIT! Returning from DB")
            print(f"{'='*50}\n")
            return cached

        # Bước 2: Không có data ngày hôm nay -> phân tích mới
        print(f"[AI Service] ✗ CACHE MISS! Calling AI...")
        print(f"Không có dữ liệu phân tích {basin_name} cho ngày {today}, đang phân tích mới...")

        if not self.client:
            print("DeepSeek API chưa cấu hình, dùng fallback")
            analysis = self._get_fallback_analysis(basin_name, forecast_data)
        else:
            try:
                analysis = self._call_deepseek_api(basin_name, forecast_data)
            except json.JSONDecodeError as e:
                print(f"Lỗi parse JSON: {e}")
                analysis = self._get_fallback_analysis(basin_name, forecast_data)
            except Exception as e:
                print(f"Lỗi AI analysis: {e}")
                analysis = self._get_fallback_analysis(basin_name, forecast_data)

        # Bước 3: Lưu vào DB
        self.cache_repo.save_analysis(basin_name, analysis, today)

        # Thêm thông tin ngày phân tích
        analysis["analysis_date"] = str(today)

        return analysis

    # ==================== ASYNC (NON-BLOCKING) MODE ====================

    def analyze_forecast_async(
        self,
        basin_name: str,
        forecast_data: Dict[str, Any]
    ) -> Tuple[str, Optional[Dict[str, Any]]]:
        """
        Start AI analysis in background thread (non-blocking).

        Logic:
        1. Check DB cache first - if today's data exists, return immediately
        2. Check if there's already a pending/processing job for this basin
        3. If no existing job, create new job and start background thread
        4. Return (job_id, cached_result or None)

        Args:
            basin_name: Basin code
            forecast_data: Forecast data dict

        Returns:
            Tuple of (job_id, cached_result_or_none)
            - If cached: ("cached", analysis_data)
            - If processing: (job_id, None)
        """
        today = date.today()
        basin_upper = basin_name.upper()

        print(f"\n{'='*50}")
        print(f"[AI Async] analyze_forecast_async() called for {basin_upper}")

        # Step 1: Check DB cache
        cached = self.cache_repo.get_cached_analysis(basin_upper, today)
        if cached:
            print(f"[AI Async] CACHE HIT! Returning from DB immediately")
            return ("cached", cached)

        # Step 2: Check for existing pending/processing job
        existing_job = self.job_repo.get_pending_job(basin_upper)
        if existing_job:
            job_id = existing_job["job_id"]
            print(f"[AI Async] Found existing job: {job_id} (status: {existing_job['status']})")
            return (job_id, None)

        # Step 3: Create new job
        job_id = self.job_repo.create_job(basin_upper, forecast_data)
        print(f"[AI Async] Created new job: {job_id}")

        # Step 4: Start background thread
        thread = threading.Thread(
            target=self._run_analysis_job,
            args=(job_id, basin_upper, forecast_data),
            daemon=True
        )
        thread.start()
        self._running_jobs.add(job_id)

        print(f"[AI Async] Started background thread for {job_id}")
        print(f"{'='*50}\n")

        return (job_id, None)

    def _run_analysis_job(
        self,
        job_id: str,
        basin_name: str,
        forecast_data: Dict[str, Any]
    ):
        """
        Run AI analysis in background thread.
        Updates job status as it progresses.
        Uses global semaphore to prevent concurrent heavy tasks.
        """
        task_name = f"AI_{basin_name}_{job_id}"
        semaphore_acquired = False

        try:
            print(f"[AI Job {job_id}] Starting analysis...")

            # Update status to processing
            self.job_repo.update_status(job_id, "processing", progress=10)

            today = date.today()

            # Check cache again (in case another thread completed)
            cached = self.cache_repo.get_cached_analysis(basin_name, today)
            if cached:
                print(f"[AI Job {job_id}] Cache found, skipping API call")
                self.job_repo.update_status(job_id, "completed", result=cached)
                self._running_jobs.discard(job_id)
                return

            # Acquire global semaphore before heavy API call
            semaphore_acquired = acquire_heavy_task(task_name, timeout=180.0)
            if not semaphore_acquired:
                print(f"[AI Job {job_id}] Could not acquire semaphore, using fallback")
                analysis = self._get_fallback_analysis(basin_name, forecast_data)
            else:
                # Update progress
                self.job_repo.update_status(job_id, "processing", progress=30)

                # Call AI
                if not self.client:
                    print(f"[AI Job {job_id}] No API key, using fallback")
                    analysis = self._get_fallback_analysis(basin_name, forecast_data)
                else:
                    try:
                        self.job_repo.update_status(job_id, "processing", progress=50)
                        analysis = self._call_deepseek_api(basin_name, forecast_data)
                        self.job_repo.update_status(job_id, "processing", progress=80)
                    except Exception as e:
                        print(f"[AI Job {job_id}] API error: {e}, using fallback")
                        analysis = self._get_fallback_analysis(basin_name, forecast_data)

            # Save to cache
            self.cache_repo.save_analysis(basin_name, analysis, today)
            analysis["analysis_date"] = str(today)

            # Update job as completed
            self.job_repo.update_status(job_id, "completed", result=analysis)
            print(f"[AI Job {job_id}] Completed successfully!")

        except Exception as e:
            print(f"[AI Job {job_id}] Failed with error: {e}")
            self.job_repo.update_status(job_id, "failed", error_message=str(e))

        finally:
            self._running_jobs.discard(job_id)
            if semaphore_acquired:
                release_heavy_task(task_name)

    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get status of an AI analysis job.

        Args:
            job_id: Job identifier

        Returns:
            Dict with job status, progress, and result (if completed)
        """
        if job_id == "cached":
            return {"status": "completed", "progress": 100, "from_cache": True}

        job = self.job_repo.get_job(job_id)
        if not job:
            return None

        response = {
            "job_id": job["job_id"],
            "basin_code": job["basin_code"],
            "status": job["status"],
            "progress": job["progress"],
            "created_at": job["created_at"].isoformat() if job.get("created_at") else None
        }

        if job["status"] == "completed" and job.get("result"):
            response["result"] = job["result"]
            response["completed_at"] = job["completed_at"].isoformat() if job.get("completed_at") else None

        if job["status"] == "failed":
            response["error"] = job.get("error_message")

        return response

    # ==================== SYNC MODE (ORIGINAL) ====================

    def _call_deepseek_api(
        self,
        basin_name: str,
        forecast_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Call DeepSeek API for analysis"""
        info = self.BASIN_INFO.get(basin_name, {"region_name": basin_name, "provinces": {}})
        forecast_days = forecast_data.get("forecast_days", [])

        # Build prompt
        prompt = f"""Bạn là chuyên gia phân tích thiên tai lũ lụt Việt Nam. Phân tích dự báo cho {info['region_name']} ({basin_name}):

Dữ liệu dự báo 14 ngày:
"""
        for day in forecast_days[:14]:
            prompt += f"\n- {day['date']}: Mưa {day['daily_rain']:.1f}mm, Tích lũy 3 ngày {day['accumulated_3d']:.1f}mm"

        prompt += f"""

Các tỉnh trong vùng và huyện:
{chr(10).join([f"- {p}: {', '.join(d[:5])}" for p, d in info['provinces'].items()])}

BẮT BUỘC trả về JSON với TẤT CẢ các tỉnh và TỐI THIỂU 3-4 huyện mỗi tỉnh:
{{
  "peak_rain": {{"date": "YYYY-MM-DD", "amount_mm": số, "intensity": "Nhẹ/Vừa/Lớn/Rất lớn"}},
  "flood_timeline": {{"rising_start": "YYYY-MM-DD", "peak_date": "YYYY-MM-DD", "receding_end": "YYYY-MM-DD"}},
  "affected_areas": [{{"province": "Tên tỉnh", "impact_level": "Cao/Trung bình/Thấp", "water_level_cm": số (ước tính mực nước ngập 20-200cm), "flood_area_km2": số (ước tính diện tích ngập 5-100km2), "reason": "Lý do ngập", "districts": [{{"name": "Tên huyện", "impact_level": "Cao/Trung bình/Thấp", "water_level_cm": số, "flood_area_km2": số, "affected_wards": ["Tên xã 1", "Tên xã 2"], "evacuation_needed": true/false, "notes": "Ghi chú"}}]}}],
  "overall_risk": {{"level": "Thấp/Trung bình/Cao/Rất cao", "score": 1-10, "description": "Mô tả"}},
  "recommendations": {{"government": ["..."], "citizens": ["..."]}},
  "summary": "Tóm tắt 1-2 câu"
}}"""

        response = self.client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "Bạn là chuyên gia phân tích thiên tai. LUÔN trả về JSON hợp lệ."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=2000
        )

        result = response.choices[0].message.content.strip()

        # Handle markdown code blocks
        if result.startswith("```"):
            result = result.split("```")[1]
            if result.startswith("json"):
                result = result[4:]
        result = result.strip()

        return json.loads(result)

    def _get_fallback_analysis(
        self,
        basin_name: str,
        forecast_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate fallback analysis when AI is unavailable"""
        forecast_days = forecast_data.get("forecast_days", [])

        # Find peak rain
        max_rain = 0
        peak_date = None
        for day in forecast_days:
            if day.get("daily_rain", 0) > max_rain:
                max_rain = day["daily_rain"]
                peak_date = day["date"]

        # Determine intensity and whether flood is possible
        # Only consider flood timeline if rainfall is significant (>= 30mm)
        has_flood_risk = max_rain >= 30

        if max_rain >= 100:
            intensity = "Rất lớn"
            risk_level = "Cao"
            risk_score = 7
        elif max_rain >= 50:
            intensity = "Lớn"
            risk_level = "Trung bình"
            risk_score = 5
        elif max_rain >= 20:
            intensity = "Vừa"
            risk_level = "Thấp"
            risk_score = 3
        else:
            intensity = "Nhẹ"
            risk_level = "Rất thấp"
            risk_score = 1

        info = self.BASIN_INFO.get(basin_name, {"region_name": basin_name, "provinces": {}})

        # Generate affected areas with realistic estimates based on rainfall
        affected_areas = []
        provinces_list = list(info.get("provinces", {}).items())[:5]

        for i, (province, districts_list) in enumerate(provinces_list):
            # Estimate water level based on rainfall and position
            base_water = min(30 + (max_rain * 0.5), 150)  # 30-150cm range
            water_level = int(base_water * (1 - i * 0.15))  # Decreasing for farther provinces
            flood_area = round(5 + (max_rain * 0.3) * (1 - i * 0.1), 1)  # 5-35 km2

            # Generate districts data
            districts_data = []
            for j, district_name in enumerate(districts_list[:4]):
                district_water = int(water_level * (1 - j * 0.1))
                district_area = round(flood_area * 0.3 * (1 - j * 0.1), 1)
                # Get affected wards from DISTRICT_WARDS dictionary
                wards = self.DISTRICT_WARDS.get(district_name, [])
                # Select wards based on impact level (more wards for higher impact)
                if district_water > 60:
                    num_wards = min(len(wards), 5)  # Cao - up to 5 wards
                elif district_water > 30:
                    num_wards = min(len(wards), 3)  # Trung bình - up to 3 wards
                else:
                    num_wards = min(len(wards), 2)  # Thấp - up to 2 wards

                districts_data.append({
                    "name": district_name,
                    "impact_level": "Cao" if district_water > 60 else "Trung bình" if district_water > 30 else "Thấp",
                    "water_level_cm": district_water,
                    "flood_area_km2": district_area,
                    "affected_wards": wards[:num_wards],
                    "evacuation_needed": district_water > 80,
                    "notes": f"Ước tính mực nước {district_water}cm"
                })

            affected_areas.append({
                "province": province,
                "impact_level": "Cao" if water_level > 60 else "Trung bình" if water_level > 30 else "Thấp",
                "water_level_cm": water_level,
                "flood_area_km2": flood_area,
                "reason": f"Lượng mưa tích lũy cao ({max_rain:.0f}mm)",
                "districts": districts_data
            })

        # Only generate flood timeline if there's actual flood risk
        # When rainfall is low (< 30mm), set timeline to null/N/A
        if has_flood_risk:
            flood_timeline = {
                "rising_start": peak_date,
                "peak_date": peak_date,
                "receding_end": peak_date
            }
            summary = f"Dự báo lượng mưa tối đa {max_rain:.1f}mm. Cần theo dõi diễn biến."
        else:
            # No flood risk - set timeline to null/N/A
            flood_timeline = {
                "rising_start": "N/A",
                "peak_date": "N/A",
                "receding_end": "N/A"
            }
            summary = f"Thời tiết ổn định, lượng mưa thấp ({max_rain:.1f}mm). Không có nguy cơ lũ lụt."

        return {
            "peak_rain": {
                "date": peak_date,
                "amount_mm": max_rain,
                "intensity": intensity
            },
            "flood_timeline": flood_timeline,
            "affected_areas": affected_areas if has_flood_risk else [],  # No affected areas if no flood risk
            "overall_risk": {
                "level": risk_level,
                "score": risk_score,
                "description": summary
            },
            "recommendations": {
                "government": ["Theo dõi diễn biến thời tiết", "Chuẩn bị phương án ứng phó"] if has_flood_risk else ["Tiếp tục theo dõi dự báo thời tiết"],
                "citizens": ["Theo dõi thông tin cảnh báo", "Chuẩn bị đồ dùng thiết yếu"] if has_flood_risk else ["Không cần chuẩn bị đặc biệt"]
            },
            "summary": summary
        }

    def _get_reservoirs_for_basin(self, basin_name: str) -> list:
        """Get EVN reservoir data for a specific basin"""
        all_reservoirs = self.evn_repo.get_latest()
        basin_reservoirs = []
        for r in all_reservoirs:
            r_basin = self.RESERVOIR_BASINS.get(r["name"], "UNKNOWN")
            if r_basin == basin_name:
                # Calculate water percent
                if r.get("hdbt") and r.get("htl"):
                    r["water_percent"] = round(r["htl"] / r["hdbt"] * 100, 1)
                else:
                    r["water_percent"] = None
                basin_reservoirs.append(r)
        return basin_reservoirs

    def analyze_reservoir_comprehensive(
        self,
        basin_name: str,
        forecast_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Comprehensive analysis combining EVN reservoir data + weather forecast

        Args:
            basin_name: Basin code (HONG, CENTRAL, MEKONG, DONGNAI)
            forecast_data: Weather forecast data from Open-Meteo

        Returns:
            AI analysis result including reservoir impact
        """
        # Check DB cache first (EVN Analysis Cache - 1 day expiry)
        cached = self.evn_analysis_cache.get_cached_analysis(basin_name, date.today())
        if cached:
            print(f"✓ Using DB cached EVN analysis for {basin_name}")
            return cached.get("analysis", {})

        # Get EVN reservoir data for this basin
        reservoirs = self._get_reservoirs_for_basin(basin_name)
        reservoir_status = {
            "total": len(reservoirs),
            "reservoirs": reservoirs
        }

        if not self.client:
            print("DeepSeek API not configured, using fallback")
            result = self._get_reservoir_fallback(basin_name, forecast_data, reservoirs)
            # Save to DB cache
            self.evn_analysis_cache.save_analysis(
                basin_name, result, reservoir_status, date.today()
            )
            return result

        try:
            analysis = self._call_deepseek_reservoir_api(basin_name, forecast_data, reservoirs)
            # Save to DB cache
            self.evn_analysis_cache.save_analysis(
                basin_name, analysis, reservoir_status, date.today()
            )
            return analysis

        except Exception as e:
            print(f"Error in reservoir AI analysis: {e}")
            result = self._get_reservoir_fallback(basin_name, forecast_data, reservoirs)
            # Save fallback to DB cache
            self.evn_analysis_cache.save_analysis(
                basin_name, result, reservoir_status, date.today()
            )
            return result

    def _call_deepseek_reservoir_api(
        self,
        basin_name: str,
        forecast_data: Dict[str, Any],
        reservoirs: list
    ) -> Dict[str, Any]:
        """Call DeepSeek API for reservoir + weather analysis"""
        info = self.BASIN_INFO.get(basin_name, {"region_name": basin_name, "provinces": {}})
        forecast_days = forecast_data.get("forecast_days", [])

        # Build reservoir info string
        reservoir_str = ""
        if reservoirs:
            reservoir_str = "\n\nDỮ LIỆU HỒ CHỨA THỦY ĐIỆN (DỮ LIỆU THỰC TỪ EVN):\n"
            for r in reservoirs:
                water_pct = r.get("water_percent", "N/A")
                gates_open = (r.get("ncxs") or 0) + (r.get("ncxm") or 0)
                discharge = r.get("total_qx") or 0
                reservoir_str += f"- {r['name']}: Htl={r.get('htl')}m ({water_pct}% dung tích), "
                reservoir_str += f"Xả={discharge}m³/s, Cửa xả mở={gates_open}\n"

        # Build prompt
        prompt = f"""Bạn là chuyên gia phân tích thiên tai lũ lụt Việt Nam. Phân tích TỔNG HỢP cho {info['region_name']} ({basin_name}):

DỮ LIỆU DỰ BÁO THỜI TIẾT (Open-Meteo 14 ngày):
"""
        for day in forecast_days[:14]:
            prompt += f"- {day['date']}: Mưa {day['daily_rain']:.1f}mm, Tích lũy 3 ngày {day['accumulated_3d']:.1f}mm\n"

        prompt += reservoir_str

        prompt += f"""
CÁC TỈNH TRONG VÙNG:
{chr(10).join([f"- {p}: {', '.join(d[:5])}" for p, d in info['provinces'].items()])}

YÊU CẦU PHÂN TÍCH:
1. Đánh giá nguy cơ lũ từ MƯA LỚN dựa trên dự báo thời tiết
2. Đánh giá nguy cơ lũ từ XẢ ĐẬP dựa trên dữ liệu hồ chứa EVN thực tế
3. Kết hợp 2 yếu tố để đưa ra đánh giá tổng thể
4. Xác định vùng nguy hiểm nhất (hạ lưu đập + vùng trũng)

BẮT BUỘC trả về JSON:
{{
  "analysis_type": "reservoir_weather_combined",
  "weather_risk": {{
    "peak_rain": {{"date": "YYYY-MM-DD", "amount_mm": số, "intensity": "Nhẹ/Vừa/Lớn/Rất lớn"}},
    "risk_level": "Thấp/Trung bình/Cao/Rất cao",
    "description": "Mô tả nguy cơ từ mưa"
  }},
  "reservoir_risk": {{
    "high_water_count": số hồ mực nước cao (>90%),
    "discharging_count": số hồ đang xả,
    "critical_reservoirs": ["Tên hồ nguy hiểm nhất"],
    "risk_level": "Thấp/Trung bình/Cao/Rất cao",
    "description": "Mô tả nguy cơ từ hồ chứa"
  }},
  "combined_risk": {{
    "level": "Thấp/Trung bình/Cao/Rất cao",
    "score": 1-10,
    "description": "Đánh giá tổng hợp cả 2 yếu tố"
  }},
  "downstream_impact": [
    {{"area": "Tên vùng hạ lưu", "reservoir": "Hồ ảnh hưởng", "risk": "Cao/TB/Thấp", "reason": "Lý do"}}
  ],
  "affected_areas": [{{"province": "Tên tỉnh", "impact_level": "Cao/TB/Thấp", "water_level_cm": số, "flood_type": "Mưa/Xả đập/Cả hai", "districts": [{{"name": "Huyện", "impact_level": "Cao/TB/Thấp"}}]}}],
  "timeline": {{
    "flood_start": "YYYY-MM-DD hoặc null",
    "peak": "YYYY-MM-DD hoặc null",
    "end": "YYYY-MM-DD hoặc null"
  }},
  "recommendations": {{
    "immediate": ["Hành động ngay"],
    "preparation": ["Chuẩn bị"],
    "monitoring": ["Theo dõi"]
  }},
  "summary": "Tóm tắt 2-3 câu về tình hình tổng thể"
}}"""

        response = self.client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "Bạn là chuyên gia phân tích thiên tai lũ lụt Việt Nam. LUÔN trả về JSON hợp lệ. Khi phân tích hồ chứa, chú ý: mực nước >95% là RẤT CAO, cửa xả mở = đang xả lũ."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=2500
        )

        result = response.choices[0].message.content.strip()

        # Handle markdown code blocks
        if result.startswith("```"):
            result = result.split("```")[1]
            if result.startswith("json"):
                result = result[4:]
        result = result.strip()

        return json.loads(result)

    def _get_reservoir_fallback(
        self,
        basin_name: str,
        forecast_data: Dict[str, Any],
        reservoirs: list
    ) -> Dict[str, Any]:
        """Generate fallback reservoir analysis when AI is unavailable"""
        forecast_days = forecast_data.get("forecast_days", [])

        # Find peak rain
        max_rain = 0
        peak_date = None
        for day in forecast_days:
            if day.get("daily_rain", 0) > max_rain:
                max_rain = day["daily_rain"]
                peak_date = day["date"]

        # Analyze reservoirs
        high_water_count = 0
        discharging_count = 0
        critical_reservoirs = []

        for r in reservoirs:
            water_pct = r.get("water_percent") or 0
            gates_open = (r.get("ncxs") or 0) + (r.get("ncxm") or 0)

            if water_pct >= 90:
                high_water_count += 1
            if gates_open > 0:
                discharging_count += 1
                critical_reservoirs.append(r["name"])

        # Determine risk levels
        weather_risk = "Cao" if max_rain >= 100 else "Trung bình" if max_rain >= 50 else "Thấp"
        reservoir_risk = "Cao" if discharging_count > 0 or high_water_count >= 3 else "Trung bình" if high_water_count >= 1 else "Thấp"

        # Combined risk
        if weather_risk == "Cao" and reservoir_risk == "Cao":
            combined_level = "Rất cao"
            combined_score = 9
        elif weather_risk == "Cao" or reservoir_risk == "Cao":
            combined_level = "Cao"
            combined_score = 7
        elif weather_risk == "Trung bình" or reservoir_risk == "Trung bình":
            combined_level = "Trung bình"
            combined_score = 5
        else:
            combined_level = "Thấp"
            combined_score = 2

        info = self.BASIN_INFO.get(basin_name, {"region_name": basin_name, "provinces": {}})

        # Generate affected areas
        affected_areas = []
        for province, districts in list(info.get("provinces", {}).items())[:4]:
            flood_type = "Cả hai" if discharging_count > 0 and max_rain >= 50 else "Xả đập" if discharging_count > 0 else "Mưa"
            water_level = int(30 + max_rain * 0.4 + discharging_count * 20)

            affected_areas.append({
                "province": province,
                "impact_level": "Cao" if water_level > 80 else "Trung bình" if water_level > 40 else "Thấp",
                "water_level_cm": water_level,
                "flood_type": flood_type,
                "districts": [{"name": d, "impact_level": "Trung bình"} for d in districts[:3]]
            })

        # Downstream impact
        downstream_impact = []
        for r_name in critical_reservoirs[:3]:
            downstream_impact.append({
                "area": f"Hạ lưu {r_name}",
                "reservoir": r_name,
                "risk": "Cao",
                "reason": "Hồ đang xả lũ"
            })

        return {
            "analysis_type": "reservoir_weather_combined",
            "weather_risk": {
                "peak_rain": {"date": peak_date, "amount_mm": max_rain, "intensity": "Lớn" if max_rain >= 50 else "Vừa"},
                "risk_level": weather_risk,
                "description": f"Dự báo lượng mưa tối đa {max_rain:.0f}mm"
            },
            "reservoir_risk": {
                "high_water_count": high_water_count,
                "discharging_count": discharging_count,
                "critical_reservoirs": critical_reservoirs,
                "risk_level": reservoir_risk,
                "description": f"{discharging_count} hồ đang xả, {high_water_count} hồ mực nước cao"
            },
            "combined_risk": {
                "level": combined_level,
                "score": combined_score,
                "description": f"Kết hợp nguy cơ từ mưa ({weather_risk}) và hồ chứa ({reservoir_risk})"
            },
            "downstream_impact": downstream_impact,
            "affected_areas": affected_areas,
            "timeline": {
                "flood_start": peak_date,
                "peak": peak_date,
                "end": None
            },
            "recommendations": {
                "immediate": ["Theo dõi thông báo xả lũ từ các hồ chứa"] if discharging_count > 0 else [],
                "preparation": ["Chuẩn bị đồ dùng thiết yếu", "Xác định nơi sơ tán"],
                "monitoring": ["Theo dõi mực nước sông", "Cập nhật dự báo thời tiết"]
            },
            "summary": f"Vùng {info['region_name']}: {discharging_count} hồ đang xả lũ, {high_water_count} hồ mực nước cao, dự báo mưa tối đa {max_rain:.0f}mm. Mức nguy cơ tổng hợp: {combined_level}."
        }
