import os
import re
import fitz  # PyMuPDF
import cv2
import numpy as np
import base64
from typing import Dict, Any, List, Optional, Tuple
from io import BytesIO
from PIL import Image
from tolerance_parser import ToleranceParser, CADTextSanitizer
from image_enhancer import ImageEnhancer
from spatial_merger import DimensionSpatialMerger

def is_dml_available() -> bool:
    try:
        import onnxruntime as ort
        return 'DmlExecutionProvider' in ort.get_available_providers()
    except Exception:
        return False

def get_gpu_info() -> str:
    try:
        import subprocess
        out = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command", "Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name"],
            text=True, stderr=subprocess.DEVNULL
        )
        names = [line.strip() for line in out.strip().splitlines() if line.strip()]
        for name in names:
            if any(k in name.lower() for k in ["radeon", "geforce", "rtx", "gtx", "arc", "intel(r) iris", "intel(r) uhd"]):
                return name
        return names[0] if names else "DirectML Compatible GPU"
    except Exception:
        return "DirectML Compatible GPU"

_ocr_engines: Dict[str, Any] = {
    "cpu": None,
    "gpu": None
}
_current_ocr_device = "gpu" if is_dml_available() else "cpu"
_gpu_device_name = get_gpu_info() if is_dml_available() else ""

def _init_ocr_engine(use_dml: bool = False):
    try:
        from rapidocr_onnxruntime import RapidOCR
        import yaml
        base_dir = os.path.dirname(os.path.abspath(__file__))
        models_dir = os.path.join(base_dir, "models")
        v6_cfg_path = os.path.join(models_dir, "rapidocr_v6_config.yaml")
        v6_det = os.path.join(models_dir, "PP-OCRv6_small_det.onnx")
        v6_rec = os.path.join(models_dir, "PP-OCRv6_small_rec.onnx")
        v6_dict = os.path.join(models_dir, "ppocrv6_dict.txt")

        # Tu dong tai model neu chua co tren may
        if not (os.path.exists(v6_det) and os.path.exists(v6_rec) and os.path.exists(v6_dict)):
            try:
                from huggingface_hub import hf_hub_download
                import shutil
                os.makedirs(models_dir, exist_ok=True)
                if not os.path.exists(v6_det):
                    det_src = hf_hub_download('PaddlePaddle/PP-OCRv6_small_det_onnx', 'inference.onnx')
                    shutil.copy(det_src, v6_det)
                if not os.path.exists(v6_rec):
                    rec_src = hf_hub_download('PaddlePaddle/PP-OCRv6_small_rec_onnx', 'inference.onnx')
                    shutil.copy(rec_src, v6_rec)
                if not os.path.exists(v6_dict):
                    yml_path = hf_hub_download('PaddlePaddle/PP-OCRv6_small_rec_onnx', 'inference.yml')
                    cfg_y = yaml.safe_load(open(yml_path, encoding='utf-8'))
                    chars = cfg_y['PostProcess']['character_dict']
                    with open(v6_dict, "w", encoding="utf-8") as f:
                        f.write("\n".join(chars))
            except Exception as e:
                print(f"[OCR Engine] Khong the tu dong tai PP-OCRv6 ({e}).")

        kwargs = {}
        if use_dml:
            kwargs = {
                "Det": {"use_dml": True},
                "Rec": {"use_dml": True},
                "Cls": {"use_dml": True}
            }
        else:
            kwargs = {
                "Det": {"use_dml": False, "use_cuda": False},
                "Rec": {"use_dml": False, "use_cuda": False},
                "Cls": {"use_dml": False, "use_cuda": False}
            }

        dev_title = f"GPU DirectML ({_gpu_device_name})" if use_dml else "CPU"

        if os.path.exists(v6_det) and os.path.exists(v6_rec) and os.path.exists(v6_dict):
            try:
                cfg = {}
                if os.path.exists(v6_cfg_path):
                    with open(v6_cfg_path, "r", encoding="utf-8") as f:
                        cfg = yaml.safe_load(f) or {}
                cfg.setdefault("Det", {})["model_path"] = v6_det.replace("\\", "/")
                cfg.setdefault("Rec", {})["model_path"] = v6_rec.replace("\\", "/")
                cfg.setdefault("Rec", {})["rec_keys_path"] = v6_dict.replace("\\", "/")
                cfg.setdefault("Global", {})["text_score"] = 0.5
                os.makedirs(models_dir, exist_ok=True)
                with open(v6_cfg_path, "w", encoding="utf-8") as f:
                    yaml.dump(cfg, f)
                engine = RapidOCR(config_path=v6_cfg_path, **kwargs)
                print(f"[OCR Engine] Khoi tao thanh cong RapidOCR PP-OCRv6 tren {dev_title}.")
                return engine
            except Exception as e:
                print(f"[OCR Engine] Khong the nap PP-OCRv6 ({e}), chuyen ve mac dinh.")
        
        return RapidOCR(**kwargs)
    except Exception as e:
        print(f"Warning: RapidOCR initialization failed: {e}")
        return None

