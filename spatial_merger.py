import re
from typing import List, Dict, Any, Tuple

class DimensionSpatialMerger:
    """
    Module hop nhat khong gian 2D (Spatial Geometry Merger) cho cac text box OCR:
    - Nhan dien cau truc dung sai xep chong (Stacked tolerance):
        25  +0.02
            -0.01
    - Nhan dien tien to dung tach roi (Ø, R, 4X, M):
        Ø   25
    - Ghep cac text box roi rac thanh mot DimensionObject thong nhat truoc khi dua vao ToleranceParser.
    """

    @staticmethod
    def merge_boxes(ocr_results: List[Dict[str, Any]]) -> List[str]:
        """
        Nhan vao danh sach cac item OCR:
        item = {
            'text': str,
            'x0': float, 'x1': float,
            'y0': float, 'y1': float,
            'cx': float, 'cy': float,
            'h': float, 'w': float,
            'score': float
        }
        Tra ve danh sach cac chuoi kich thuoc da duoc ghep dung theo khong gian 2D.
        """
        if not ocr_results:
            return []

        # Loc cac box co chu cai, chu so hoac ky hieu ky thuat
        valid_items = []
        for it in ocr_results:
            t = it.get('text', '').strip()
            if t and re.search(r'[0-9°Øø\u3002A-Za-z±+\-]', t):
                it_copy = dict(it)
                it_copy['w'] = it_copy['x1'] - it_copy['x0']
                it_copy['h'] = it_copy['y1'] - it_copy['y0']
                it_copy['cx'] = (it_copy['x0'] + it_copy['x1']) / 2.0
                it_copy['cy'] = (it_copy['y0'] + it_copy['y1']) / 2.0
                valid_items.append(it_copy)

        if not valid_items:
            return []

        if len(valid_items) == 1:
            return [valid_items[0]['text']]

        # Pre-merge cac dau co lap (+, -, ±, em-dash) voi so dung ngay sau tren cung dong
        pre_merged = []
        skip_indices = set()
        for i, it in enumerate(valid_items):
            if i in skip_indices:
                continue
            if it['text'] in ['-', '+', '±', '—', '–', '−'] or re.match(r'^[+-]$', it['text']):
                best_j = None
                best_dy = float('inf')
                for j, it2 in enumerate(valid_items):
                    if i != j and j not in skip_indices:
                        dx = it2['x0'] - it['x1']
                        dy = abs(it['cy'] - it2['cy'])
                        line_h = max(it['h'], it2['h'])
                        if dy < line_h * 0.75 and 0 <= dx <= max(10.0, line_h * 1.5):
                            if dy < best_dy:
                                best_dy = dy
                                best_j = j
                if best_j is not None:
                    it2 = valid_items[best_j]
                    sign_char = '-' if it['text'] in ['-', '—', '–', '−'] else ('+' if it['text'] == '+' else '±')
                    new_item = {
                        'text': sign_char + it2['text'].lstrip('+-'),
                        'x0': it['x0'],
                        'y0': min(it['y0'], it2['y0']),
                        'x1': it2['x1'],
                        'y1': max(it['y1'], it2['y1']),
                        'score': (it.get('score', 1.0) + it2.get('score', 1.0)) / 2.0
                    }
                    new_item['w'] = new_item['x1'] - new_item['x0']
                    new_item['h'] = new_item['y1'] - new_item['y0']
                    new_item['cx'] = (new_item['x0'] + new_item['x1']) / 2.0
                    new_item['cy'] = (new_item['y0'] + new_item['y1']) / 2.0
                    pre_merged.append(new_item)
                    skip_indices.add(i)
                    skip_indices.add(best_j)
                else:
                    pre_merged.append(it)
            else:
                pre_merged.append(it)
        valid_items = pre_merged

        avg_h = sum(it['h'] for it in valid_items) / len(valid_items)

        # 1. Kiem tra xem co phai cau truc Stacked Tolerance khong?
        # Dac diem:
        # - Co 1 box so danh nghia lon nam ben trai (width va height tuong doi lon)
        # - Co 2 box nho nam ben phai chong len nhau theo chieu doc (y0 cua box 1 < y0 cua box 2, x0 deu o ben phai cua nominal)
        sorted_by_x = sorted(valid_items, key=lambda it: it['x0'])
        nominal_candidate = sorted_by_x[0]

        # Kiem tra cac box nam ben phai
        right_boxes = [it for it in sorted_by_x[1:] if it['x0'] >= nominal_candidate['cx']]
        
        if len(right_boxes) >= 2:
            # Sap xep 2 box theo chieu doc
            stacked_candidates = sorted(right_boxes, key=lambda it: it['cy'])
            top_box = stacked_candidates[0]
            bottom_box = stacked_candidates[1]

            # Kiem tra tinh chat xep chong:
            # 1. Hai box nam de len nhau hoac gan nhau theo chieu doc
            # 2. Chua dau + hoac - hoac so thap phan
            top_txt = top_box['text'].strip()
            bot_txt = bottom_box['text'].strip()
            
            is_tol_like = any(ch in top_txt for ch in ['+', '-', '0', '.']) and any(ch in bot_txt for ch in ['+', '-', '0', '.'])
            y_overlap_or_stacked = (bottom_box['cy'] - top_box['cy']) > 0 and (bottom_box['cy'] - top_box['cy']) < avg_h * 2.2

            if is_tol_like and y_overlap_or_stacked:
                # Ghep thanh dang: <Nominal> +<Upper> -<Lower>
                # Vi du: "25 +0.02 -0.01"
                nom_txt = nominal_candidate['text'].strip()
                merged_line = f"{nom_txt} {top_txt} {bot_txt}"
                return [merged_line]

        # 2. Neu khong phai Stacked, gom nhom theo cum dong ngang binh thuong (Line Clustering)
        line_clusters = []
        # Sap xep theo y tang dan
        sorted_by_y = sorted(valid_items, key=lambda it: (it['cy'], it['x0']))
        
        for it in sorted_by_y:
            matched = False
            for l in line_clusters:
                # Dung nguong max(12, avg_h * 0.6) de gom dong
                if abs(it['cy'] - l[0]['cy']) < max(12, avg_h * 0.6):
                    l.append(it)
                    matched = True
                    break
            if not matched:
                line_clusters.append([it])

        # Sap xep cac dong tu tren xuong duoi
        line_clusters.sort(key=lambda l: min(it['y0'] for it in l))

        merged_lines = []
        for l in line_clusters:
            # Trong cung 1 dong, sap xep tu trai sang phai
            l.sort(key=lambda it: it['x0'])
            
            # Khu trung lap cac box de len nhau do DBNet (vi du '-57.5' va '51')
            filtered = []
            for it in l:
                if not filtered:
                    filtered.append(it)
                else:
                    prev = filtered[-1]
                    overlap_w = min(prev['x1'], it['x1']) - max(prev['x0'], it['x0'])
                    min_w = min(prev['x1'] - prev['x0'], it['x1'] - it['x0'])
                    it_w = it['x1'] - it['x0']
                    # Neu do trung lap chieu ngang > 40% chieu rong cua box nho hon
                    if min_w > 0 and (overlap_w / min_w > 0.4 or (it_w > 0 and overlap_w / it_w > 0.4)):
                        # Box nao co dau cham hoac score cao hon hoac dai hon thi uu tien
                        if '.' in it['text'] and '.' not in prev['text']:
                            filtered[-1] = it
                        elif '.' in prev['text'] and '.' not in it['text']:
                            pass # Giu lai box co dau cham
                        elif it.get('score', 0) > prev.get('score', 0) + 0.15:
                            filtered[-1] = it
                        elif len(it['text']) > len(prev['text']):
                            filtered[-1] = it
                    else:
                        filtered.append(it)

            # Ghep text cac item trong dong
            merged_lines.append(' '.join(it['text'] for it in filtered))

        return merged_lines

    @staticmethod
    def pick_best_tol(txt_list: List[str], preferred_sign: str = '+') -> str:
        """
        Loc va chon gia tri dung sai toi uu nhat tu ket qua OCR sub-region.
        """
        candidates = []
        for raw in txt_list:
            s = raw.replace(' ', '').replace('O', '0').replace('o', '0')
            matches = re.findall(r'([\+\-]?[0-9]+(?:\.[0-9]+)?)', s)
            for m in matches:
                val_str = m
                if not val_str.startswith('+') and not val_str.startswith('-'):
                    if '+' in s:
                        val_str = '+' + val_str
                    elif '-' in s:
                        val_str = '-' + val_str
                candidates.append(val_str)

        clean_candidates = []
        for c in candidates:
            if c in ['1', 'TU', '!']:
                continue
            clean_candidates.append(c)

        if not clean_candidates:
            return ""

        clean_candidates.sort(key=lambda x: (x.startswith(preferred_sign), '.' in x, len(x)), reverse=True)
        best = clean_candidates[0]
        if not (best.startswith('+') or best.startswith('-')):
            best = preferred_sign + best
        return best

    @staticmethod
    def extract_stacked_subregion(crop_cv, nominal_str: str, rapid_engine, parser) -> Dict[str, Any]:
        """
        Sub-Region Zoom Inspection ket hop thuat toan check_stacked_tolerances tu edocr2:
        Khi crop chua boc tach duoc dung sai (tol_type == 'global') nhung co nominal,
        1. Su dung pixel density cut tu edocr2 de tach [Nominal, Upper, Lower]
        2. Hoac zoom rieng nua ben phai cua crop de quet dung sai xep chong (stacked tolerance).
        """
        if crop_cv is None or crop_cv.size == 0 or rapid_engine is None:
            return None

        import cv2
        from image_enhancer import ImageEnhancer

        # Cach 1: Su dung thuat toan check_stacked_tolerances tu edocr2 de cat theo mat do pixel
        try:
            parts = ImageEnhancer.check_stacked_tolerances(crop_cv)
            if len(parts) == 3:
                # parts[0]: nominal, parts[1]: upper_tol, parts[2]: lower_tol
                def _quick_ocr(img_part):
                    zoomed = cv2.resize(img_part, (0, 0), fx=2.5, fy=2.5, interpolation=cv2.INTER_LANCZOS4)
                    padded = cv2.copyMakeBorder(zoomed, 15, 15, 15, 15, cv2.BORDER_CONSTANT, value=[255, 255, 255])
                    res, _ = rapid_engine(padded)
                    txts = [t[1].strip() for t in res if t[1].strip()] if res else []
                    return txts

                u_txts = _quick_ocr(parts[1])
                l_txts = _quick_ocr(parts[2])
                u_tol = DimensionSpatialMerger.pick_best_tol(u_txts, preferred_sign='+')
                l_tol = DimensionSpatialMerger.pick_best_tol(l_txts, preferred_sign='-')

                if u_tol and l_tol:
                    combined = f"{nominal_str} {u_tol} {l_tol}".strip()
                    parsed = parser.parse(combined)
                    if parsed and parsed.get("nominal") is not None and parsed.get("tol_type") in ["local", "local_stacked"]:
                        return parsed
        except Exception:
            pass

        # Cach 2: Sub-region vertical split fallback
        h, w = crop_cv.shape[:2]
        right_w = max(int(w * 0.45), 15)
        right_part = crop_cv[:, w - right_w:]
        rh, rw = right_part.shape[:2]

        sub_top = right_part[0:int(rh * 0.55), :]
        sub_bot = right_part[int(rh * 0.45):, :]

        def ocr_sub(sub_img):
            scale = 3.5
            zoomed = cv2.resize(sub_img, (0, 0), fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
            padded = cv2.copyMakeBorder(zoomed, 30, 30, 30, 30, cv2.BORDER_CONSTANT, value=[255, 255, 255])
            
            passes = [padded]
            gray = cv2.cvtColor(padded, cv2.COLOR_BGR2GRAY)
            _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            passes.append(thresh)

            detected = []
            for p in passes:
                try:
                    res, _ = rapid_engine(p)
                    if res:
                        for _, txt, _ in res:
                            detected.append(txt.strip())
                except Exception:
                    pass
            return detected

        top_txts = ocr_sub(sub_top)
        bot_txts = ocr_sub(sub_bot)

        u_tol = DimensionSpatialMerger.pick_best_tol(top_txts, preferred_sign='+')
        l_tol = DimensionSpatialMerger.pick_best_tol(bot_txts, preferred_sign='-')

        if u_tol and l_tol:
            combined = f"{nominal_str} {u_tol} {l_tol}".strip()
            parsed = parser.parse(combined)
            if parsed and parsed.get("nominal") is not None and parsed.get("tol_type") in ["local", "local_stacked"]:
                return parsed

        return None

