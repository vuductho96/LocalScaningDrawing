"""
OCR-based UI Element Detector.
Locates words, buttons, links, and text strings on the screen using OCR.
"""

import logging
from typing import List, Optional, Tuple, Union
from PIL import Image
import numpy as np

from computer_use.types import DetectedElement, BoundingBox

logger = logging.getLogger("computer_use.ocr")

_RAPID_OCR_INSTANCE = None


def get_ocr_engine():
    """Lazily initializes the RapidOCR engine singleton."""
    global _RAPID_OCR_INSTANCE
    if _RAPID_OCR_INSTANCE is None:
        try:
            from rapidocr_onnxruntime import RapidOCR
            _RAPID_OCR_INSTANCE = RapidOCR()
            logger.info("RapidOCR initialized successfully.")
        except Exception as e:
            logger.warning(f"Could not load RapidOCR: {e}. OCR features will be limited.")
            _RAPID_OCR_INSTANCE = None
    return _RAPID_OCR_INSTANCE


class OCRDetector:
    """
    Detector for locating on-screen text elements.
    """

    def __init__(self):
        self.engine = get_ocr_engine()

    def detect_all(self, image: Union[Image.Image, np.ndarray]) -> List[DetectedElement]:
        """
        Runs OCR on the given image and extracts all detected text elements with bounding boxes.
        """
        if self.engine is None:
            self.engine = get_ocr_engine()
            if self.engine is None:
                return []

        # Convert PIL to numpy if needed
        if isinstance(image, Image.Image):
            rgb = np.array(image)
            img_np = rgb[:, :, ::-1] if len(rgb.shape) == 3 else rgb
        else:
            img_np = image

        try:
            results, _ = self.engine(img_np)
        except Exception as e:
            logger.error(f"OCR execution failed: {e}")
            return []

        elements: List[DetectedElement] = []
        if not results:
            return elements

        for item in results:
            # item format: [box_points, text, confidence]
            points, text, conf = item
            # points is 4 corners [[x1, y1], [x2, y2], [x3, y3], [x4, y4]]
            pts = np.array(points)
            min_x, min_y = int(np.min(pts[:, 0])), int(np.min(pts[:, 1]))
            max_x, max_y = int(np.max(pts[:, 0])), int(np.max(pts[:, 1]))
            w = max_x - min_x
            h = max_y - min_y

            bbox = BoundingBox(x=min_x, y=min_y, width=w, height=h)
            center = (min_x + w // 2, min_y + h // 2)

            elements.append(DetectedElement(
                text=text.strip(),
                bbox=bbox,
                confidence=float(conf),
                center=center
            ))

        return elements

    def find_text(
        self,
        image: Union[Image.Image, np.ndarray],
        query: str,
        exact: bool = False,
        case_sensitive: bool = False,
        min_confidence: float = 0.5
    ) -> List[DetectedElement]:
        """
        Finds all occurrences of `query` text on the screen.
        Returns a list of matching DetectedElements sorted by confidence.
        """
        all_elements = self.detect_all(image)
        matched: List[DetectedElement] = []

        q = query if case_sensitive else query.lower()

        for el in all_elements:
            if not el.text or el.confidence < min_confidence:
                continue

            t = el.text if case_sensitive else el.text.lower()

            if exact:
                if t == q:
                    matched.append(el)
            else:
                if q in t:
                    matched.append(el)

        # Sort by confidence descending
        matched.sort(key=lambda x: x.confidence, reverse=True)
        return matched

    def find_first(
        self,
        image: Union[Image.Image, np.ndarray],
        query: str,
        exact: bool = False,
        case_sensitive: bool = False
    ) -> Optional[DetectedElement]:
        """
        Finds the first/best match for the given query text.
        """
        matches = self.find_text(image, query, exact=exact, case_sensitive=case_sensitive)
        return matches[0] if matches else None
