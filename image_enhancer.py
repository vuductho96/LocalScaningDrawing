import cv2
import numpy as np
from typing import List, Tuple

class ImageEnhancer:
    """
    Multi-pass image preprocessor chuyen biet cho ban ve ky thuat co khi CAD.
    Cung cap cac phien ban anh voi cac bo loc khac nhau:
    - Pass 1: Standard Padded & Lanczos 2x (Ban goc phong to net cao)
    - Pass 2: Grayscale + CLAHE (Keo do tuong phan cuc bo cho net mo)
    - Pass 3: Adaptive/Otsu Binarization (Tach nen trang chu den ro ret)
    - Pass 4: Unsharp Mask Sharpening (Lam sac net cac vien chu so va dau cham)
    """

    @staticmethod
    def create_passes(img_bgr: np.ndarray, base_scale: float = 2.0, pad: int = 24) -> List[Tuple[str, np.ndarray]]:
        """
        Tra ve danh sach cac tuple (pass_name, processed_image_bgr)
        """
        if img_bgr is None or img_bgr.size == 0:
            return []

        # 1. Them padding vien trang de khong bi cat mat dau +- hoac dau cham o mep
        padded = cv2.copyMakeBorder(
            img_bgr, pad, pad, pad, pad,
            cv2.BORDER_CONSTANT, value=[255, 255, 255]
        )
        ph, pw = padded.shape[:2]
        scale = base_scale if min(ph, pw) < 120 else 1.5

        # Upscale Lanczos
        pass1_standard = cv2.resize(padded, None, fx=scale, fy=scale, interpolation=cv2.INTER_LANCZOS4)
        gray = cv2.cvtColor(pass1_standard, cv2.COLOR_BGR2GRAY)

        # Pass 1: CLAHE (Contrast Limited Adaptive Histogram Equalization)
        # Giup lam ro chu so mo hoac net dut trong ban ve scan va CAD
        passes = []
        try:
            clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
            clahe_gray = clahe.apply(gray)
            pass1_clahe = cv2.cvtColor(clahe_gray, cv2.COLOR_GRAY2BGR)
            passes.append(("clahe", pass1_clahe))
        except Exception:
            pass

        # Pass 2: Standard Upscaled Lanczos
        passes.append(("standard", pass1_standard))

        # Pass 3: Unsharp Mask (Sharpening)
        # Khac phuc hien tuong chu so bi nham: '8' va '3', '0' va '8', dau '.' bi mo
        try:
            gaussian = cv2.GaussianBlur(gray, (0, 0), 2.0)
            sharp_gray = cv2.addWeighted(gray, 1.5, gaussian, -0.5, 0)
            pass3_sharp = cv2.cvtColor(sharp_gray, cv2.COLOR_GRAY2BGR)
            passes.append(("sharpen", pass3_sharp))
        except Exception:
            pass

        # Pass 4: Adaptive / Otsu Thresholding (Binarization)
        # Khong con bong mo mau xam, chi con chu den tuyet doi tren nen trang
        try:
            # Ap dung Otsu binarization truc tiep
            _, thresh_gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            pass4_otsu = cv2.cvtColor(thresh_gray, cv2.COLOR_GRAY2BGR)
            passes.append(("otsu", pass4_otsu))
        except Exception:
            pass

        return passes