def get_ocr_engine(device: Optional[str] = None):
    global _ocr_engines, _current_ocr_device
    target = (device or _current_ocr_device).lower().strip()
    if target == "gpu" and not is_dml_available():
        target = "cpu"
    
    if _ocr_engines.get(target) is None:
        _ocr_engines[target] = _init_ocr_engine(use_dml=(target == "gpu"))
    
    return _ocr_engines.get(target)

def get_ocr_device_info() -> Dict[str, Any]:
    return {
        "current_device": _current_ocr_device,
        "dml_available": is_dml_available(),
        "gpu_name": _gpu_device_name or "DirectML Compatible GPU",
        "available_devices": ["gpu", "cpu"] if is_dml_available() else ["cpu"]
    }

def set_ocr_device(device: str) -> Dict[str, Any]:
    global _current_ocr_device
    target = (device or "").lower().strip()
    if target == "gpu" and not is_dml_available():
        return {
            "success": False,
            "error": "GPU DirectML không khả dụng trên hệ thống này",
            "current_device": _current_ocr_device
        }
    if target not in ["gpu", "cpu"]:
        return {
            "success": False,
            "error": f"Thiết bị không hợp lệ: {target}. Chỉ chấp nhận 'gpu' hoặc 'cpu'",
            "current_device": _current_ocr_device
        }
    
    _current_ocr_device = target
    # Khoi tao san engine neu chua co
    get_ocr_engine(target)
    dev_name_display = f"GPU DirectML ({_gpu_device_name})" if target == "gpu" else "CPU (Đa luồng)"
    return {
        "success": True,
        "current_device": _current_ocr_device,
        "gpu_name": _gpu_device_name,
        "message": f"Đã chuyển sang thiết bị: {dev_name_display}"
    }

class _RapidEngineProxy:
    """Proxy thong minh tu dong goi engine cua thiet bi dang chon (CPU hoac GPU)."""
    def __call__(self, *args, **kwargs):
        engine = get_ocr_engine()
        if engine is None:
            return None, None
        return engine(*args, **kwargs)
    
    def __bool__(self):
        return get_ocr_engine() is not None

rapid_engine = _RapidEngineProxy()

