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

# Quota mac dinh cua goi Gemini Free Tier:
# - RPD (Requests Per Day): 1500 yeu cau / ngay
# - RPM (Requests Per Minute): 15 yeu cau / phut
# - TPM (Tokens Per Minute): 1,000,000 tokens / phut
DEFAULT_FREE_QUOTA = {
    "rpd_limit": 1500,  # 1500 requests/day
    "rpm_limit": 15,    # 15 requests/minute
    "tpm_limit": 1000000 # 1M tokens/minute
}

CANDIDATE_MODELS = [
    "gemini-flash-latest",
    "gemini-2.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.6-flash"
]

class AIVisionService:
    def __init__(self):
        self.api_key = os.environ.get("GEMINI_API_KEY", "")
        self.model_name = CANDIDATE_MODELS[0]
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

    def save_config(self, api_key: str, model_name: Optional[str] = None):
        self.api_key = api_key.strip()
        if model_name:
            self.model_name = model_name.strip()
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump({
                    "api_key": self.api_key,
                    "model_name": self.model_name
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

        rpd_limit = DEFAULT_FREE_QUOTA["rpd_limit"]
        rpm_limit = DEFAULT_FREE_QUOTA["rpm_limit"]

        rpd_used = day_stats["requests"]
        rpm_used = min_stats["requests"]

        percent_rpd = min(100.0, round((rpd_used / rpd_limit) * 100, 1))
        percent_rpm = min(100.0, round((rpm_used / rpm_limit) * 100, 1))

        return {
            "configured": self.is_configured(),
            "model": self.model_name,
            "day_key": day_key,
            "rpd_used": rpd_used,
            "rpd_limit": rpd_limit,
            "rpd_remaining": max(0, rpd_limit - rpd_used),
            "percent_rpd": percent_rpd,
            "rpm_used": rpm_used,
            "rpm_limit": rpm_limit,
            "rpm_remaining": max(0, rpm_limit - rpm_used),
            "percent_rpm": percent_rpm,
            "day_tokens": day_stats.get("tokens", 0),
            "models_used": day_stats.get("models", {})
        }

    def _request_gemini(self, prompt: str, image_b64: Optional[str] = None, timeout: int = 25) -> Tuple[bool, Any]:
        if not self.is_configured():
            return False, "Chưa cấu hình Gemini API Key"

        # Danh sách model thử nghiệm (ưu tiên model_name hiện tại)
        models_to_try = [self.model_name] + [m for m in CANDIDATE_MODELS if m != self.model_name]

        parts = [{"text": prompt}]
        if image_b64:
            parts.append({
                "inline_data": {
                    "mime_type": "image/png",
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
        for model in models_to_try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.api_key}"
            try:
                r = requests.post(url, json=payload, timeout=timeout)
                if r.status_code == 200:
                    res_json = r.json()
                    text = res_json["candidates"][0]["content"]["parts"][0]["text"]
                    self.model_name = model  # Giữ lại model thành công
                    
                    # Ghi nhận usage request & tokens
                    usage_meta = res_json.get("usageMetadata", {})
                    tot_tokens = usage_meta.get("totalTokenCount", 0)
                    self.record_usage(model, tot_tokens)
                    
                    return True, json.loads(text)
                elif r.status_code in [503, 404, 429]:
                    last_err = f"Model {model} quá tải ({r.status_code})"
                    continue
                else:
                    return False, f"Lỗi Google API ({r.status_code}): {r.text[:150]}"
            except Exception as e:
                last_err = str(e)
                continue

        return False, f"Tất cả các model AI đều bận hoặc lỗi kết nối ({last_err})"

    def check_status(self) -> Dict[str, Any]:
        usage_info = self.get_usage_stats()
        if not self.is_configured():
            return {
                "configured": False,
                "status": "needs_key",
                "message": "Chưa cấu hình Gemini API Key",
                "usage": usage_info
            }
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={self.api_key}"
        try:
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                return {
                    "configured": True,
                    "status": "ready",
                    "model": self.model_name,
                    "message": "AI Vision sẵn sàng hoạt động (Gemini Flash)",
                    "usage": usage_info
                }
            else:
                return {
                    "configured": False,
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

        b64_data = base64.b64encode(img_bytes).decode("utf-8")

        prompt = f"""Bạn là chuyên gia thẩm định kích thước bản vẽ cơ khí (GD&T, ISO, ASME Y14.5).
Hãy nhìn ảnh cắt và giải mã chính xác các thông số kích thước:
- Gợi ý từ OCR cục bộ: "{raw_ocr_hint}"

Yêu cầu:
1. nominal: Số danh nghĩa thực (ví dụ: 57.51, 39.4, 0.20). Nếu là góc độ hoặc chữ thuần túy thì null.
2. nominal_str: Chuỗi danh nghĩa (ví dụ: "57.51", "4°30'23\"", "R0.20", "2-C0.20").
3. upper_tol: Dung sai trên kèm dấu (+0.005, +0.01, 0).
4. lower_tol: Dung sai dưới kèm dấu (-0.005, -0.01, 0).
5. qty: Số lượng (ví dụ "2", "4").
6. prefix: Ký hiệu (R, C, Ø, M, ...).
7. suffix: Hậu tố (THRU, DP, ...).
8. tol_type: Loại dung sai ('symmetric', 'stacked', 'angle', 'local').
9. full_callout: Chuỗi kích thước đầy đủ (ví dụ "57.51 ±0.005", "2-C0.20 ±0.05", "R0.20").
10. explanation: Giải thích ngắn 1 câu.

Trả về JSON:
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
  "explanation": "string"
}}"""

        ok, res = self._request_gemini(prompt, b64_data, timeout=25)
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

        b64_data = base64.b64encode(img_bytes).decode("utf-8")

        prompt = """Bạn là hệ thống AI phân tích bản vẽ kỹ thuật cơ khí.
Nhiệm vụ: Phát hiện TẤT CẢ các cụm ghi chú kích thước và dung sai (dimensions, tolerances, callouts, R, C, Ø, góc độ) trên toàn bộ trang bản vẽ này.

Với mỗi kích thước, hãy khoanh vùng ô chữ nhật bao quanh chính xác cụm chữ/số đó.
Tọa độ bounding box định dạng [ymin, xmin, ymax, xmax] theo thang điểm từ 0 đến 1000.

Trả về JSON:
{
  "dimensions": [
    {
      "box_2d": [ymin, xmin, ymax, xmax],
      "label": "Kích thước đọc được sơ bộ"
    }
  ]
}"""

        ok, res = self._request_gemini(prompt, b64_data, timeout=40)
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
