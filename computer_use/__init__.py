"""
Computer Use Toolkit - Python library for programmatic and autonomous OS interaction.
"""

from computer_use.config import ComputerUseConfig, default_config
from computer_use.controllers.input_controller import InputController
from computer_use.controllers.screen_controller import ScreenController
from computer_use.detection.ocr_detector import OCRDetector
from computer_use.detection.template_matcher import TemplateMatcher
from computer_use.detection.ui_automation import UIAutomationInspector
from computer_use.ai.grounding import VisionGrounding
from computer_use.agent.types import (
    ActionType,
    BoundingBox,
    DetectedElement,
    ComputerAction,
    ActionResult,
    ExecutionStep,
)
from computer_use.agent.agent import ComputerUseAgent

__version__ = "1.0.0"

__all__ = [
    "ComputerUseConfig",
    "default_config",
    "InputController",
    "ScreenController",
    "OCRDetector",
    "TemplateMatcher",
    "UIAutomationInspector",
    "VisionGrounding",
    "ActionType",
    "BoundingBox",
    "DetectedElement",
    "ComputerAction",
    "ActionResult",
    "ExecutionStep",
    "ComputerUseAgent",
]
