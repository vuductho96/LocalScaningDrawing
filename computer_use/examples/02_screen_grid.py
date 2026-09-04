"""
Example 02: Screen Capture and Visual Coordinate Grid
Captures the current display and overlays coordinate grid markers for visual grounding.
"""

import os
import sys

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from computer_use import ScreenController

def main():
    print("=== Screen Capture & Visual Grid Demo ===")
    screen = ScreenController()

    # 1. Inspect monitors
    monitors = screen.get_monitors()
    print(f"Found {len(monitors)} monitor(s):")
    for i, m in enumerate(monitors):
        print(f"  Monitor {i}: {m}")

    # 2. Capture primary screen
    img = screen.capture()
    print(f"Captured screen size: {img.size}")
    img.save("screenshot_raw.png")
    print("Saved raw screenshot to 'screenshot_raw.png'")

    # 3. Create Coordinate Grid Overlay (used by Vision AI models to locate pixels accurately)
    grid_img = screen.draw_grid_overlay(img, spacing=100)
    grid_img.save("screenshot_grid.png")
    print("Saved visual grid overlay to 'screenshot_grid.png'")

    # 4. Highlight a specific point (e.g. center)
    w, h = img.size
    highlighted = screen.highlight_point(img, w // 2, h // 2, label="Center Screen (Target)")
    highlighted.save("screenshot_highlight.png")
    print("Saved highlighted marker to 'screenshot_highlight.png'")

if __name__ == "__main__":
    main()
