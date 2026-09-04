"""
Type definitions, enums, and data models for Computer Use.
"""

from enum import Enum
from typing import Optional, List, Tuple, Any, Dict
from pydantic import BaseModel, Field


class ActionType(str, Enum):
    # Mouse Actions
    MOUSE_MOVE = "mouse_move"
    LEFT_CLICK = "left_click"
    RIGHT_CLICK = "right_click"
    MIDDLE_CLICK = "middle_click"
    DOUBLE_CLICK = "double_click"
    TRIPLE_CLICK = "triple_click"
    MOUSE_DOWN = "mouse_down"
    MOUSE_UP = "mouse_up"
    DRAG_TO = "drag_to"
    SCROLL = "scroll"
    
    # Keyboard Actions
    TYPE_TEXT = "type_text"
    KEY_PRESS = "key_press"
    KEY_DOWN = "key_down"
    KEY_UP = "key_up"
    HOTKEY = "hotkey"
    
    # Screen & State Actions
    SCREENSHOT = "screenshot"
    WAIT = "wait"
    
    # High-level actions
    FIND_AND_CLICK = "find_and_click"
    DONE = "done"
    FAIL = "fail"


class BoundingBox(BaseModel):
    x: int
    y: int
    width: int
    height: int
    
    @property
    def center(self) -> Tuple[int, int]:
        return (self.x + self.width // 2, self.y + self.height // 2)
        
    @property
    def x2(self) -> int:
        return self.x + self.width
        
    @property
    def y2(self) -> int:
        return self.y + self.height


class DetectedElement(BaseModel):
    text: Optional[str] = None
    label: Optional[str] = None
    bbox: BoundingBox
    confidence: float = 1.0
    center: Tuple[int, int]


class ComputerAction(BaseModel):
    action: ActionType
    x: Optional[int] = Field(default=None, description="Target X coordinate")
    y: Optional[int] = Field(default=None, description="Target Y coordinate")
    text: Optional[str] = Field(default=None, description="Text to type or search")
    key: Optional[str] = Field(default=None, description="Keyboard key to press (e.g. 'enter', 'tab', 'esc')")
    keys: Optional[List[str]] = Field(default=None, description="List of keys for hotkey combination (e.g. ['ctrl', 'c'])")
    button: Optional[str] = Field(default="left", description="Mouse button ('left', 'right', 'middle')")
    clicks: Optional[int] = Field(default=1, description="Number of clicks or scroll units")
    duration: Optional[float] = Field(default=None, description="Duration for move/wait in seconds")
    direction: Optional[str] = Field(default="vertical", description="Scroll direction: 'vertical' or 'horizontal'")
    reasoning: Optional[str] = Field(default=None, description="AI reasoning behind choosing this action")


class ActionResult(BaseModel):
    success: bool
    action: ComputerAction
    message: str = ""
    error: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


class ExecutionStep(BaseModel):
    step_number: int
    action: ComputerAction
    result: ActionResult
    screenshot_path: Optional[str] = None
    timestamp: float
