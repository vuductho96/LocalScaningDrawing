"""
Command Line Interface (CLI) for Computer Use Toolkit.
"""

import argparse
import sys
import logging
from computer_use import (
    InputController,
    ScreenController,
    OCRDetector,
    UIAutomationInspector,
    ComputerUseAgent,
)

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")


def main():
    parser = argparse.ArgumentParser(description="Computer Use Toolkit CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # 1. Screenshot command
    p_screenshot = subparsers.add_parser("screenshot", help="Capture a screenshot")
    p_screenshot.add_argument("-o", "--output", default="screenshot.png", help="Output file path (default: screenshot.png)")
    p_screenshot.add_argument("--grid", action="store_true", help="Draw coordinate grid overlay")
    p_screenshot.add_argument("--spacing", type=int, default=100, help="Grid spacing in pixels (default: 100)")

    # 2. Mouse position command
    subparsers.add_parser("mouse-pos", help="Get current mouse cursor position and screen size")

    # 3. Click command
    p_click = subparsers.add_parser("click", help="Click at specific (x, y) coordinates")
    p_click.add_argument("x", type=int, help="X coordinate")
    p_click.add_argument("y", type=int, help="Y coordinate")
    p_click.add_argument("-b", "--button", default="left", choices=["left", "right", "middle"], help="Mouse button")
    p_click.add_argument("-c", "--clicks", type=int, default=1, help="Number of clicks")

    # 4. Type command
    p_type = subparsers.add_parser("type", help="Type a text string")
    p_type.add_argument("text", type=str, help="Text to type")
    p_type.add_argument("--enter", action="store_true", help="Press Enter key after typing")

    # 5. Find text command
    p_find = subparsers.add_parser("find-text", help="Find text on screen using OCR")
    p_find.add_argument("query", type=str, help="Text to search for on screen")
    p_find.add_argument("--click", action="store_true", help="Click the found text")
    p_find.add_argument("--exact", action="store_true", help="Exact match only")

    # 6. List windows command
    subparsers.add_parser("list-windows", help="List visible Windows desktop application windows")

    # 7. Run Agent command
    p_agent = subparsers.add_parser("run-agent", help="Run autonomous AI vision agent")
    p_agent.add_argument("--goal", required=True, type=str, help="The goal or instruction for the AI agent")
    p_agent.add_argument("--max-steps", type=int, default=15, help="Maximum number of steps (default: 15)")
    p_agent.add_argument("--no-grid", action="store_true", help="Disable visual grid overlay for grounding")
    p_agent.add_argument("--save-dir", default=None, help="Directory to save step screenshots")
    p_agent.add_argument("--api-key", default=None, help="Gemini API Key (or use GEMINI_API_KEY env var)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    input_ctrl = InputController()
    screen_ctrl = ScreenController()

    if args.command == "screenshot":
        img = screen_ctrl.capture()
        if args.grid:
            img = screen_ctrl.draw_grid_overlay(img, spacing=args.spacing)
        img.save(args.output)
        print(f"Screenshot saved to: {args.output} ({img.width}x{img.height})")

    elif args.command == "mouse-pos":
        pos = input_ctrl.get_mouse_position()
        size = input_ctrl.get_screen_size()
        print(f"Screen Size: {size[0]}x{size[1]}")
        print(f"Current Cursor Position: X={pos[0]}, Y={pos[1]}")

    elif args.command == "click":
        pos = input_ctrl.click(args.x, args.y, button=args.button, clicks=args.clicks)
        print(f"Clicked at ({pos[0]}, {pos[1]}) with button '{args.button}' ({args.clicks} times)")

    elif args.command == "type":
        input_ctrl.type_text(args.text)
        if args.enter:
            input_ctrl.press_key("enter")
        print(f"Typed text: '{args.text}' (enter={args.enter})")

    elif args.command == "find-text":
        ocr = OCRDetector()
        img = screen_ctrl.capture()
        matches = ocr.find_text(img, args.query, exact=args.exact)
        print(f"Found {len(matches)} match(es) for '{args.query}':")
        for i, m in enumerate(matches, 1):
            print(f"  {i}. '{m.text}' at Center: {m.center}, BBox: {m.bbox.model_dump()}, Confidence: {m.confidence:.2f}")

        if args.click and matches:
            best = matches[0]
            input_ctrl.click(best.center[0], best.center[1])
            print(f"Clicked best match at {best.center}")

    elif args.command == "list-windows":
        uia = UIAutomationInspector()
        windows = uia.list_open_windows()
        print(f"Found {len(windows)} visible top-level windows:")
        for w in windows:
            print(f"  - [{w['hwnd']}] '{w['title']}' | Pos: {w['bbox'].x},{w['bbox'].y} | Size: {w['bbox'].width}x{w['bbox'].height}")

    elif args.command == "run-agent":
        agent = ComputerUseAgent(api_key=args.api_key)
        steps = agent.run_task(
            goal=args.goal,
            max_steps=args.max_steps,
            use_grid=not args.no_grid,
            save_screenshots_dir=args.save_dir
        )
        print(f"\nTask execution completed in {len(steps)} steps.")


if __name__ == "__main__":
    main()
