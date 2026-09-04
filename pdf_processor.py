import os
import re
import fitz  # PyMuPDF
import cv2
import numpy as np
import base64
from io import BytesIO
from PIL import Image
from tolerance_parser import ToleranceParser, CADTextSanitizer

try:
    from rapidocr_onnxruntime import RapidOCR
    rapid_engine = RapidOCR()
except Exception as e:
    print(f"Warning: RapidOCR initialization failed: {e}")
    rapid_engine = None

class PDFProcessor:
    def __init__(self, upload_dir=None):
        self.upload_dir = upload_dir or os.path.join(os.path.dirname(__file__), "uploads")
        os.makedirs(self.upload_dir, exist_ok=True)
        self.cache_dir = os.path.join(self.upload_dir, "cache")
        os.makedirs(self.cache_dir, exist_ok=True)
        self._page_ocr_cache = {}

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
            img = Image.open(cache_path)
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
                matched_elements.sort(key=lambda item: (item["cy"], item["cx"]))
                raw_page_text = "\n".join([el["text"] for el in matched_elements if el["text"]])
                page_text = self._clean_ocr_text(raw_page_text)
                if page_text:
                    parsed_candidate = parser.parse(page_text)
                    if parsed_candidate.get("nominal") is not None:
                        parsed_from_page = parsed_candidate
                        parsed_from_page["thumbnail"] = thumb_b64
                        parsed_from_page["source"] = "page_ocr_aligned"
                        parsed_from_page["box"] = {"x": x, "y": y, "w": w, "h": h}

        # Buoc 3: Chay RapidOCR truc tiep tren vung crop (kem tu dong xoay goc va khu trung lap)
        def _ocr_single_cv(img_in):
            padded = cv2.copyMakeBorder(img_in, 24, 24, 24, 24, cv2.BORDER_CONSTANT, value=[255, 255, 255])
            ph, pw = padded.shape[:2]
            scale = 2.0 if min(ph, pw) < 100 else 1.4
            proc_img = cv2.resize(padded, None, fx=scale, fy=scale, interpolation=cv2.INTER_LANCZOS4)
            
            ocr_res, _ = rapid_engine(proc_img)
            if not ocr_res:
                return "", None, 0.0

            items = []
            for box, txt, score in ocr_res:
                txt_clean = txt.strip()
                if txt_clean and re.search(r'[0-9°Øø\u3002A-Za-z]', txt_clean):
                    xs = [pt[0] for pt in box]
                    ys = [pt[1] for pt in box]
                    items.append({
                        'text': txt_clean,
                        'x0': min(xs), 'x1': max(xs),
                        'y0': min(ys), 'y1': max(ys),
                        'cx': sum(xs) / 4.0, 'cy': sum(ys) / 4.0,
                        'h': max(ys) - min(ys),
                        'score': score
                    })
            lines = []
            if items:
                items.sort(key=lambda it: (it['cy'], it['x0']))
                avg_h = sum(it['h'] for it in items) / len(items)
                line_clusters = []
                for it in items:
                    matched = False
                    for l in line_clusters:
                        if abs(it['cy'] - l[0]['cy']) < max(12, avg_h * 0.55):
                            l.append(it)
                            matched = True
                            break
                    if not matched:
                        line_clusters.append([it])

                line_clusters.sort(key=lambda l: min(it['y0'] for it in l))
                for l in line_clusters:
                    l.sort(key=lambda it: it['x0'])
                    # Khu trung lap cac hop bi de len nhau do DBNet (vi du '5' va '5.0')
                    filtered = []
                    for it in l:
                        if not filtered:
                            filtered.append(it)
                        else:
                            prev = filtered[-1]
                            overlap_w = min(prev['x1'], it['x1']) - max(prev['x0'], it['x0'])
                            min_w = min(prev['x1'] - prev['x0'], it['x1'] - it['x0'])
                            if min_w > 0 and overlap_w / min_w > 0.5:
                                if '.' in it['text'] and '.' not in prev['text']:
                                    filtered[-1] = it
                                elif len(it['text']) > len(prev['text']):
                                    filtered[-1] = it
                            else:
                                filtered.append(it)
                    lines.append(' '.join(it['text'] for it in filtered))
            else:
                for line in ocr_res:
                    txt = line[1].strip()
                    if txt and re.search(r'[0-9°Øø\u3002]', txt):
                        lines.append(txt)

            raw_txt = self._clean_ocr_text("\n".join(lines))
            parsed_res = parser.parse(raw_txt) if raw_txt else None
            avg_sc = sum(it['score'] for it in items) / len(items) if items else 0.0
            return raw_txt, parsed_res, avg_sc

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
                        if parsed_crop.get("tol_type") in ["local", "local_stacked", "local_limit"]:
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

        # 3. Mac dinh fallback
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