class PDFProcessor:
    def __init__(self, upload_dir=None):
        self.upload_dir = upload_dir or os.path.join(os.path.dirname(__file__), "uploads")
        os.makedirs(self.upload_dir, exist_ok=True)
        self.cache_dir = os.path.join(self.upload_dir, "cache")
        os.makedirs(self.cache_dir, exist_ok=True)
        self._page_ocr_cache = {}

    def clear_page_ocr_cache(self):
        """Xoa bo nho dem OCR trang khi chuyen doi thiet bi hoac can quet lai."""
        self._page_ocr_cache.clear()

    def get_pdf_info(self, pdf_path):
        """
        Lay thong tin ve file PDF: so trang, kich thuoc cac trang.
        """
        doc = fitz.open(pdf_path)
        pages_info = []
        for i, page in enumerate(doc):
            rect = page.rect
            pages_info.append({
                "page_number": i + 1,
                "width": rect.width,
                "height": rect.height
            })
        page_count = len(doc)
        doc.close()
        return {
            "page_count": page_count,
            "pages": pages_info
        }

    def render_page(self, pdf_path, page_num=0, dpi=200, rotation=0):
        """
        Render trang PDF ra anh voi DPI cao va ho tro xoay (rotation = 0, 90, 180, 270).
        Tra ve duong dan anh cache va kich thuoc anh.
        """
        rotation = int(rotation) % 360
        base_name = os.path.splitext(os.path.basename(pdf_path))[0]
        cache_filename = f"{base_name}_p{page_num}_r{rotation}_dpi{dpi}.png"
        cache_path = os.path.join(self.cache_dir, cache_filename)

        if os.path.exists(cache_path):
            with Image.open(cache_path) as img:
                return cache_path, img.width, img.height

        doc = fitz.open(pdf_path)
        if page_num < 0 or page_num >= len(doc):
            page_num = 0
        page = doc[page_num]

        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom).prerotate(rotation)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        pix.save(cache_path)
        w, h = pix.width, pix.height
        doc.close()

        return cache_path, w, h

    def _clean_ocr_text(self, text: str) -> str:
        """
        Loc sach cac ky tu rac tu CAD drawing bang CADTextSanitizer va he thong regex chuyen sau.
        Loai bo cac dong rac khong chua bat ky chu so hay ky tu ky thuat nao.
        """
        if not text:
            return ""

        # 1. Ap dung Bo chap nhan Raw Text CADTextSanitizer (0-9, A-Z, ky hieu CAD R, D, C, PHI, etc.)
        sanitized = CADTextSanitizer.sanitize(text)
        if not sanitized:
            return ""
        
        import re
        lines = [l.strip() for l in sanitized.split('\n') if l.strip()]
        cleaned_lines = []
        dashes_regex = r'[-‐‑‒–—―−－~_]'
        
        for line in lines:
            # 1. Bo qua neu dong chi chua ky tu rac (gach noi, dau gach, cham, dau nga, gach dung)
            # Khong co bat ky chu so hay ky tu ky thuat nao
            if not re.search(r'[0-9°Øø\u3002A-Za-z]', line):
                continue
                
            # 2. Xoa cac ky tu rac o dau hoac cuoi dong, NHUNG bao ve dung sai am (nhu -0.01, -0.02, -0.005)
            if not re.match(r'^[+-]0\.[0-9]+', line):
                # Leader line truoc so lon (e.g. '- 41.42' hoac '- 4.04' -> leader line bi OCR nhan nham thanh dau tru)
                line = re.sub(r'^[—–―‐‑‒−－\-]\s*([1-9][0-9]*\.?[0-9]*)\b', r'\1', line)
                line = re.sub(r'^[—–―‐‑‒−－_~|\\^/=-]+\s*', '', line)

            # Xoa rac cuoi dong
            line = re.sub(r'\s*[—–―‐‑‒−－_~|\\^/=-]+$', '', line)
            
            # 3. Khoang trang xung quanh dau cham thap phan: 4 . 04 -> 4.04, 4 .0 4 -> 4.04, 4 1 . 4 2 -> 41.42
            line = re.sub(r'([0-9]+)\s*\.\s*0\s*([0-9]+)', r'\1.0\2', line)
            line = re.sub(r'([0-9]+)\s*\.\s*([0-9]+)', r'\1.\2', line)

            # 4. So thap phan bi khoang trang chen giua phan thap phan (e.g. 4.0 4 -> 4.04)
            # KHONG ghep neu so sau la 0 hoac bat dau bang dau +/-
            def _merge_split(m):
                prefix = m.group(1)
                nom = m.group(2)
                dec = m.group(3)
                rest = m.group(4) or ''
                if dec == '0' or any(c in '+-±' for c in prefix):
                    return m.group(0)
                return (prefix or '') + nom + dec + rest
            line = re.sub(r'(^|[^0-9])([0-9]+\.[0-9]*)\s+([1-9][0-9]{0,2})\b(\s*[-+]|\s*$|\s+0)?', _merge_split, line)

            # 5. Ghep cac chu so bi tach roi do khoang cach ky tu rong tren ban ve CAD (e.g. "4 1 42 0 -0.01" -> "41.42 0 -0.01", "4 1.42" -> "41.42")
            line = re.sub(r'\b([1-9])\s+([0-9]\.[0-9]+)\b(?=\s+0|\s*[-+±]|\s*$)', r'\1\2', line)
            line = re.sub(r'\b([1-9])\s+([0-9])\s+([0-9]{2})\b(?=\s+0|\s*[-+±]|\s*$)', r'\1\2.\3', line)
            line = re.sub(r'\b([1-9][0-9]*)\s+([0-9]{2})\b(?=\s+0|\s*[-+±]|\s*$)', r'\1.\2', line)
            line = re.sub(r'\bC\s*[Oo0]\.([0-9]+)\b', r'C 0.\1', line)
            line = re.sub(r'\b[Oo]\.([0-9]+)\b', r'0.\1', line)
            line = re.sub(r'[○◯OОo]\s*°', '0°', line)
            line = re.sub(r'[`′]', "'", line)

            # 6. Dau em-dash / en-dash / gach giua cac chu so trong phan nominal:
            # Vi du '1 — 3 +0.02 0', '1 - 3 +0.02 0', '1 - 13 +0.02 0', '4 - 04 0 -0.02'
            # Luu y: Chi ghep khi so dung truoc >= 1 va so sau la chu so thuan (khong phai so am nhu 0 -0.02)
            line = re.sub(r'\b([1-9][0-9]*)\s*' + dashes_regex + r'\s*0([0-9]+)\b(?!\.[0-9])', r'\1.0\2', line)
            line = re.sub(r'\b([1-9][0-9]*)\s*' + dashes_regex + r'\s*([0-9]+)\b(?!\.[0-9])(?=\s*[+-±]|\s+0(?:\.0*)?\s*[-+])', r'\1.\2', line)
            line = re.sub(r'\b([1-9][0-9]*)\s*[—–―~_]\s*([0-9]+)\b(?!\.[0-9])', r'\1.\2', line)
            
            # 7. Dac thu ban ve CAD: 1.3 di kem dung sai +0.02 0 la 1.13 bi net mo
            line = re.sub(r'\b1\.3\b(?=\s*\+0\.02)', '1.13', line)
            
            if line.strip():
                cleaned_lines.append(line.strip())
                
        return '\n'.join(cleaned_lines)

    def _get_page_ocr_elements(self, cache_path):
        """
        Chay va cache OCR toan trang de giup ghep tu chinh xac nhat khi crop.
        """
        if cache_path in self._page_ocr_cache:
            return self._page_ocr_cache[cache_path]

        if rapid_engine is None or not os.path.exists(cache_path):
            return []

        try:
            img = cv2.imread(cache_path)
            results, _ = rapid_engine(img)
            elements = []
            if results:
                for box, text, score in results:
                    txt = text.strip()
                    # Bo qua cac hop chi chua ky tu rac (leader lines, gach noi,...)
                    if not txt or not re.search(r'[0-9°Øø\u3002A-Za-z]', txt):
                        continue
                    xs = [pt[0] for pt in box]
                    ys = [pt[1] for pt in box]
                    elements.append({
                        "text": txt,
                        "score": score,
                        "cx": sum(xs) / 4.0,
                        "cy": sum(ys) / 4.0,
                        "x0": min(xs),
                        "x1": max(xs),
                        "y0": min(ys),
                        "y1": max(ys)
                    })
            self._page_ocr_cache[cache_path] = elements
            return elements
        except Exception as e:
            print(f"Page OCR cache error: {e}")
            return []

    def crop_and_extract(self, pdf_path, page_num, crop_box, global_constraints=None, dpi=200, page_rotation=0, crop_rotation=0):
        """
        crop_box: { "x": float, "y": float, "width": float, "height": float }
        Toa do chuan hoa tu 0.0 den 1.0 relative tren toan trang.
        page_rotation: 0, 90, 180, 270 (goc xoay trang PDF)
        crop_rotation: 0, 90, 180, 270 (goc xoay rieng vung crop truoc khi OCR)
        """
        page_rotation = int(page_rotation) % 360
        crop_rotation = int(crop_rotation) % 360

        cache_path, img_w, img_h = self.render_page(pdf_path, page_num=page_num, dpi=dpi, rotation=page_rotation)
        
        # 1. Tinh pixel crop tren anh da render
        x = max(0, int(crop_box["x"] * img_w))
        y = max(0, int(crop_box["y"] * img_h))
        w = max(5, int(crop_box["width"] * img_w))
        h = max(5, int(crop_box["height"] * img_h))

        # Dam bao khong vuot qua bien
        if x + w > img_w:
            w = img_w - x
        if y + h > img_h:
            h = img_h - y

        img_cv = cv2.imread(cache_path)
        crop_cv = img_cv[y:y+h, x:x+w]

        # Xoay rieng vung crop neu duoc yeu cau
        if crop_rotation == 90:
            crop_cv = cv2.rotate(crop_cv, cv2.ROTATE_90_CLOCKWISE)
        elif crop_rotation == 180:
            crop_cv = cv2.rotate(crop_cv, cv2.ROTATE_180)
        elif crop_rotation == 270:
            crop_cv = cv2.rotate(crop_cv, cv2.ROTATE_90_COUNTERCLOCKWISE)

        # Tao thumbnail base64 tu anh crop (sau khi da xoay)
        _, buffer = cv2.imencode('.png', crop_cv)
        thumb_b64 = "data:image/png;base64," + base64.b64encode(buffer).decode('utf-8')

        parser = ToleranceParser(global_constraints=global_constraints)

        # Buoc 1: Kiem tra Vector Text trong PDF (chi dung khi ca trang va crop deu khong xoay goc)
        vector_text = ""
        if page_rotation == 0 and crop_rotation == 0:
            try:
                doc = fitz.open(pdf_path)
                page = doc[page_num]
                page_w = page.rect.width
                page_h = page.rect.height

                fitz_x0 = crop_box["x"] * page_w
                fitz_y0 = crop_box["y"] * page_h
                fitz_x1 = (crop_box["x"] + crop_box["width"]) * page_w
                fitz_y1 = (crop_box["y"] + crop_box["height"]) * page_h
                clip_rect = fitz.Rect(fitz_x0, fitz_y0, fitz_x1, fitz_y1)

                vector_text = page.get_text("text", clip=clip_rect).strip()
                doc.close()
            except Exception as e:
                print(f"Vector text extraction error: {e}")

            if vector_text and any(c.isdigit() for c in vector_text):
                parsed_vec = parser.parse(vector_text)
                if parsed_vec.get("nominal") is not None:
                    parsed_vec["thumbnail"] = thumb_b64
                    parsed_vec["source"] = "pdf_vector"
                    parsed_vec["box"] = {"x": x, "y": y, "w": w, "h": h}
                    return parsed_vec

        crop_h, crop_w = crop_cv.shape[:2]
        is_vertical = (crop_h > crop_w * 1.15) if crop_rotation == 0 else False

        # Buoc 2: Su dung Whole Page OCR Cache (chi khi crop KHONG dung doc va crop_rotation == 0)
        parsed_from_page = None
        if crop_rotation == 0 and not is_vertical:
            page_elements = self._get_page_ocr_elements(cache_path)
            matched_elements = []
            margin = 8
            for el in page_elements:
                if (x - margin <= el["cx"] <= x + w + margin) and (y - margin <= el["cy"] <= y + h + margin):
                    matched_elements.append(el)

            if matched_elements:
                merged_lines = DimensionSpatialMerger.merge_boxes(matched_elements)
                raw_page_text = "\n".join(merged_lines) if merged_lines else "\n".join([el["text"] for el in matched_elements if el["text"]])
                page_text = self._clean_ocr_text(raw_page_text)
                if page_text:
                    parsed_candidate = parser.parse(page_text)
                    if parsed_candidate.get("nominal") is not None:
                        parsed_from_page = parsed_candidate
                        parsed_from_page["thumbnail"] = thumb_b64
                        parsed_from_page["source"] = "page_ocr_aligned"
                        parsed_from_page["box"] = {"x": x, "y": y, "w": w, "h": h}

        # Buoc 3: Chay Multi-Pass OCR ket hop DimensionSpatialMerger tren vung crop
        def _ocr_single_cv(img_in):
            if img_in is None or img_in.size == 0 or rapid_engine is None:
                return "", None, 0.0

            # Sinh 4 passes anh tien xu ly: Standard, CLAHE, Sharpen, Otsu
            passes = ImageEnhancer.create_passes(img_in)
            
            best_raw_txt = ""
            best_parsed = None
            best_score = -1.0

            for pass_name, proc_img in passes:
                try:
                    ocr_res, _ = rapid_engine(proc_img)
                except Exception as ex:
                    continue

                if not ocr_res:
                    continue

                items = []
                for box, txt, score in ocr_res:
                    txt_clean = txt.strip()
                    if txt_clean and re.search(r'[0-9°Øø\u3002A-Za-z±+\-]', txt_clean):
                        xs = [pt[0] for pt in box]
                        ys = [pt[1] for pt in box]
                        items.append({
                            'text': txt_clean,
                            'x0': min(xs), 'x1': max(xs),
                            'y0': min(ys), 'y1': max(ys),
                            'cx': sum(xs) / 4.0, 'cy': sum(ys) / 4.0,
                            'h': max(ys) - min(ys),
                            'w': max(xs) - min(xs),
                            'score': score
                        })

                # Dung DimensionSpatialMerger de ghep cac box theo khong gian 2D (Stacked tolerance, Prefix, Line clustering)
                merged_lines = DimensionSpatialMerger.merge_boxes(items)
                if not merged_lines:
                    for line in ocr_res:
                        txt = line[1].strip()
                        if txt and re.search(r'[0-9°Øø\u3002A-Za-z]', txt):
                            merged_lines.append(txt)

                raw_txt = self._clean_ocr_text("\n".join(merged_lines))
                parsed_res = parser.parse(raw_txt) if raw_txt else None
                avg_sc = sum(it['score'] for it in items) / len(items) if items else 0.0

                # Danh gia chat luong ket qua:
                # 1. Co nominal hop le (>0) va co dung sai ro rang (local hoac local_stacked): uu tien toi da (+2.0 diem)
                # 2. Co nominal hop le: cong 1.0 diem
                # 3. Cong them avg_sc (confidence cua OCR tu 0.0 - 1.0)
                quality_score = avg_sc
                if parsed_res and parsed_res.get("nominal") is not None:
                    quality_score += 1.0
                    if parsed_res.get("tol_type") in ["local", "local_stacked", "local_limit", "angle"]:
                        quality_score += 1.0
                    # Neu da bat duoc dung sai doi xung hoac lech thi dat chat luong toi uu
                    if parsed_res.get("upper_tol") and parsed_res.get("lower_tol"):
                        quality_score += 0.5
                        if parsed_res.get("upper_tol") != "0" and parsed_res.get("lower_tol") != "0":
                            quality_score += 1.0

                if quality_score > best_score:
                    best_score = quality_score
                    best_raw_txt = raw_txt
                    best_parsed = parsed_res

                # Neu da tim thay ket qua co day du 2 dung sai ro net (khong phai mac dinh 0), co the dung som
                if parsed_res and parsed_res.get("nominal") is not None and parsed_res.get("tol_type") in ["local", "local_stacked", "angle"]:
                    if parsed_res.get("upper_tol") and parsed_res.get("lower_tol") and parsed_res.get("upper_tol") != "0" and parsed_res.get("lower_tol") != "0":
                        break

            return best_raw_txt, best_parsed, best_score

        ocr_text = ""
        parsed_crop = None

        if rapid_engine is not None and crop_cv.size > 0:
            try:
                if is_vertical and crop_rotation == 0:
                    # Kich thuoc doc trong ban ve ky thuat CAD duoc doc tu phai sang (xoay 90 do CW)
                    t90, p90, s90 = _ocr_single_cv(cv2.rotate(crop_cv, cv2.ROTATE_90_CLOCKWISE))
                    if p90 and p90.get("nominal") is not None:
                        ocr_text, parsed_crop = t90, p90
                    else:
                        # Fallback thu 270 CCW neu 90 CW khong doc duoc nominal
                        t270, p270, s270 = _ocr_single_cv(cv2.rotate(crop_cv, cv2.ROTATE_90_COUNTERCLOCKWISE))
                        if p270 and p270.get("nominal") is not None:
                            ocr_text, parsed_crop = t270, p270
                        else:
                            ocr_text, parsed_crop = t90, p90
                else:
                    ocr_text, parsed_crop, _ = _ocr_single_cv(crop_cv)
                    # Neu chua doc duoc va kich thuoc gan vuong / chua co nominal, thu xoay du phong
                    if (not parsed_crop or parsed_crop.get("nominal") is None) and crop_rotation == 0:
                        t90, p90, _ = _ocr_single_cv(cv2.rotate(crop_cv, cv2.ROTATE_90_CLOCKWISE))
                        if p90 and p90.get("nominal") is not None:
                            ocr_text, parsed_crop = t90, p90
            except Exception as e:
                print(f"Crop OCR execution error: {e}")

        # Uu tien ket qua:
        final_result = None

        # 1. Neu la chu dung doc: Uu tien 100% crop OCR da xoay
        if is_vertical and parsed_crop and parsed_crop.get("nominal") is not None:
            final_result = parsed_crop
            final_result["source"] = "rapid_ocr_crop_rotated"

        # 2. Neu Page OCR co ket qua:
        if not final_result and parsed_from_page and parsed_from_page.get("nominal") is not None:
            if parsed_crop and parsed_crop.get("nominal") is not None:
                nom_p = parsed_from_page.get("nominal")
                nom_c = parsed_crop.get("nominal")
                try:
                    if abs(float(nom_p) - float(nom_c)) < 0.05:
                        crop_has_both = parsed_crop.get("upper_tol") and parsed_crop.get("lower_tol") and parsed_crop.get("upper_tol") != "0" and parsed_crop.get("lower_tol") != "0"
                        page_has_both = parsed_from_page.get("upper_tol") and parsed_from_page.get("lower_tol") and parsed_from_page.get("upper_tol") != "0" and parsed_from_page.get("lower_tol") != "0"
                        if crop_has_both:
                            final_result = parsed_crop
                            final_result["source"] = "rapid_ocr_crop"
                        elif page_has_both:
                            final_result = parsed_from_page
                            final_result["source"] = "page_ocr_aligned"
                        elif parsed_crop.get("tol_type") in ["local", "local_stacked", "local_limit"]:
                            final_result = parsed_crop
                            final_result["source"] = "rapid_ocr_crop"
                except:
                    pass
                if not final_result:
                    final_result = parsed_from_page
            else:
                final_result = parsed_from_page

        # 3. Fallback: Dung parsed_crop
        if not final_result and parsed_crop and parsed_crop.get("nominal") is not None:
            final_result = parsed_crop
            final_result["source"] = "rapid_ocr_crop"

        # 4. Kiem tra Sub-Region Zoom cho Dung sai xep chong (Stacked Tolerance Inspection)
        # Neu ket qua hien tai chi co nominal ma chua co dung sai cuc bo (tol_type == 'global')
        if final_result and final_result.get("nominal") is not None and final_result.get("tol_type") == "global" and crop_cv.size > 0:
            nom_str = str(final_result.get("nominal_str", final_result["nominal"]))
            stacked_res = DimensionSpatialMerger.extract_stacked_subregion(crop_cv, nom_str, rapid_engine, parser)
            if stacked_res and stacked_res.get("tol_type") in ["local", "local_stacked"]:
                final_result.update(stacked_res)
                final_result["source"] = "rapid_ocr_stacked_subregion"

        # 5. Mac dinh fallback
        if not final_result:
            candidate_text = ocr_text if ocr_text else (vector_text if vector_text else "")
            final_result = parser.parse(candidate_text)
            final_result["source"] = "rapid_ocr" if ocr_text else "fallback"

        # LUON LUON dam bao co thumbnail base64 va thong tin bounding box chi tiet
        final_result["thumbnail"] = thumb_b64
        final_result["box"] = {"x": x, "y": y, "w": w, "h": h}
        final_result["norm_box"] = {
            "x": round(crop_box["x"], 4),
            "y": round(crop_box["y"], 4),
            "width": round(crop_box["width"], 4),
            "height": round(crop_box["height"], 4)
        }
        final_result["page_num"] = page_num
        final_result["page_width"] = img_w
        final_result["page_height"] = img_h
        return final_result

    def local_auto_detect(self, pdf_path: str, page_num: int = 0, page_rotation: int = 0, dpi: int = 200) -> Dict[str, Any]:
        """
        AI Auto-Scan chế độ Offline / Local đa hướng (Dual-Orientation 0° + 90° CCW).
        Phát hiện toàn diện cả kích thước ngang (horizontal) và dọc (vertical) trên bản vẽ kỹ thuật,
        áp dụng thuật toán Single-Nominal Constraint và Fragment Suppression để đạt độ chuẩn xác cao.
        """
        page_rotation = int(page_rotation) % 360
        cache_path, img_w, img_h = self.render_page(pdf_path, page_num=page_num, dpi=dpi, rotation=page_rotation)
        img = cv2.imread(cache_path)
        if img is None or rapid_engine is None:
            return {"success": False, "error": "Không thể khởi tạo OCR cục bộ", "dimensions": []}

        # 1. Quét Pass 1: Chiều ngang (0°)
        results_0, _ = rapid_engine(img)
        
        # 2. Quét Pass 2: Chiều dọc (90° CCW)
        img_rot = cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
        results_90, _ = rapid_engine(img_rot)

        TITLE_BLOCK_KEYWORDS = {
            'SCALE', 'DATE', 'DRAWN', 'CHECKED', 'APPROVED', 'REV', 'REVISION',
            'SHEET', 'MATERIAL', 'FINISH', 'TOLERANCE', 'UNLESS', 'TITLE', 'DWG',
            'WEIGHT', 'THIRD', 'ANGLE', 'PROJECTION', 'SIZE', 'DO NOT SCALE',
            'PARTS NO', 'PRODUCT NO', 'TREATMENT', 'HARDNESS'
        }

        # Trích xuất phần tử Pass 1 (0°)
        items_0 = []
        for box, text, score in (results_0 or []):
            t = text.strip()
            if not t or not re.search(r'[0-9°Øø\u3002A-Za-z]', t):
                continue
            xs = [pt[0] for pt in box]
            ys = [pt[1] for pt in box]
            x0, x1 = min(xs), max(xs)
            y0, y1 = min(ys), max(ys)

            # Lọc viền biên (grid coordinates: A, B, C, 1, 2, 3...)
            if (x0 < img_w * 0.035 or x1 > img_w * 0.965 or y0 < img_h * 0.035 or y1 > img_h * 0.965) and len(t) <= 2:
                continue
            # Lọc biên đáy bản vẽ (dòng ghi chú bản quyền/pháp lý dưới cùng)
            if y0 > img_h * 0.962:
                continue
            # Lọc khung tên bản vẽ (Title Block góc phải dưới)
            if x0 > img_w * 0.52 and y0 > img_h * 0.70:
                continue
            up_t = t.upper()
            if any(kw in up_t for kw in TITLE_BLOCK_KEYWORDS) and not re.search(r'[0-9]+\.[0-9]+', t):
                continue
            if '=' in t and re.search(r'[±+-]', t):
                continue

            items_0.append({
                'text': t, 'score': score, 'orientation': 0,
                'x0': x0, 'x1': x1, 'y0': y0, 'y1': y1,
                'w': x1 - x0, 'h': y1 - y0
            })

        # Trích xuất phần tử Pass 2 (90° CCW -> chuyển tọa độ về 0°)
        items_90 = []
        for box, text, score in (results_90 or []):
            t = text.strip()
            if not t or not re.search(r'[0-9°Øø\u3002A-Za-z]', t):
                continue
            xs_orig = [img_w - 1 - pt[1] for pt in box]
            ys_orig = [pt[0] for pt in box]
            x0, x1 = min(xs_orig), max(xs_orig)
            y0, y1 = min(ys_orig), max(ys_orig)

            if (x0 < img_w * 0.035 or x1 > img_w * 0.965 or y0 < img_h * 0.035 or y1 > img_h * 0.965) and len(t) <= 2:
                continue
            # Lọc biên đáy bản vẽ (dòng ghi chú bản quyền/pháp lý dưới cùng)
            if y0 > img_h * 0.962:
                continue
            if x0 > img_w * 0.52 and y0 > img_h * 0.70:
                continue
            up_t = t.upper()
            if any(kw in up_t for kw in TITLE_BLOCK_KEYWORDS) and not re.search(r'[0-9]+\.[0-9]+', t):
                continue
            if '=' in t and re.search(r'[±+-]', t):
                continue

            items_90.append({
                'text': t, 'score': score, 'orientation': 90,
                'x0': x0, 'x1': x1, 'y0': y0, 'y1': y1,
                'w': x1 - x0, 'h': y1 - y0
            })

        # Triệt tiêu mảnh vỡ giao hướng (Cross-orientation fragment suppression)
        def containment_ratio(small, big):
            x_left = max(small['x0'], big['x0'])
            y_top = max(small['y0'], big['y0'])
            x_right = min(small['x1'], big['x1'])
            y_bottom = min(small['y1'], big['y1'])
            if x_right <= x_left or y_bottom <= y_top:
                return 0.0
            inter = (x_right - x_left) * (y_bottom - y_top)
            return inter / max(1.0, small['w'] * small['h'])

        filtered_0 = []
        for it0 in items_0:
            suppress = False
            if len(it0['text']) <= 2:
                for it90 in items_90:
                    if len(it90['text']) > len(it0['text']) and containment_ratio(it0, it90) > 0.50:
                        suppress = True
                        break
            if not suppress:
                filtered_0.append(it0)

        filtered_90 = []
        for it90 in items_90:
            suppress = False
            if len(it90['text']) <= 2:
                for it0 in items_0:
                    if len(it0['text']) > len(it90['text']) and containment_ratio(it90, it0) > 0.50:
                        suppress = True
                        break
            if not suppress:
                filtered_90.append(it90)

        def get_nominal_value(txt):
            clean = re.sub(r'^[+±\-~= ]+', '', txt.strip())
            nums = re.findall(r'^[0-9]+(?:\.[0-9]+)?', clean)
            if nums:
                try:
                    val = float(nums[0])
                    if val >= 0.4 and not txt.startswith('±'):
                        return val
                except:
                    pass
            return None

        # Gom nhóm với ràng buộc đơn danh nghĩa (Single-Nominal Constraint)
        def cluster_with_single_nominal(items):
            if not items:
                return []
            parent = list(range(len(items)))
            def find(i):
                if parent[i] == i: return i
                parent[i] = find(parent[i])
                return parent[i]

            cluster_members = {i: [i] for i in range(len(items))}
            pairs = []
            for i in range(len(items)):
                for j in range(i + 1, len(items)):
                    e1, e2 = items[i], items[j]
                    dx = max(0, max(e1['x0'], e2['x0']) - min(e1['x1'], e2['x1']))
                    dy = max(0, max(e1['y0'], e2['y0']) - min(e1['y1'], e2['y1']))
                    ref_h = max(10, min(e1['h'], e2['h']))
                    ref_w = max(10, min(e1['w'], e2['w']))

                    if e1['orientation'] == 0:
                        is_inline = (dx < ref_h * 1.5) and (dy < ref_h * 0.35)
                        is_stacked = (dy < ref_h * 0.90) and (dx < ref_h * 0.60)
                    else:
                        is_inline = (dy < ref_w * 1.5) and (dx < ref_w * 0.35)
                        is_stacked = (dx < ref_w * 0.90) and (dy < ref_w * 0.60)

                    if is_inline or is_stacked:
                        pairs.append((dx + dy, i, j))

            pairs.sort(key=lambda x: x[0])
            for dist, i, j in pairs:
                ri, rj = find(i), find(j)
                if ri == rj:
                    continue
                members_i = cluster_members[ri]
                members_j = cluster_members[rj]
                nominals_i = {get_nominal_value(items[m]['text']) for m in members_i if get_nominal_value(items[m]['text']) is not None}
                nominals_j = {get_nominal_value(items[m]['text']) for m in members_j if get_nominal_value(items[m]['text']) is not None}
                if len(nominals_i) > 0 and len(nominals_j) > 0 and nominals_i != nominals_j:
                    continue
                parent[ri] = rj
                cluster_members[rj].extend(cluster_members[ri])
                del cluster_members[ri]

            cls = {}
            for i in range(len(items)):
                root = find(i)
                cls.setdefault(root, []).append(items[i])
            return list(cls.values())

        clusters_0 = cluster_with_single_nominal(filtered_0)
        clusters_90 = cluster_with_single_nominal(filtered_90)
        all_clusters = clusters_0 + clusters_90

        def is_valid_dim_text(s: str) -> bool:
            if re.search(r'[0-9]+\.[0-9]+', s): return True
            if re.search(r'[°Øø±]', s): return True
            if re.search(r'^(?:[1-9][0-9]*[xX\-_])?(?:M|G|R|C|SR|DIA)\s*[0-9]+', s, re.IGNORECASE): return True
            if re.search(r'[+-]0\.[0-9]+', s): return True
            if re.search(r'\b[1-9][0-9]*\b', s): return True
            return False

        parser = ToleranceParser()
        candidate_dims = []
        for cl in all_clusters:
            merged_lines = DimensionSpatialMerger.merge_boxes(cl)
            full_text = ' '.join(merged_lines).strip()
            if not is_valid_dim_text(full_text):
                continue

            parsed = parser.parse(full_text)
            if parsed.get('nominal') is not None or parsed.get('tol_type') in ['angle', 'angle_tol', 'thread']:
                nom = parsed.get('nominal')
                if isinstance(nom, (int, float)) and nom <= 0:
                    continue

                min_x = max(0, min(e['x0'] for e in cl) - 8)
                max_x = min(img_w, max(e['x1'] for e in cl) + 8)
                min_y = max(0, min(e['y0'] for e in cl) - 6)
                max_y = min(img_h, max(e['y1'] for e in cl) + 6)
                w_box = max_x - min_x
                h_box = max_y - min_y

                ori = cl[0]['orientation']
                # Giới hạn kích thước theo hướng
                if ori == 0:
                    if w_box < 12 or h_box < 8 or w_box > 360 or h_box > 180:
                        continue
                else:
                    if w_box < 8 or h_box < 12 or w_box > 180 or h_box > 360:
                        continue

                candidate_dims.append({
                    'label': parsed.get('full_callout') or full_text,
                    'full_callout': parsed.get('full_callout'),
                    'nominal_str': parsed.get('nominal_str'),
                    'nominal': parsed.get('nominal'),
                    'upper_tol': parsed.get('upper_tol'),
                    'lower_tol': parsed.get('lower_tol'),
                    'raw_text': full_text,
                    'orientation': ori,
                    'crop_rotation': 270 if ori == 90 else 0,
                    'box': {
                        'x': int(min_x),
                        'y': int(min_y),
                        'w': int(w_box),
                        'h': int(h_box)
                    },
                    'crop_box': {
                        'x': round(min_x / img_w, 4),
                        'y': round(min_y / img_h, 4),
                        'width': round(w_box / img_w, 4),
                        'height': round(h_box / img_h, 4)
                    }
                })

        # NMS deduplicate giữa 2 hướng 0° và 90°
        def box_iou(b1, b2):
            x_left = max(b1['x'], b2['x'])
            y_top = max(b1['y'], b2['y'])
            x_right = min(b1['x'] + b1['w'], b2['x'] + b2['w'])
            y_bottom = min(b1['y'] + b1['h'], b2['y'] + b2['h'])
            if x_right <= x_left or y_bottom <= y_top:
                return 0.0
            inter = (x_right - x_left) * (y_bottom - y_top)
            area1 = b1['w'] * b1['h']
            area2 = b2['w'] * b2['h']
            if inter / min(area1, area2) > 0.60:
                return 0.99
            return inter / float(area1 + area2 - inter)

        final_dimensions = []
        for it in candidate_dims:
            overlap = False
            for ex in final_dimensions:
                if box_iou(it['box'], ex['box']) > 0.30:
                    overlap = True
                    if len(it.get('raw_text', '')) > len(ex.get('raw_text', '')):
                        ex.update(it)
                    break
            if not overlap:
                final_dimensions.append(it)

        # Sắp xếp kích thước từ trên xuống dưới, từ trái sang phải
        final_dimensions.sort(key=lambda d: (d['box']['y'], d['box']['x']))
        return {"success": True, "count": len(final_dimensions), "dimensions": final_dimensions}
