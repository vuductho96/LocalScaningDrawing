"""
Autonomous Computer Use Agent.
Orchestrates Screen Capture, Vision Grounding, OCR/Template Detection, and Input Execution in a unified loop.
"""

import time
import os
import logging
from typing import List, Dict, Any, Optional, Callable
from PIL import Image

from computer_use.config import default_config, ComputerUseConfig
from computer_use.types import ComputerAction, ActionType, ActionResult, ExecutionStep, DetectedElement
from computer_use.controllers.input_controller import InputController
from computer_use.controllers.screen_controller import ScreenController
from computer_use.detection.ocr_detector import OCRDetector
from computer_use.detection.template_matcher import TemplateMatcher
from computer_use.ai.grounding import VisionGrounding

logger = logging.getLogger("computer_use.agent")


class ComputerUseAgent:
    """
    Unified Computer Use Agent combining vision AI, direct UI detection, and OS interaction.
    """

    def __init__(
        self,
        config: Optional[ComputerUseConfig] = None,
        api_key: Optional[str] = None
    ):
        self.config = config or default_config
        self.input = InputController(self.config)
        self.screen = ScreenController(self.config)
        self.ocr = OCRDetector()
        self.matcher = TemplateMatcher()
        self.grounding = VisionGrounding(api_key=api_key, config=self.config)
        
        self.history: List[Dict[str, Any]] = []

    # ========================== DIRECT / HYBRID UTILITIES ==========================

    def click_text(self, text_query: str, exact: bool = False, button: str = "left", clicks: int = 1) -> Optional[DetectedElement]:
        """
        Takes a screenshot, finds the specified text using OCR, and clicks its center coordinate.
        """
        img = self.screen.capture()
        match = self.ocr.find_first(img, text_query, exact=exact)
        
        if match:
            cx, cy = match.center
            logger.info(f"Found '{text_query}' at ({cx}, {cy}) with confidence {match.confidence:.2f}. Clicking...")
            self.input.click(cx, cy, button=button, clicks=clicks)
            return match
        else:
            logger.warning(f"Text '{text_query}' was not found on screen.")
            return None

    def click_template(self, template_path_or_img: Any, threshold: float = 0.8) -> Optional[DetectedElement]:
        """
        Takes a screenshot, finds the given template image/icon, and clicks its center coordinate.
        """
        img = self.screen.capture()
        match = self.matcher.find_template(img, template_path_or_img, threshold=threshold)
        
        if match:
            cx, cy = match.center
            logger.info(f"Found template match at ({cx}, {cy}) with confidence {match.confidence:.2f}. Clicking...")
            self.input.click(cx, cy)
            return match
        else:
            logger.warning("Template match not found on screen.")
            return None

    # ========================== AUTONOMOUS AI AGENT LOOP ==========================

    def run_task(
        self,
        goal: str,
        max_steps: Optional[int] = None,
        use_grid: bool = True,
        save_screenshots_dir: Optional[str] = None,
        step_callback: Optional[Callable[[ExecutionStep], None]] = None
    ) -> List[ExecutionStep]:
        """
        Runs an autonomous loop to achieve the given user goal using Vision AI:
        1. Capture screen (with optional coordinate grid).
        2. Ask Vision Model for the next action.
        3. Execute action on OS.
        4. Log step & repeat until finished or step limit reached.
        """
        limit = max_steps or self.config.max_steps_per_task
        steps: List[ExecutionStep] = []
        self.history = []

        if save_screenshots_dir:
            os.makedirs(save_screenshots_dir, exist_ok=True)

        logger.info(f"Starting Computer Use Task: '{goal}' (Max steps: {limit})")

        for step_idx in range(1, limit + 1):
            logger.info(f"--- Step {step_idx}/{limit} ---")
            
            # 1. Capture screen
            raw_screenshot = self.screen.capture()
            screen_size = self.input.get_screen_size()
            
            if use_grid:
                vision_image = self.screen.draw_grid_overlay(raw_screenshot)
            else:
                vision_image = raw_screenshot

            screenshot_path = None
            if save_screenshots_dir:
                screenshot_path = os.path.join(save_screenshots_dir, f"step_{step_idx:03d}.png")
                vision_image.save(screenshot_path)

            # 2. Predict next action
            action = self.grounding.predict_next_action(
                image=vision_image,
                goal=goal,
                history=self.history,
                screen_size=screen_size
            )
            
            logger.info(f"Step {step_idx} Decided Action: {action.action} | Reasoning: {action.reasoning}")

            # 3. Check for completion or failure
            if action.action == ActionType.DONE:
                result = ActionResult(success=True, action=action, message=action.reasoning or "Task completed.")
                step_record = ExecutionStep(
                    step_number=step_idx,
                    action=action,
                    result=result,
                    screenshot_path=screenshot_path,
                    timestamp=time.time()
                )
                steps.append(step_record)
                if step_callback:
                    step_callback(step_record)
                logger.info(f"Task completed successfully: {action.reasoning}")
                break

            if action.action == ActionType.FAIL:
                result = ActionResult(success=False, action=action, error=action.reasoning, message=action.reasoning or "Task failed.")
                step_record = ExecutionStep(
                    step_number=step_idx,
                    action=action,
                    result=result,
                    screenshot_path=screenshot_path,
                    timestamp=time.time()
                )
                steps.append(step_record)
                if step_callback:
                    step_callback(step_record)
                logger.error(f"Task aborted: {action.reasoning}")
                break

            # 4. Execute action
            result = self.input.execute(action)

            # Record history
            self.history.append({
                "action": action.action.value,
                "details": action.model_dump(exclude={"reasoning"}),
                "message": result.message,
                "success": result.success
            })

            step_record = ExecutionStep(
                step_number=step_idx,
                action=action,
                result=result,
                screenshot_path=screenshot_path,
                timestamp=time.time()
            )
            steps.append(step_record)

            if step_callback:
                step_callback(step_record)

            # 5. Wait for UI updates
            time.sleep(self.config.step_delay)

        return steps
