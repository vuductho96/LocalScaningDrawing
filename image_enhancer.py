import cv2
import numpy as np
from typing import List, Tuple

class ImageEnhancer:
    """
    Multi-pass image preprocessor chuyen biet cho ban ve ky thuat co khi CAD.
    Tich hop cac thuat toan tien tien tu du an edocr2:
    - clean_leader_lines: Xoa sach cac duong giong, mui ten, net gach cat ngang so
    - check_stacked_tolerances: Phan tich mat do pixel de cat tach vung dung sai 2 tang
    - Multi-pass filters: Standard, Cleaned (edocr2), CLAHE, Sharpen, Otsu
    """

    @staticmethod
    def clean_leader_lines(img_bgr: np.ndarray) -> np.ndarray:
        """
        Thuat toan clean_h_lines & clean_v_lines tu edocr2:
        Phat hien cac duong giong kich thuoc (dimension line) va duong dan mui ten
        chay ngang hoac doc cat qua chu so, sau do to trang xoa bo chung ma van giu nguyen chu so.
        """
        if img_bgr is None or img_bgr.size == 0:
            return img_bgr

        try:
            h, w = img_bgr.shape[:2]
            if w < 30 or h < 20:
                return img_bgr

            cleaned = img_bgr.copy()
            gray = cv2.cvtColor(cleaned, cv2.COLOR_BGR2GRAY)
            # Nhi phan hoa nguoc de net ve thanh trang (255), nen thanh den (0)
            _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)

            # 1. Phat hien cac doan thang ngang dai (duong giong kich thuoc nam ngang)
            # Do dai kernel bang 70% chieu rong o crop
            h_len = max(int(w * 0.70), 18)
            horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (h_len, 1))
            detect_horizontal = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, horizontal_kernel, iterations=1)
            cnts_h, _ = cv2.findContours(detect_horizontal, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for c in cnts_h:
                # To trang de xoa net giong ngang voi do day mong tranh an vao so
                cv2.drawContours(cleaned, [c], -1, (255, 255, 255), 1)

            # 2. Phat hien cac doan thang doc dai (duong giong kich thuoc nam doc)
            # Do dai kernel bang 75% chieu cao o crop
            v_len = max(int(h * 0.75), 18)
            vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, v_len))
            detect_vertical = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, vertical_kernel, iterations=1)
            cnts_v, _ = cv2.findContours(detect_vertical, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for c in cnts_v:
                # To trang de xoa net giong doc voi do day mong tranh an vao so
                cv2.drawContours(cleaned, [c], -1, (255, 255, 255), 1)

            return cleaned
        except Exception:
            return img_bgr

    @staticmethod
    def check_stacked_tolerances(img_bgr: np.ndarray) -> List[np.ndarray]:
        """
        Thuat toan check_tolerances tu edocr2:
        Phan tich mat do pixel den tu phai qua trai.
        Neu phat hien vung chu dung sai co 2 tang (tren va duoi),
        tu dong tinh toan duong cat ngang tole_h_cut va duong cat doc tole_v_cut,
        roi cat tach thanh 3 anh con rieng biet:
        [0]: Kich thuoc danh nghia (Nominal) - Ben trai
        [1]: Dung sai tren (Upper Tol) - Nua tren ben phai
        [2]: Dung sai duoi (Lower Tol) - Nua duoi ben phai
        """
        if img_bgr is None or img_bgr.size == 0:
            return [img_bgr]

        try:
            h, w = img_bgr.shape[:2]
            if w < 40 or h < 24:
                return [img_bgr]

            img_gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

            # 1. Tim dong tren va dong duoi chua pixel van ban
            top_line, bot_line = 0, h - 1
            for i in range(h):
                if np.any(img_gray[i, :] < 200):
                    top_line = i
                    break
            for i in range(h - 1, top_line, -1):
                if np.any(img_gray[i, :] < 200):
                    bot_line = i
                    break

            if bot_line - top_line < 15:
                return [img_bgr]

            # 2. Do khoang cach tu mep phai lui ve trai den khi gap pixel den dau tien
            stop_at = []
            for i in range(top_line, bot_line + 1):
                row = img_gray[i, :]
                black_indices = np.where(row < 200)[0]
                if len(black_indices) > 0:
                    stop_at.append(w - 1 - black_indices[-1])
                else:
                    stop_at.append(w)

            if not stop_at:
                return [img_bgr]

            # 3. Kiem tra xem co doan ho giua 2 dong dung sai (khoang trong o giua theo chieu doc)
            tole = False
            tole_h_cut = None
            mid_start = int(0.25 * len(stop_at))
            mid_end = int(0.75 * len(stop_at))

            for idx in range(mid_start, mid_end):
                d = stop_at[idx]
                if d > h * 0.45 or d > w * 0.25:
                    tole = True
                    tole_h_cut = idx + top_line
                    break

            if tole and tole_h_cut is not None:
                # Tim duong cat doc giua nominal va cum dung sai
                tole_v_cut = None
                scan_start = max(0, w - int(w * 0.55))
                scan_end = w - 5

                # Tim cot co khoang trong doc tu 25% den 75% chieu cao
                for j in range(scan_start, scan_end):
                    col_section = img_gray[top_line:bot_line, j]
                    if np.all(col_section > 210) or np.mean(col_section) > 240:
                        tole_v_cut = j + 2
                        break

                if tole_v_cut and tole_v_cut > int(w * 0.35) and tole_v_cut < int(w * 0.85):
                    nominal_part = img_bgr[:, :tole_v_cut]
                    upper_part = img_bgr[:tole_h_cut, tole_v_cut:]
                    lower_part = img_bgr[tole_h_cut:, tole_v_cut:]

                    if nominal_part.size > 0 and upper_part.size > 0 and lower_part.size > 0:
                        return [nominal_part, upper_part, lower_part]

            return [img_bgr]
        except Exception:
            return [img_bgr]

    @staticmethod
    def create_passes(img_bgr: np.ndarray, base_scale: float = 2.0, pad: int = 24) -> List[Tuple[str, np.ndarray]]:
        """
        Tra ve danh sach cac tuple (pass_name, processed_image_bgr)
        """
        passes = []

        # Pass 0: Raw native resolution (1.0x) voi padding nhe (8px)
        # Day la pass cuc ky quan trong cho cac chu so dung sai nho nam sat duong giong,
        # tranh bi mo/dinh net do phep phong to hoac mat chu do xoa net.
        raw_pad = cv2.copyMakeBorder(
            img_bgr, 8, 8, 8, 8,
            cv2.BORDER_CONSTANT, value=[255, 255, 255]
        )
        passes.append(("raw_native", raw_pad))

        # 1. Them padding vien trang de khong bi cat mat dau +- hoac dau cham o mep
        padded = cv2.copyMakeBorder(
            img_bgr, pad, pad, pad, pad,
            cv2.BORDER_CONSTANT, value=[255, 255, 255]
        )
        ph, pw = padded.shape[:2]
        scale = base_scale if min(ph, pw) < 120 else 1.5

        # Upscale Lanczos
        pass1_standard = cv2.resize(padded, None, fx=scale, fy=scale, interpolation=cv2.INTER_LANCZOS4)

        # Pass moi: Xoa duong giong kich thuoc (edocr2 clean_leader_lines)
        pass_cleaned = ImageEnhancer.clean_leader_lines(pass1_standard)
        gray = cv2.cvtColor(pass_cleaned, cv2.COLOR_BGR2GRAY)

        # Pass 1: Cleaned Leader Lines (Khu triet de cac net gach, mui ten va duong giong)
        passes.append(("edocr2_cleaned", pass_cleaned))

        # Pass 2: CLAHE (Contrast Limited Adaptive Histogram Equalization)
        try:
            clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
            clahe_gray = clahe.apply(gray)
            pass2_clahe = cv2.cvtColor(clahe_gray, cv2.COLOR_GRAY2BGR)
            passes.append(("clahe", pass2_clahe))
        except Exception:
            pass

        # Pass 3: Standard Upscaled Lanczos
        passes.append(("standard", pass1_standard))

        # Pass 4: Unsharp Mask (Sharpening)
        try:
            gaussian = cv2.GaussianBlur(gray, (0, 0), 2.0)
            sharp_gray = cv2.addWeighted(gray, 1.5, gaussian, -0.5, 0)
            pass4_sharp = cv2.cvtColor(sharp_gray, cv2.COLOR_GRAY2BGR)
            passes.append(("sharpen", pass4_sharp))
        except Exception:
            pass

        # Pass 5: Adaptive / Otsu Thresholding (Binarization)
        try:
            _, thresh_gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            pass5_otsu = cv2.cvtColor(thresh_gray, cv2.COLOR_GRAY2BGR)
            passes.append(("otsu", pass5_otsu))
        except Exception:
            pass

        return passes

