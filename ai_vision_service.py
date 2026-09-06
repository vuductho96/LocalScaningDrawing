import os
import json
import base64
import logging
import datetime
from typing import Optional, List, Dict, Any, Tuple
import requests

logger = logging.getLogger("ai_vision_service")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "ai_config.json")
USAGE_FILE = os.path.join(BASE_DIR, "ai_usage.json")

from PIL import Image
import io

# Hạn mức mặc định theo từng gói dịch vụ của Google Gemini:
QUOTA_PROFILES = {
    "free": {
        "name": "Free Tier (Miễn phí vĩnh viễn)",
        "rpd_limit": 1500,        # 1,500 requests/ngày
        "rpm_limit": 15,          # 15 requests/phút
        "tpm_limit": 1000000,     # 1,000,000 tokens/phút
        "daily_cost_cap": 0.0
    },
    "paid": {
        "name": "Pay-as-you-go (Trả phí linh hoạt theo Token)",
        "rpd_limit": 10000,       # 10,000 requests/ngày (hoặc tùy chỉnh)
        "rpm_limit": 1000,        # 1,000 requests/phút
        "tpm_limit": 4000000,     # 4,000,000 tokens/phút
        "daily_cost_cap": 10.0
    }
}

# Danh sách model ưu tiên theo thứ tự tối ưu token & tốc độ cao nhất
CANDIDATE_MODELS = [
    "gemini-2.5-flash",
    "gemini-flash-latest",
    "gemini-2.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-3.8-flash",
    "gemini-3.7-flash"
]

def optimize_image_for_gemini(image_bytes: bytes, max_dim: int = 1600, quality: int = 85) -> Tuple[str, str]:
    """
    Tối ưu hóa ảnh trước khi gửi lên Gemini Vision:
    - Downscale ảnh nếu kích thước vượt quá max_dim (giữ nguyên tỷ lệ khung hình).
    - Nén dạng JPEG 85% để giảm mạnh dung lượng base64 và số lượng vision tiles.
    - Tiết kiệm 60% - 75% lượng input tokens tiêu thụ.
    """
    try:
        img = Image.open(io.BytesIO(image_bytes))
        w, h = img.size
        
        # Nếu là ảnh nhỏ (ví dụ ảnh crop từng kích thước lẻ)
        if max(w, h) <= max_dim:
            # Chỉ nén lại định dạng JPEG nếu cần
            if img.mode != "RGB":
                img = img.convert("RGB")
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=quality, optimize=True)
            return base64.b64encode(buf.getvalue()).decode("utf-8"), "image/jpeg"

        # Downscale thông minh giữ tỷ lệ
        ratio = min(max_dim / float(w), max_dim / float(h))
        new_w = max(1, int(w * ratio))
        new_h = max(1, int(h * ratio))
        resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        if resized.mode != "RGB":
            resized = resized.convert("RGB")

        buf = io.BytesIO()
        resized.save(buf, format="JPEG", quality=quality, optimize=True)
        return base64.b64encode(buf.getvalue()).decode("utf-8"), "image/jpeg"
    except Exception as e:
        logger.warning(f"Could not optimize image, falling back to raw: {e}")
        return base64.b64encode(image_bytes).decode("utf-8"), "image/png"

