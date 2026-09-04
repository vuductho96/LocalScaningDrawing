"""
Configuration settings for the Computer Use toolkit.
"""

from pydantic import BaseModel, Field
from typing import Optional


class ComputerUseConfig(BaseModel):
    # PyAutoGUI Safety settings
    failsafe: bool = Field(default=True, description="Enable moving mouse to corner to abort")
    action_pause: float = Field(default=0.1, description="Default pause after PyAutoGUI actions (in seconds)")
    mouse_move_duration: float = Field(default=0.2, description="Duration for smooth mouse movements (in seconds)")
    
    # Keyboard settings
    typing_interval: float = Field(default=0.015, description="Interval between keystrokes when typing text")
    
    # Screen capture settings
    default_monitor: int = Field(default=1, description="Default monitor index (1-based)")
    grid_spacing: int = Field(default=100, description="Pixel spacing for coordinate grid overlay")
    grid_color: str = Field(default="rgba(255, 0, 0, 0.4)", description="Color for grid lines")
    
    # AI Vision Settings
    gemini_model_name: str = Field(default="gemini-2.5-flash", description="Default Gemini vision model")
    api_key: Optional[str] = Field(default=None, description="API Key for Gemini/Vision provider")
    max_steps_per_task: int = Field(default=30, description="Max execution steps for autonomous agent")
    step_delay: float = Field(default=1.0, description="Delay between agent loop steps to allow UI rendering")


# Global default configuration instance
default_config = ComputerUseConfig()
