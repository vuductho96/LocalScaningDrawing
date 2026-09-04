"""
Example 04: Autonomous Computer Use Agent with Gemini Vision
Runs an end-to-end autonomous agent loop to fulfill natural language instructions.
"""

import os
import sys

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from computer_use import ComputerUseAgent, ComputerUseConfig

def step_logger(step):
    print(f"[Step {step.step_number}] Action: {step.action.action.value} -> {step.result.message}")
    if step.action.reasoning:
        print(f"  Reasoning: {step.action.reasoning}")

def main():
    # Make sure your GEMINI_API_KEY is configured
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Note: Set GEMINI_API_KEY environment variable or pass api_key directly to run the Vision Agent.")
        print("Example: set GEMINI_API_KEY=your_key_here")

    config = ComputerUseConfig(
        max_steps_per_task=10,
        step_delay=1.5,
        grid_spacing=100
    )

    agent = ComputerUseAgent(config=config, api_key=api_key)

    goal = "Open notepad, type 'Hello from Gemini Computer Use Agent', and press Enter."
    print(f"Task Goal: '{goal}'")
    
    # Run the autonomous loop
    # steps = agent.run_task(
    #     goal=goal,
    #     max_steps=10,
    #     use_grid=True,
    #     save_screenshots_dir="agent_steps",
    #     step_callback=step_logger
    # )
    # print(f"Completed in {len(steps)} steps.")

if __name__ == "__main__":
    main()
