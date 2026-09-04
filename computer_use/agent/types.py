"""
Re-export types from computer_use.types for backwards compatibility.
"""

from computer_use.types import (
    ActionType,
    BoundingBox,
    DetectedElement,
    ComputerAction,
    ActionResult,
    ExecutionStep,
)

__all__ = [
    "ActionType",
    "BoundingBox",
    "DetectedElement",
    "ComputerAction",
    "ActionResult",
    "ExecutionStep",
]
