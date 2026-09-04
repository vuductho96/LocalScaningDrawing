"""
Screen Controller for high-speed multi-monitor screen capture,
region cropping, base64 encoding, and coordinate grid overlay generation.
"""

import io
import base64
import logging
from typing import Optional, Tuple, List, Dict, Any, Union
from PIL import Image, ImageDraw, ImageFont
import numpy as np

try:
    import mss
    HAS_MSS = True
except ImportError:
    HAS_MSS = False

from computer_use.config import default_config, ComputerUseConfig

logger = logging.getLogger("computer_use.screen")


class ScreenController:
    """
    Controller for capturing screenshots and generating visual grounding grids.
    """

    def __init__(self, config: Optional[ComputerUseConfig] = None):
        self.config = config or default_config

    def get_monitors(self) -> List[Dict[str, Any]]:
        """
        Returns the list of available monitors and their dimensions.
        """
        if HAS_MSS:
            try:
                with mss.mss() as sct:
                    return list(sct.monitors)
            except Exception as e:
                logger.warning(f"mss monitor query failed: {e}")

        # Fallback to PIL ImageGrab
        try:
            from PIL import ImageGrab
            img = ImageGrab.grab()
            return [{"left": 0, "top": 0, "width": img.width, "height": img.height}]
        except Exception:
            return [{"left": 0, "top": 0, "width": 1920, "height": 1080}]

    def capture(self, monitor_index: Optional[int] = None) -> Image.Image:
        """
        Captures the screen of the specified monitor index (1-based index).
        Returns a PIL Image in RGB format.
        Has automatic fallback across MSS, PIL ImageGrab, and PyAutoGUI.
        """
        target_monitor = monitor_index if monitor_index is not None else self.config.default_monitor
        
        # 1. Try MSS for fast capture
        if HAS_MSS:
            try:
                with mss.mss() as sct:
                    monitors = sct.monitors
                    idx = min(target_monitor, len(monitors) - 1) if len(monitors) > 1 else 0
                    sct_img = sct.grab(monitors[idx])
                    img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
                    return img
            except Exception as e:
                logger.debug(f"MSS capture failed ({e}), falling back to PIL ImageGrab...")

        # 2. Try PIL ImageGrab
        try:
            from PIL import ImageGrab
            return ImageGrab.grab().convert("RGB")
        except Exception as e:
            logger.debug(f"PIL ImageGrab failed ({e}), falling back to PyAutoGUI...")

        # 3. Try PyAutoGUI screenshot
        try:
            import pyautogui
            return pyautogui.screenshot().convert("RGB")
        except Exception as e:
            logger.warning(f"All screen capture methods failed ({e}). Returning fallback canvas.")
            # Fallback canvas if desktop is inaccessible
            return Image.new("RGB", (1920, 1080), color=(30, 30, 30))

    def capture_region(self, x: int, y: int, width: int, height: int) -> Image.Image:
        """
        Captures a specific rectangular region of the screen.
        """
        if HAS_MSS:
            try:
                with mss.mss() as sct:
                    region = {"left": x, "top": y, "width": width, "height": height}
                    sct_img = sct.grab(region)
                    return Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
            except Exception:
                pass

        try:
            from PIL import ImageGrab
            bbox = (x, y, x + width, y + height)
            return ImageGrab.grab(bbox=bbox).convert("RGB")
        except Exception:
            full = self.capture()
            return full.crop((x, y, x + width, y + height))

    def draw_grid_overlay(
        self,
        image: Image.Image,
        spacing: Optional[int] = None,
        color: Tuple[int, int, int, int] = (255, 0, 0, 100),
        text_color: Tuple[int, int, int] = (255, 255, 255),
        bg_color: Tuple[int, int, int] = (200, 0, 0),
        font_size: int = 11
    ) -> Image.Image:
        """
        Draws an assistive coordinate grid with (X, Y) pixel markers over the screenshot.
        This provides high accuracy for multimodal AI models (Gemini, Claude, GPT-4o)
        when performing visual grounding and coordinate selection.
        """
        grid_spacing = spacing or self.config.grid_spacing
        width, height = image.size
        
        # Create an overlay layer for transparent grid lines
        overlay = Image.new("RGBA", (width, height), (255, 255, 255, 0))
        draw_overlay = ImageDraw.Draw(overlay)
        
        # Draw vertical lines
        for x in range(0, width, grid_spacing):
            draw_overlay.line([(x, 0), (x, height)], fill=color, width=1)
            
        # Draw horizontal lines
        for y in range(0, height, grid_spacing):
            draw_overlay.line([(0, y), (width, y)], fill=color, width=1)
            
        # Merge grid lines with original image
        base_rgba = image.convert("RGBA")
        combined = Image.alpha_composite(base_rgba, overlay).convert("RGB")
        draw = ImageDraw.Draw(combined)
        
        try:
            font = ImageFont.load_default()
        except Exception:
            font = None

        # Draw coordinate labels at grid intersections
        for x in range(0, width, grid_spacing * 2):
            for y in range(0, height, grid_spacing * 2):
                label = f"{x},{y}"
                bbox = draw.textbbox((x + 2, y + 2), label, font=font) if font and hasattr(draw, "textbbox") else (x + 2, y + 2, x + 50, y + 14)
                padded_bbox = (bbox[0] - 2, bbox[1] - 1, bbox[2] + 2, bbox[3] + 1)
                draw.rectangle(padded_bbox, fill=bg_color)
                draw.text((x + 2, y + 2), label, fill=text_color, font=font)
                
        return combined

    def highlight_point(
        self,
        image: Image.Image,
        x: int,
        y: int,
        radius: int = 12,
        color: Tuple[int, int, int] = (255, 0, 0),
        label: Optional[str] = None
    ) -> Image.Image:
        """
        Draws a target marker (crosshair / circle) at (x, y) on the screenshot for logging and debugging.
        """
        img_copy = image.copy()
        draw = ImageDraw.Draw(img_copy)
        
        draw.ellipse([x - radius, y - radius, x + radius, y + radius], outline=color, width=3)
        draw.line([x - radius * 2, y, x + radius * 2, y], fill=color, width=2)
        draw.line([x, y - radius * 2, x, y + radius * 2], fill=color, width=2)
        
        if label:
            draw.text((x + radius + 4, y - 8), label, fill=color)
            
        return img_copy

    def highlight_bounding_box(
        self,
        image: Image.Image,
        x: int,
        y: int,
        w: int,
        h: int,
        color: Tuple[int, int, int] = (0, 255, 0),
        label: Optional[str] = None
    ) -> Image.Image:
        """
        Draws a bounding box on the screenshot with an optional label.
        """
        img_copy = image.copy()
        draw = ImageDraw.Draw(img_copy)
        draw.rectangle([x, y, x + w, y + h], outline=color, width=3)
        if label:
            draw.text((x, max(0, y - 15)), label, fill=color)
        return img_copy

    @staticmethod
    def to_base64(image: Image.Image, format: str = "PNG", quality: int = 90) -> str:
        """
        Encodes a PIL Image into a base64 string.
        """
        buffered = io.BytesIO()
        if format.upper() == "JPEG":
            image.convert("RGB").save(buffered, format="JPEG", quality=quality)
        else:
            image.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode("utf-8")

    @staticmethod
    def to_numpy(image: Image.Image) -> np.ndarray:
        """Converts PIL Image to OpenCV/NumPy BGR array."""
        rgb = np.array(image)
        return rgb[:, :, ::-1].copy()

    @staticmethod
    def from_numpy(arr: np.ndarray) -> Image.Image:
        """Converts OpenCV/NumPy BGR array to PIL Image."""
        if len(arr.shape) == 2:
            return Image.fromarray(arr)
        rgb = arr[:, :, ::-1].copy()
        return Image.fromarray(rgb)
