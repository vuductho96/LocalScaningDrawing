"""
Example 01: Basic Mouse and Keyboard Actions
Demonstrates safe programmatic control of mouse, keyboard, and hotkeys.
"""

import os
import sys
import time

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from computer_use import InputController, ComputerUseConfig

# Configure with safety options
config = ComputerUseConfig(
    failsafe=True,              # Move mouse to any corner of screen to immediately abort
    action_pause=0.1,           # Small pause between actions
    mouse_move_duration=0.3     # Smooth mouse movement
)

ctrl = InputController(config)

def main():
    print("=== Basic Actions Example ===")
    
    # 1. Screen information
    width, height = ctrl.get_screen_size()
    print(f"Screen Size: {width}x{height}")
    
    cur_x, cur_y = ctrl.get_mouse_position()
    print(f"Current Mouse Position: ({cur_x}, {cur_y})")

    # 2. Smooth mouse movements
    print("Moving mouse smoothly to center of screen...")
    ctrl.move_to(width // 2, height // 2)
    time.sleep(0.5)

    # 3. Mouse clicks
    print("Simulating right click at current position...")
    # ctrl.right_click()
    
    # 4. Keyboard typing
    print("Typing demo text...")
    # ctrl.type_text("Hello from Computer Use Toolkit!")
    
    # 5. Hotkeys
    print("Demo hotkey (e.g. Esc)...")
    ctrl.press_key("esc")

    print("Basic actions demo finished successfully.")

if __name__ == "__main__":
    main()
