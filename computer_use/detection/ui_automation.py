"""
Windows UI Automation Inspector.
Finds active window titles, bounding rectangles, and accessible UI controls.
"""

import logging
import ctypes
from ctypes import wintypes
from typing import List, Dict, Any, Optional, Tuple
from computer_use.types import BoundingBox, DetectedElement

logger = logging.getLogger("computer_use.uia")


class UIAutomationInspector:
    """
    Inspector for querying Windows system windows and native UI elements.
    """

    def __init__(self):
        self.user32 = ctypes.windll.user32 if hasattr(ctypes, "windll") else None

    def get_active_window_info(self) -> Optional[Dict[str, Any]]:
        """
        Retrieves title and bounding box of the currently focused window.
        """
        if not self.user32:
            return None

        try:
            hwnd = self.user32.GetForegroundWindow()
            if not hwnd:
                return None

            # Get title
            length = self.user32.GetWindowTextLengthW(hwnd)
            buff = ctypes.create_unicode_buffer(length + 1)
            self.user32.GetWindowTextW(hwnd, buff, length + 1)
            title = buff.value

            # Get rect
            rect = wintypes.RECT()
            self.user32.GetWindowRect(hwnd, ctypes.byref(rect))

            w = rect.right - rect.left
            h = rect.bottom - rect.top

            return {
                "hwnd": hwnd,
                "title": title,
                "bbox": BoundingBox(x=rect.left, y=rect.top, width=w, height=h),
                "center": (rect.left + w // 2, rect.top + h // 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get active window info: {e}")
            return None

    def list_open_windows(self) -> List[Dict[str, Any]]:
        """
        Lists visible top-level application windows.
        """
        if not self.user32:
            return []

        windows: List[Dict[str, Any]] = []

        def enum_windows_proc(hwnd, lParam):
            if self.user32.IsWindowVisible(hwnd):
                length = self.user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buff = ctypes.create_unicode_buffer(length + 1)
                    self.user32.GetWindowTextW(hwnd, buff, length + 1)
                    title = buff.value
                    if title and title.strip():
                        rect = wintypes.RECT()
                        self.user32.GetWindowRect(hwnd, ctypes.byref(rect))
                        w = rect.right - rect.left
                        h = rect.bottom - rect.top
                        if w > 20 and h > 20:
                            windows.append({
                                "hwnd": hwnd,
                                "title": title,
                                "bbox": BoundingBox(x=rect.left, y=rect.top, width=w, height=h),
                                "center": (rect.left + w // 2, rect.top + h // 2)
                            })
            return 1

        enum_proc_type = ctypes.WINFUNCTYPE(ctypes.c_int, wintypes.HWND, wintypes.LPARAM)
        self.user32.EnumWindows(enum_proc_type(enum_windows_proc), 0)
        return windows
