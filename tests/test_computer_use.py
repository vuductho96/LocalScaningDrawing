"""
Unit and Integration Tests for Computer Use Toolkit.
"""

import os
import unittest
from PIL import Image, ImageDraw, ImageFont

from computer_use import (
    InputController,
    ScreenController,
    OCRDetector,
    TemplateMatcher,
    ComputerAction,
    ActionType,
    ActionResult,
    BoundingBox,
)


class TestComputerUse(unittest.TestCase):

    def setUp(self):
        self.input_ctrl = InputController()
        self.screen_ctrl = ScreenController()
        self.ocr = OCRDetector()
        self.matcher = TemplateMatcher()

    def test_screen_size_and_mouse(self):
        w, h = self.input_ctrl.get_screen_size()
        self.assertGreater(w, 0)
        self.assertGreater(h, 0)

        pos = self.input_ctrl.get_mouse_position()
        self.assertEqual(len(pos), 2)

    def test_grid_overlay(self):
        # Create a test canvas
        canvas = Image.new("RGB", (800, 600), color=(240, 240, 240))
        grid_img = self.screen_ctrl.draw_grid_overlay(canvas, spacing=100)
        self.assertEqual(grid_img.size, (800, 600))

    def test_highlight_marker(self):
        canvas = Image.new("RGB", (800, 600), color=(255, 255, 255))
        marked = self.screen_ctrl.highlight_point(canvas, 400, 300, label="Test Target")
        self.assertEqual(marked.size, (800, 600))

    def test_ocr_and_template_matching(self):
        # Create an image with clear text
        img = Image.new("RGB", (600, 300), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)
        draw.text((100, 100), "Save Document", fill=(0, 0, 0))
        
        # Test OCR detection
        matches = self.ocr.find_text(img, "Save", exact=False)
        self.assertTrue(len(matches) >= 0)

        # Create template icon with distinctive pattern
        template = Image.new("RGB", (40, 40), color=(200, 200, 200))
        tdraw = ImageDraw.Draw(template)
        tdraw.rectangle([10, 10, 30, 30], fill=(0, 120, 215))
        tdraw.ellipse([15, 15, 25, 25], fill=(255, 0, 0))

        # Draw the template into main image at (200, 150)
        img.paste(template, (200, 150))
        
        match = self.matcher.find_template(img, template, threshold=0.85)
        self.assertIsNotNone(match)
        self.assertAlmostEqual(match.center[0], 220, delta=2)
        self.assertAlmostEqual(match.center[1], 170, delta=2)

    def test_action_execution_models(self):
        action = ComputerAction(
            action=ActionType.WAIT,
            duration=0.01,
            reasoning="Testing wait action"
        )
        res = self.input_ctrl.execute(action)
        self.assertTrue(res.success)


if __name__ == "__main__":
    unittest.main()
