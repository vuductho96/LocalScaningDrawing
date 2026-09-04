"""
Template Matcher for locating icons, buttons, and visual UI assets using OpenCV.
"""

import logging
from typing import List, Optional, Tuple, Union
from PIL import Image
import numpy as np
import cv2

from computer_use.types import DetectedElement, BoundingBox

logger = logging.getLogger("computer_use.template")


class TemplateMatcher:
    """
    Locates UI components based on image template matching.
    """

    @staticmethod
    def _to_cv2(img: Union[Image.Image, np.ndarray, str]) -> Optional[np.ndarray]:
        if isinstance(img, str):
            return cv2.imread(img)
        elif isinstance(img, Image.Image):
            rgb = np.array(img)
            return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        elif isinstance(img, np.ndarray):
            return img.copy()
        return None

    def find_template(
        self,
        screen_img: Union[Image.Image, np.ndarray, str],
        template_img: Union[Image.Image, np.ndarray, str],
        threshold: float = 0.8,
        label: Optional[str] = None
    ) -> Optional[DetectedElement]:
        """
        Finds the single best match for template_img within screen_img using minMaxLoc.
        """
        screen = self._to_cv2(screen_img)
        templ = self._to_cv2(template_img)

        if screen is None or templ is None:
            logger.error("Failed to load screen or template image.")
            return None

        screen_gray = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY) if len(screen.shape) == 3 else screen
        templ_gray = cv2.cvtColor(templ, cv2.COLOR_BGR2GRAY) if len(templ.shape) == 3 else templ

        th, tw = templ_gray.shape[:2]
        if th > screen_gray.shape[0] or tw > screen_gray.shape[1]:
            logger.warning("Template image is larger than target screen image.")
            return None

        res = cv2.matchTemplate(screen_gray, templ_gray, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)

        if max_val >= threshold:
            best_x, best_y = max_loc
            bbox = BoundingBox(x=best_x, y=best_y, width=tw, height=th)
            center = (best_x + tw // 2, best_y + th // 2)
            return DetectedElement(
                label=label or "template_match",
                bbox=bbox,
                confidence=float(max_val),
                center=center
            )
        return None

    def find_all_templates(
        self,
        screen_img: Union[Image.Image, np.ndarray, str],
        template_img: Union[Image.Image, np.ndarray, str],
        threshold: float = 0.8,
        label: Optional[str] = None,
        max_matches: int = 20
    ) -> List[DetectedElement]:
        """
        Finds all occurrences of template_img within screen_img sorted by confidence.
        """
        screen = self._to_cv2(screen_img)
        templ = self._to_cv2(template_img)

        if screen is None or templ is None:
            logger.error("Failed to load screen or template image.")
            return []

        screen_gray = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY) if len(screen.shape) == 3 else screen
        templ_gray = cv2.cvtColor(templ, cv2.COLOR_BGR2GRAY) if len(templ.shape) == 3 else templ

        th, tw = templ_gray.shape[:2]
        if th > screen_gray.shape[0] or tw > screen_gray.shape[1]:
            logger.warning("Template image is larger than target screen image.")
            return []

        res = cv2.matchTemplate(screen_gray, templ_gray, cv2.TM_CCOEFF_NORMED)
        loc = np.where(res >= threshold)
        
        points = list(zip(*loc[::-1])) # (x, y) coordinates
        # Sort points by score descending
        points.sort(key=lambda pt: res[pt[1], pt[0]], reverse=True)

        matches: List[DetectedElement] = []
        used_rects = []
        for pt in points:
            x, y = int(pt[0]), int(pt[1])
            conf = float(res[y, x])

            overlap = False
            for rx, ry in used_rects:
                if abs(x - rx) < tw // 2 and abs(y - ry) < th // 2:
                    overlap = True
                    break

            if not overlap:
                used_rects.append((x, y))
                bbox = BoundingBox(x=x, y=y, width=tw, height=th)
                center = (x + tw // 2, y + th // 2)
                matches.append(DetectedElement(
                    label=label or "template_match",
                    bbox=bbox,
                    confidence=conf,
                    center=center
                ))

                if len(matches) >= max_matches:
                    break

        return matches
