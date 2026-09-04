"""
Input Controller for Mouse and Keyboard Automation.
Provides safe, smooth, and robust interaction capabilities.
"""

import time
import logging
from typing import Tuple, Optional, List, Union
import pyautogui

from computer_use.config import default_config, ComputerUseConfig
from computer_use.types import ComputerAction, ActionType, ActionResult

logger = logging.getLogger("computer_use.input")


class InputController:
    """
    Controller for executing mouse and keyboard actions on the operating system.
    """

    def __init__(self, config: Optional[ComputerUseConfig] = None):
        self.config = config or default_config
        
        # Apply safety settings
        pyautogui.FAILSAFE = self.config.failsafe
        pyautogui.PAUSE = self.config.action_pause

    def get_screen_size(self) -> Tuple[int, int]:
        """Returns the primary screen size as (width, height)."""
        return pyautogui.size()

    def get_mouse_position(self) -> Tuple[int, int]:
        """Returns the current mouse cursor position as (x, y)."""
        pos = pyautogui.position()
        return (pos.x, pos.y)

    def _clamp_coordinates(self, x: int, y: int) -> Tuple[int, int]:
        """Clamps coordinates to ensure they are within the screen boundaries."""
        screen_w, screen_h = self.get_screen_size()
        clamped_x = max(0, min(x, screen_w - 1))
        clamped_y = max(0, min(y, screen_h - 1))
        return clamped_x, clamped_y

    # ========================== MOUSE ACTIONS ==========================

    def move_to(self, x: int, y: int, duration: Optional[float] = None, smooth: bool = True) -> Tuple[int, int]:
        """
        Moves the mouse cursor to the specified coordinates (x, y).
        """
        x, y = self._clamp_coordinates(x, y)
        move_duration = duration if duration is not None else (self.config.mouse_move_duration if smooth else 0.0)
        
        try:
            if move_duration > 0:
                pyautogui.moveTo(x, y, duration=move_duration, tween=pyautogui.easeInOutQuad)
            else:
                pyautogui.moveTo(x, y)
        except pyautogui.FailSafeException:
            logger.warning("PyAutoGUI fail-safe triggered during move_to.")
            
        return x, y

    def click(self, x: Optional[int] = None, y: Optional[int] = None, button: str = "left", clicks: int = 1, interval: float = 0.0) -> Tuple[int, int]:
        """
        Clicks at the specified coordinates or current mouse position.
        """
        if x is not None and y is not None:
            self.move_to(x, y)
        else:
            x, y = self.get_mouse_position()
            
        try:
            pyautogui.click(x=x, y=y, button=button, clicks=clicks, interval=interval)
        except pyautogui.FailSafeException:
            logger.warning("PyAutoGUI fail-safe triggered during click.")
        return x, y

    def double_click(self, x: Optional[int] = None, y: Optional[int] = None) -> Tuple[int, int]:
        """Performs a double left click."""
        return self.click(x=x, y=y, button="left", clicks=2, interval=0.1)

    def triple_click(self, x: Optional[int] = None, y: Optional[int] = None) -> Tuple[int, int]:
        """Performs a triple left click."""
        return self.click(x=x, y=y, button="left", clicks=3, interval=0.1)

    def right_click(self, x: Optional[int] = None, y: Optional[int] = None) -> Tuple[int, int]:
        """Performs a right click."""
        return self.click(x=x, y=y, button="right")

    def middle_click(self, x: Optional[int] = None, y: Optional[int] = None) -> Tuple[int, int]:
        """Performs a middle click."""
        return self.click(x=x, y=y, button="middle")

    def mouse_down(self, button: str = "left") -> None:
        """Holds down the specified mouse button."""
        pyautogui.mouseDown(button=button)

    def mouse_up(self, button: str = "left") -> None:
        """Releases the specified mouse button."""
        pyautogui.mouseUp(button=button)

    def drag_to(self, x: int, y: int, duration: Optional[float] = None, button: str = "left") -> Tuple[int, int]:
        """
        Drags the mouse from the current position to (x, y) with the specified button held down.
        """
        x, y = self._clamp_coordinates(x, y)
        drag_duration = duration if duration is not None else max(self.config.mouse_move_duration * 1.5, 0.4)
        pyautogui.dragTo(x, y, duration=drag_duration, button=button, tween=pyautogui.easeInOutQuad)
        return x, y

    def scroll(self, clicks: int, direction: str = "vertical", x: Optional[int] = None, y: Optional[int] = None) -> None:
        """
        Scrolls the mouse wheel.
        clicks > 0 scrolls UP, clicks < 0 scrolls DOWN.
        For horizontal scrolling on Windows, direction='horizontal' uses hscroll.
        """
        if x is not None and y is not None:
            self.move_to(x, y)
            
        if direction == "horizontal":
            pyautogui.hscroll(clicks)
        else:
            pyautogui.scroll(clicks)

    # ========================== KEYBOARD ACTIONS ==========================

    def type_text(self, text: str, interval: Optional[float] = None) -> None:
        """
        Types the given text sequence.
        Supports automatic handling of special unicode characters or fallback to clipboard paste if needed.
        """
        type_interval = interval if interval is not None else self.config.typing_interval
        
        try:
            pyautogui.write(text, interval=type_interval)
        except Exception:
            # Fallback for complex Unicode/non-ASCII characters via clipboard
            import tkinter as tk
            root = tk.Tk()
            root.withdraw()
            root.clipboard_clear()
            root.clipboard_append(text)
            root.update()
            root.destroy()
            time.sleep(0.05)
            self.hotkey("ctrl", "v")

    def press_key(self, key: str, presses: int = 1, interval: float = 0.0) -> None:
        """
        Presses a single key (e.g. 'enter', 'tab', 'backspace', 'esc', 'down', 'f5').
        """
        try:
            pyautogui.press(key.lower(), presses=presses, interval=interval)
        except pyautogui.FailSafeException:
            logger.warning("PyAutoGUI fail-safe triggered during press_key.")

    def key_down(self, key: str) -> None:
        """Holds a key down."""
        try:
            pyautogui.keyDown(key.lower())
        except pyautogui.FailSafeException:
            logger.warning("PyAutoGUI fail-safe triggered during key_down.")

    def key_up(self, key: str) -> None:
        """Releases a held key."""
        try:
            pyautogui.keyUp(key.lower())
        except pyautogui.FailSafeException:
            logger.warning("PyAutoGUI fail-safe triggered during key_up.")

    def hotkey(self, *keys: str) -> None:
        """
        Presses a combination of keys in sequence and releases them in reverse order.
        Example: hotkey('ctrl', 'shift', 'esc')
        """
        try:
            normalized_keys = [k.lower() for k in keys]
            pyautogui.hotkey(*normalized_keys)
        except pyautogui.FailSafeException:
            logger.warning("PyAutoGUI fail-safe triggered during hotkey.")

    def wait(self, seconds: float) -> None:
        """Waits for the given amount of seconds."""
        time.sleep(seconds)

    # ========================== UNIFIED EXECUTOR ==========================

    def execute(self, action: ComputerAction) -> ActionResult:
        """
        Executes any ComputerAction object and returns a standardized ActionResult.
        """
        try:
            act_type = action.action
            
            if act_type == ActionType.MOUSE_MOVE:
                if action.x is None or action.y is None:
                    raise ValueError("MOUSE_MOVE requires 'x' and 'y' coordinates.")
                x, y = self.move_to(action.x, action.y, duration=action.duration)
                return ActionResult(success=True, action=action, message=f"Moved mouse to ({x}, {y})")

            elif act_type == ActionType.LEFT_CLICK:
                x, y = self.click(action.x, action.y, button="left", clicks=action.clicks or 1)
                return ActionResult(success=True, action=action, message=f"Left clicked at ({x}, {y})")

            elif act_type == ActionType.RIGHT_CLICK:
                x, y = self.right_click(action.x, action.y)
                return ActionResult(success=True, action=action, message=f"Right clicked at ({x}, {y})")

            elif act_type == ActionType.DOUBLE_CLICK:
                x, y = self.double_click(action.x, action.y)
                return ActionResult(success=True, action=action, message=f"Double clicked at ({x}, {y})")

            elif act_type == ActionType.TRIPLE_CLICK:
                x, y = self.triple_click(action.x, action.y)
                return ActionResult(success=True, action=action, message=f"Triple clicked at ({x}, {y})")

            elif act_type == ActionType.MIDDLE_CLICK:
                x, y = self.middle_click(action.x, action.y)
                return ActionResult(success=True, action=action, message=f"Middle clicked at ({x}, {y})")

            elif act_type == ActionType.MOUSE_DOWN:
                self.mouse_down(button=action.button or "left")
                return ActionResult(success=True, action=action, message=f"Mouse down ({action.button or 'left'})")

            elif act_type == ActionType.MOUSE_UP:
                self.mouse_up(button=action.button or "left")
                return ActionResult(success=True, action=action, message=f"Mouse up ({action.button or 'left'})")

            elif act_type == ActionType.DRAG_TO:
                if action.x is None or action.y is None:
                    raise ValueError("DRAG_TO requires 'x' and 'y' coordinates.")
                x, y = self.drag_to(action.x, action.y, duration=action.duration, button=action.button or "left")
                return ActionResult(success=True, action=action, message=f"Dragged mouse to ({x}, {y})")

            elif act_type == ActionType.SCROLL:
                clicks = action.clicks if action.clicks is not None else -3
                direction = action.direction or "vertical"
                self.scroll(clicks=clicks, direction=direction, x=action.x, y=action.y)
                return ActionResult(success=True, action=action, message=f"Scrolled {clicks} units ({direction})")

            elif act_type == ActionType.TYPE_TEXT:
                if action.text is None:
                    raise ValueError("TYPE_TEXT requires 'text'.")
                self.type_text(action.text, interval=action.duration)
                return ActionResult(success=True, action=action, message=f"Typed text: '{action.text}'")

            elif act_type == ActionType.KEY_PRESS:
                if not action.key:
                    raise ValueError("KEY_PRESS requires 'key'.")
                self.press_key(action.key, presses=action.clicks or 1)
                return ActionResult(success=True, action=action, message=f"Pressed key: '{action.key}'")

            elif act_type == ActionType.KEY_DOWN:
                if not action.key:
                    raise ValueError("KEY_DOWN requires 'key'.")
                self.key_down(action.key)
                return ActionResult(success=True, action=action, message=f"Key down: '{action.key}'")

            elif act_type == ActionType.KEY_UP:
                if not action.key:
                    raise ValueError("KEY_UP requires 'key'.")
                self.key_up(action.key)
                return ActionResult(success=True, action=action, message=f"Key up: '{action.key}'")

            elif act_type == ActionType.HOTKEY:
                if not action.keys:
                    raise ValueError("HOTKEY requires 'keys' list.")
                self.hotkey(*action.keys)
                return ActionResult(success=True, action=action, message=f"Executed hotkey: {'+'.join(action.keys)}")

            elif act_type == ActionType.WAIT:
                duration = action.duration if action.duration is not None else 1.0
                self.wait(duration)
                return ActionResult(success=True, action=action, message=f"Waited {duration}s")

            elif act_type == ActionType.DONE:
                return ActionResult(success=True, action=action, message=f"Task marked as DONE: {action.reasoning or ''}")

            elif act_type == ActionType.FAIL:
                return ActionResult(success=False, action=action, message=f"Task failed: {action.reasoning or ''}", error=action.reasoning)

            else:
                return ActionResult(success=False, action=action, error=f"Unsupported action type: {act_type}")

        except Exception as e:
            logger.error(f"Error executing action {action.action}: {e}", exc_info=True)
            return ActionResult(success=False, action=action, error=str(e), message=f"Action failed with exception: {e}")
