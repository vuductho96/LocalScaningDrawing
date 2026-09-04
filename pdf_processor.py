import os
import fitz  # PyMuPDF
import cv2
import numpy as np
import base64
from io import BytesIO
from PIL import Image
from tolerance_parser import ToleranceParser

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

    def render_page(self, pdf_path, page_num=0, dpi=200):
        """
        Render trang PDF ra anh voi DPI cao (mac dinh 200-300 DPI de net cao).
        Tra ve duong dan anh cache va kich thuoc anh.
        """
        base_name = os.path.splitext(os.path.basename(pdf_path))[0]
        cache_filename = f"{base_name}_p{page_num}_dpi{dpi}.png"
        cache_path = os.path.join(self.cache_dir, cache_filename)

        if os.path.exists(cache_path):
            img = Image.open(cache_path)
            return cache_path, img.width, img.height

        doc = fitz.open(pdf_path)
        if page_num < 0 or page_num >= len(doc):
            page_num = 0
        page = doc[page_num]

        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        pix.save(cache_path)
        w, h = pix.width, pix.height
        doc.close()

        return cache_path, w, h

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
                    xs = [pt[0] for pt in box]
                    ys = [pt[1] for pt in box]
                    elements.append({
                        "text": text.strip(),
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

    def crop_and_extract(self, pdf_path, page_num, crop_box, global_constraints=None, dpi=200):
        """
        crop_box: { "x": float, "y": float, "width": float, "height": float }
        Toa do chuan hoa tu 0.0 den 1.0 relative tren toan trang.
        """
        cache_path, img_w, img_h = self.render_page(pdf_path, page_num=page_num, dpi=dpi)
        
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

        # Tao thumbnail base64
        _, buffer = cv2.imencode('.png', crop_cv)
        thumb_b64 = "data:image/png;base64," + base64.b64encode(buffer).decode('utf-8')

        parser = ToleranceParser(global_constraints=global_constraints)

        # Buoc 1: Kiem tra Vector Text trong PDF (neu co)
        vector_text = ""
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

        # Buoc 2: Su dung Whole Page OCR Cache (do nguyen tu hoan chinh, khong bi cat ngang chu)
        page_elements = self._get_page_ocr_elements(cache_path)
        matched_elements = []
        margin = 8
        for el in page_elements:
            # Neu tam hoac hop nam trong crop box
            if (x - margin <= el["cx"] <= x + w + margin) and (y - margin <= el["cy"] <= y + h + margin):
                matched_elements.append(el)

        parsed_from_page = None
        if matched_elements:
            # Sap xep tu tren xuong duoi, trai sang phai
            matched_elements.sort(key=lambda item: (item["cy"], item["cx"]))
            page_text = "\n".join([el["text"] for el in matched_elements if el["text"]])
            parsed_candidate = parser.parse(page_text)
            if parsed_candidate.get("nominal") is not None:
                parsed_from_page = parsed_candidate
                parsed_from_page["thumbnail"] = thumb_b64
                parsed_from_page["source"] = "page_ocr_aligned"
                parsed_from_page["box"] = {"x": x, "y": y, "w": w, "h": h}

        # Buoc 3: Chay RapidOCR truc tiep tren vung crop (phong to de bat chi tiet cuc nho)
        ocr_text = ""
        ocr_lines = []
        if rapid_engine is not None and crop_cv.size > 0:
            min_dim = min(w, h)
            scale = 1.0
            if min_dim < 60:
                scale = 3.0
            elif min_dim < 120:
                scale = 2.0

            if scale > 1.0:
                proc_img = cv2.resize(crop_cv, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
            else:
                proc_img = crop_cv

            try:
                ocr_result, _ = rapid_engine(proc_img)
                if ocr_result:
                    for line in ocr_result:
                        txt = line[1].strip()
                        if txt:
                            ocr_lines.append(txt)
                    ocr_text = "\n".join(ocr_lines)

                # Neu vung crop co chieu cao lon hon chieu rong dang ke (chu dung doc)
                # hoac chua doc duoc chu so nao, thu xoay 90 do va 270 do
                if (h > w * 1.3) or not any(c.isdigit() for c in ocr_text):
                    best_text = ocr_text
                    best_parsed = parser.parse(ocr_text) if ocr_text else None
                    
                    # Thu xoay 90 do nguoc chieu kim dong ho (CCW)
                    img_ccw = cv2.rotate(proc_img, cv2.ROTATE_90_COUNTERCLOCKWISE)
                    res_ccw, _ = rapid_engine(img_ccw)
                    if res_ccw:
                        txt_ccw = "\n".join([line[1].strip() for line in res_ccw if line[1].strip()])
                        p_ccw = parser.parse(txt_ccw)
                        if p_ccw.get("nominal") is not None:
                            if not best_parsed or best_parsed.get("nominal") is None or p_ccw.get("tol_type") != "global":
                                ocr_text = txt_ccw
                                best_parsed = p_ccw

                    # Thu xoay 90 do theo chieu kim dong ho (CW)
                    img_cw = cv2.rotate(proc_img, cv2.ROTATE_90_CLOCKWISE)
                    res_cw, _ = rapid_engine(img_cw)
                    if res_cw:
                        txt_cw = "\n".join([line[1].strip() for line in res_cw if line[1].strip()])
                        p_cw = parser.parse(txt_cw)
                        if p_cw.get("nominal") is not None:
                            if not best_parsed or best_parsed.get("nominal") is None or p_cw.get("tol_type") != "global":
                                ocr_text = txt_cw
            except Exception as e:
                print(f"RapidOCR error: {e}")

        parsed_crop = parser.parse(ocr_text) if ocr_text else None

        # Uu tien ket qua:
        # 1. Neu Page OCR ra ket qua chuan:
        if parsed_from_page and parsed_from_page.get("nominal") is not None:
            # Neu crop OCR cung ra ket qua, kiem tra xem crop OCR co thuc su dang tin cay hon khong
            if parsed_crop and parsed_crop.get("nominal") is not None:
                # Neu ca hai deu co nominal giong nhau hoac rat gan nhau:
                nom_p = parsed_from_page.get("nominal")
                nom_c = parsed_crop.get("nominal")
                if abs(nom_p - nom_c) < 0.05:
                    # Neu crop OCR phat hien dung sai rieng hop ly (vi du co dau +- hoac stacked ro rang)
                    if parsed_crop.get("tol_type") in ["local", "local_stacked", "local_limit"]:
                        return parsed_crop
                # Neu page OCR co so nguyen ven (khong bi chia cat thanh nhieu so le), uu tien page OCR
                return parsed_from_page
            return parsed_from_page

        if parsed_crop and parsed_crop.get("nominal") is not None:
            parsed_crop["thumbnail"] = thumb_b64
            parsed_crop["source"] = "rapid_ocr_crop"
            parsed_crop["box"] = {"x": x, "y": y, "w": w, "h": h}
            return parsed_crop

        # Mac dinh fallback
        candidate_text = ocr_text if ocr_text else (vector_text if vector_text else "")
        parsed = parser.parse(candidate_text)
        parsed["thumbnail"] = thumb_b64
        parsed["source"] = "rapid_ocr" if ocr_text else "fallback"
        parsed["box"] = {"x": x, "y": y, "w": w, "h": h}
        return parsed