class AIVisionService:
    def __init__(self):
        self.api_key = os.environ.get("GEMINI_API_KEY", "")
        self.model_name = CANDIDATE_MODELS[0]
        self.billing_tier = "free"  # "free" hoac "paid"
        self.custom_rpd_limit = 0    # 0 = dung mac dinh profile
        self.server_tier_detected = "standard"
        self._load_config()
        self._load_usage()

    def _load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if data.get("api_key"):
                        self.api_key = data["api_key"]
                    if data.get("model_name"):
                        self.model_name = data["model_name"]
                    if data.get("billing_tier"):
                        self.billing_tier = data["billing_tier"]
                    if data.get("custom_rpd_limit"):
                        self.custom_rpd_limit = int(data["custom_rpd_limit"])
            except Exception as e:
                logger.error(f"Error reading ai_config.json: {e}")

    def _load_usage(self):
        self.usage_data = {}
        if os.path.exists(USAGE_FILE):
            try:
                with open(USAGE_FILE, "r", encoding="utf-8") as f:
                    self.usage_data = json.load(f)
            except Exception as e:
                logger.error(f"Error reading ai_usage.json: {e}")

    def save_config(self, api_key: Optional[str] = None, model_name: Optional[str] = None, billing_tier: Optional[str] = None, custom_rpd_limit: Optional[int] = None):
        if api_key is not None:
            clean_key = api_key.strip()
            # Chi ghi de khi nguoi dung nhap key moi thuc su (khong phai chuoi trong hoac masked dot)
            if clean_key and not all(c in '•* ' for c in clean_key):
                self.api_key = clean_key
        if model_name:
            self.model_name = model_name.strip()
        if billing_tier in QUOTA_PROFILES:
            self.billing_tier = billing_tier
        if custom_rpd_limit is not None and custom_rpd_limit > 0:
            self.custom_rpd_limit = custom_rpd_limit
        elif custom_rpd_limit == 0:
            self.custom_rpd_limit = 0

        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump({
                    "api_key": self.api_key,
                    "model_name": self.model_name,
                    "billing_tier": self.billing_tier,
                    "custom_rpd_limit": self.custom_rpd_limit
                }, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Error saving ai_config.json: {e}")
            return False

    def clear_config(self):
        """Xóa sạch API key khỏi bộ nhớ và file cấu hình json."""
        self.api_key = ""
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump({
                    "api_key": "",
                    "model_name": self.model_name
                }, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Error clearing ai_config.json: {e}")
            return False

    def is_configured(self) -> bool:
        return bool(self.api_key and len(self.api_key) > 10)

    def _save_usage(self):
        try:
            with open(USAGE_FILE, "w", encoding="utf-8") as f:
                json.dump(self.usage_data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving ai_usage.json: {e}")

    def record_usage(self, model: str, total_tokens: int = 0):
        now = datetime.datetime.now()
        day_key = now.strftime("%Y-%m-%d")
        min_key = now.strftime("%Y-%m-%d %H:%M")

        if "days" not in self.usage_data:
            self.usage_data["days"] = {}
        if day_key not in self.usage_data["days"]:
            self.usage_data["days"][day_key] = {"requests": 0, "tokens": 0, "models": {}}

        day_stats = self.usage_data["days"][day_key]
        day_stats["requests"] += 1
        day_stats["tokens"] += total_tokens
        day_stats["models"][model] = day_stats["models"].get(model, 0) + 1

        if "minutes" not in self.usage_data:
            self.usage_data["minutes"] = {}
        if min_key not in self.usage_data["minutes"]:
            self.usage_data["minutes"][min_key] = {"requests": 0, "tokens": 0}

        min_stats = self.usage_data["minutes"][min_key]
        min_stats["requests"] += 1
        min_stats["tokens"] += total_tokens

        # Don dep du lieu cac phut cu (chi giu lai 10 phut gan nhat)
        keys_to_del = [k for k in self.usage_data["minutes"].keys() if k != min_key]
        if len(keys_to_del) > 10:
            for k in keys_to_del[:-10]:
                del self.usage_data["minutes"][k]

        self._save_usage()

    def get_usage_stats(self) -> Dict[str, Any]:
        now = datetime.datetime.now()
        day_key = now.strftime("%Y-%m-%d")
        min_key = now.strftime("%Y-%m-%d %H:%M")

        day_stats = self.usage_data.get("days", {}).get(day_key, {"requests": 0, "tokens": 0, "models": {}})
        min_stats = self.usage_data.get("minutes", {}).get(min_key, {"requests": 0, "tokens": 0})

        profile = QUOTA_PROFILES.get(self.billing_tier, QUOTA_PROFILES["free"])
        
        # Hạn mức ngày: ưu tiên custom_rpd_limit nếu người dùng đặt
        rpd_limit = self.custom_rpd_limit if self.custom_rpd_limit > 0 else profile["rpd_limit"]
        rpm_limit = profile["rpm_limit"]
        tpm_limit = profile["tpm_limit"]

        rpd_used = day_stats["requests"]
        rpm_used = min_stats["requests"]
        day_tokens = day_stats.get("tokens", 0)

        # Tính tổng chi phí ước tính (cho gói trả phí: ~$0.075 / 1M tokens đối với Gemini 2.5/3 Flash)
        estimated_cost_usd = round((day_tokens / 1_000_000.0) * 0.075, 4)

        # Phần trăm sử dụng thực tế:
        # Nếu là gói Free: % dựa trên RPD limit
        # Nếu là gói Paid: % dựa trên hạn mức ngày người dùng thiết lập (ví dụ budget 5,000 req/ngày hoặc 10,000 req/ngày)
        percent_rpd = min(100.0, round((rpd_used / rpd_limit) * 100, 1)) if rpd_limit > 0 else 0.0
        percent_rpm = min(100.0, round((rpm_used / rpm_limit) * 100, 1)) if rpm_limit > 0 else 0.0

        return {
            "configured": self.is_configured(),
            "model": self.model_name,
            "billing_tier": self.billing_tier,
            "tier_name": profile["name"],
            "server_tier_detected": self.server_tier_detected,
            "custom_rpd_limit": self.custom_rpd_limit,
            "day_key": day_key,
            "rpd_used": rpd_used,
            "rpd_limit": rpd_limit,
            "rpd_remaining": max(0, rpd_limit - rpd_used),
            "percent_rpd": percent_rpd,
            "rpm_used": rpm_used,
            "rpm_limit": rpm_limit,
            "rpm_remaining": max(0, rpm_limit - rpm_used),
            "percent_rpm": percent_rpm,
            "day_tokens": day_tokens,
            "estimated_cost_usd": estimated_cost_usd,
            "models_used": day_stats.get("models", {})
        }

    def _request_gemini(self, prompt: str, image_b64: Optional[str] = None, mime_type: str = "image/jpeg", timeout: int = 25) -> Tuple[bool, Any]:
        if not self.is_configured():
            return False, "Chưa cấu hình Gemini API Key"

        # Danh sách model thử nghiệm (ưu tiên model_name hiện tại)
        models_to_try = [self.model_name] + [m for m in CANDIDATE_MODELS if m != self.model_name]

        parts = [{"text": prompt}]
        if image_b64:
            parts.append({
                "inline_data": {
                    "mime_type": mime_type,
                    "data": image_b64
                }
            })

        payload = {
            "contents": [{"parts": parts}],
            "generationConfig": {
                "response_mime_type": "application/json",
                "temperature": 0.1
            }
        }

        last_err = ""
        is_rate_limited = False
        retry_seconds = 20

        for model in models_to_try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.api_key}"
            try:
                r = requests.post(url, json=payload, timeout=timeout)
                if r.status_code == 200:
                    res_json = r.json()
                    text = res_json["candidates"][0]["content"]["parts"][0]["text"]
                    self.model_name = model  # Giữ lại model thành công
                    
                    # Phát hiện service tier trả về từ Google Server
                    tier_hdr = r.headers.get("X-Gemini-Service-Tier") or r.headers.get("x-gemini-service-tier")
                    if tier_hdr:
                        self.server_tier_detected = str(tier_hdr).strip()

                    # Ghi nhận usage request & tokens
                    usage_meta = res_json.get("usageMetadata", {})
                    tot_tokens = usage_meta.get("totalTokenCount", 0)
                    self.record_usage(model, tot_tokens)
                    
                    return True, json.loads(text)
                elif r.status_code == 429:
                    is_rate_limited = True
                    # Đọc Retry-After header nếu có
                    retry_hdr = r.headers.get("Retry-After")
                    if retry_hdr and retry_hdr.isdigit():
                        retry_seconds = int(retry_hdr)
                    last_err = f"Google báo 429: Quá giới hạn tốc độ (Rate Limit). Vui lòng đợi ~{retry_seconds}s hoặc đổi sang Gemini Flash."
                    continue
                elif r.status_code in [503, 404]:
                    last_err = f"Model {model} quá tải ({r.status_code})"
                    continue
                else:
                    return False, f"Lỗi Google API ({r.status_code}): {r.text[:150]}"
            except Exception as e:
                last_err = str(e)
                continue

        if is_rate_limited:
            return False, f"Tài khoản Google đang chạm giới hạn tốc độ (Rate Limit 429). Hãy đợi khoảng {retry_seconds} giây rồi bấm lại nhé!"
        return False, f"Tất cả các model AI đều bận hoặc lỗi kết nối ({last_err})"

    def check_status(self) -> Dict[str, Any]:
        usage_info = self.get_usage_stats()
        if not self.is_configured():
            return {
                "configured": False,
                "has_key": False,
                "status": "needs_key",
                "message": "Chưa cấu hình Gemini API Key",
                "usage": usage_info
            }
        
        # Tao chuoi masked an toan: vi du "AQ.Ab8...FVWQ"
        k = self.api_key
        masked_k = f"{k[:6]}••••••••{k[-4:]}" if len(k) > 12 else "••••••••••••"

        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={self.api_key}"
        try:
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                return {
                    "configured": True,
                    "has_key": True,
                    "masked_key": masked_k,
                    "status": "ready",
                    "model": self.model_name,
                    "billing_tier": self.billing_tier,
                    "custom_rpd_limit": self.custom_rpd_limit,
                    "message": "AI Vision sẵn sàng hoạt động (Gemini Flash)",
                    "usage": usage_info
                }
            else:
                return {
                    "configured": False,
                    "has_key": True,
                    "masked_key": masked_k,
                    "status": "error",
                    "message": f"API Key không hợp lệ ({r.status_code})",
                    "usage": usage_info
                }
        except Exception as e:
            return {
                "configured": False,
                "status": "network_error",
                "message": f"Lỗi mạng: {str(e)}",
                "usage": usage_info
            }

    def inspect_crop(self, image_path_or_bytes, raw_ocr_hint: str = "") -> Dict[str, Any]:
        if isinstance(image_path_or_bytes, str):
            with open(image_path_or_bytes, "rb") as f:
                img_bytes = f.read()
        else:
            img_bytes = image_path_or_bytes

        # Tối ưu hóa ảnh crop nhỏ trước khi gửi
        b64_data, mime_type = optimize_image_for_gemini(img_bytes, max_dim=800, quality=90)

        prompt = f"""Thẩm định kích thước bản vẽ cơ khí (GD&T, ISO). Gợi ý OCR: "{raw_ocr_hint}".
Trả về JSON ngắn gọn:
{{
  "nominal": float hoặc null,
  "nominal_str": "string",
  "upper_tol": "string",
  "lower_tol": "string",
  "qty": "string",
  "prefix": "string",
  "suffix": "string",
  "tol_type": "string",
  "full_callout": "string",
  "explanation": "string ngắn 1 dòng"
}}"""

        ok, res = self._request_gemini(prompt, b64_data, mime_type=mime_type, timeout=25)
        if ok:
            res["success"] = True
            res["source"] = f"ai_vision_{self.model_name}"
            return res
        else:
            return {"success": False, "error": str(res)}

    def auto_detect_dimensions(self, image_path_or_bytes, page_width: int, page_height: int) -> Dict[str, Any]:
        if isinstance(image_path_or_bytes, str):
            with open(image_path_or_bytes, "rb") as f:
                img_bytes = f.read()
        else:
            img_bytes = image_path_or_bytes

        # Tối ưu hóa ảnh toàn trang: Resize max 1600px, nén JPEG 85% để giảm 70% input token!
        b64_data, mime_type = optimize_image_for_gemini(img_bytes, max_dim=1600, quality=85)

        # Prompt tinh gọn tối đa để giảm thiểu Output Tokens
        prompt = """Phát hiện TẤT CẢ các cụm ghi kích thước và dung sai cơ khí (dimensions, tolerances, R, C, Ø, góc độ) trên trang bản vẽ này.
Khoanh vùng bounding box [ymin, xmin, ymax, xmax] theo thang 0-1000.
Trả về JSON ngắn gọn:
{
  "dimensions": [
    {
      "box_2d": [ymin, xmin, ymax, xmax],
      "label": "chữ số đọc được"
    }
  ]
}"""

        ok, res = self._request_gemini(prompt, b64_data, mime_type=mime_type, timeout=40)
        if ok:
            raw_dims = res.get("dimensions", [])
            boxes = []
            for item in raw_dims:
                b2d = item.get("box_2d", [])
                if len(b2d) == 4:
                    ymin, xmin, ymax, xmax = b2d
                    norm_x = max(0.0, xmin / 1000.0)
                    norm_y = max(0.0, ymin / 1000.0)
                    norm_w = min(1.0, (xmax - xmin) / 1000.0)
                    norm_h = min(1.0, (ymax - ymin) / 1000.0)

                    # Bỏ qua các box quá nhỏ hoặc quá lớn
                    if norm_w < 0.005 or norm_h < 0.005 or norm_w > 0.6 or norm_h > 0.6:
                        continue

                    px_x = norm_x * page_width
                    px_y = norm_y * page_height
                    px_w = norm_w * page_width
                    px_h = norm_h * page_height

                    boxes.append({
                        "label": item.get("label", ""),
                        "crop_box": {
                            "x": norm_x,
                            "y": norm_y,
                            "width": norm_w,
                            "height": norm_h
                        },
                        "box": {
                            "x": px_x,
                            "y": px_y,
                            "w": px_w,
                            "h": px_h
                        }
                    })
            return {
                "success": True,
                "count": len(boxes),
                "dimensions": boxes
            }
        else:
            return {"success": False, "error": str(res)}


global_ai_vision_service = AIVisionService()

