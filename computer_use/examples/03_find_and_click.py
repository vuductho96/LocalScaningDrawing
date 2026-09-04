"""
Example 03: UI Text Finding (OCR) and Template Matching
Finds text or icons on the screen and interacts with them.
"""

import os
import sys

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from computer_use import ScreenController, OCRDetector, TemplateMatcher, InputController

def main():
    print("=== Text & Template Element Detection Demo ===")
    screen = ScreenController()
    ocr = OCRDetector()
    input_ctrl = InputController()

    # Capture current screen
    img = screen.capture()

    # 1. Detect all text elements currently on screen
    elements = ocr.detect_all(img)
    print(f"Total text blocks detected on screen: {len(elements)}")
    
    # Print first 10 elements
    for el in elements[:10]:
        print(f"  - '{el.text}' | Center: {el.center} | Box: ({el.bbox.x}, {el.bbox.y}, {el.bbox.width}, {el.bbox.height})")

    # 2. Search for a specific word (e.g. 'File', 'Edit', 'Terminal', or 'Chrome')
    target = "File"
    matches = ocr.find_text(img, target, exact=False)
    if matches:
        best = matches[0]
        print(f"\nFound match for '{target}': '{best.text}' at ({best.center[0]}, {best.center[1]})")
        # To click it:
        # input_ctrl.click(best.center[0], best.center[1])
    else:
        print(f"\nText '{target}' not currently visible on screen.")

if __name__ == "__main__":
    main()
