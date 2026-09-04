# Computer Use Toolkit - Python

Bộ thư viện / toolkit Python hoàn chỉnh cung cấp tính năng **Computer Use** (điều khiển hệ điều hành, chuột, bàn phím, chụp màn hình, nhận diện giao diện và AI Vision Agent).

---

## 📦 1. Cài đặt các thư viện cần thiết

Cài đặt các gói phụ thuộc:
```bash
pip install -r requirements_computer_use.txt
```

Hoặc cài trực tiếp:
```bash
pip install pyautogui pynput mss pillow opencv-python pydantic rapidocr-onnxruntime google-genai
```

---

## 🚀 2. Kiến trúc & Các thành phần chính

```
computer_use/
├── __init__.py                # Export API chính
├── config.py                  # Cấu hình an toàn (FailSafe, timeouts, delays)
├── controllers/
│   ├── input_controller.py    # Điều khiển Chuột (Click, Move, Drag, Scroll) & Phím (Type, Hotkey)
│   └── screen_controller.py   # Chụp ảnh màn hình tốc độ cao (MSS/Pillow), tạo Coordinate Grid
├── detection/
│   ├── ocr_detector.py        # Quét văn bản trên màn hình (OCR) tìm tọa độ click
│   ├── template_matcher.py    # Tìm icon / ảnh mẫu (OpenCV Template Matching)
│   └── ui_automation.py       # Lấy danh sách và vị trí cửa sổ Windows đang mở
├── ai/
│   ├── grounding.py           # Phân tích ảnh chụp & định vị tọa độ bằng Gemini Vision AI
│   └── prompts.py             # Schema & System prompts cho Vision Model
├── agent/
│   ├── agent.py               # Autonomous Agent Loop (Screenshot -> AI -> Act -> Verify)
│   └── types.py               # Data models: ActionType, ComputerAction, ActionResult,...
└── cli.py                     # CLI Tool chạy tác vụ trực tiếp từ terminal
```

---

## 💻 3. Hướng dẫn sử dụng Python API

### A. Điều khiển Chuột & Bàn phím (`InputController`)

```python
from computer_use import InputController

ctrl = InputController()

# Lấy kích thước màn hình và vị trí chuột
w, h = ctrl.get_screen_size()
x, y = ctrl.get_mouse_position()

# Di chuyển mượt mà
ctrl.move_to(500, 300, duration=0.2)

# Click chuột (left, right, double_click, middle)
ctrl.click(500, 300)
ctrl.double_click(500, 300)
ctrl.right_click(500, 300)

# Kéo thả (Drag & Drop)
ctrl.drag_to(800, 300, duration=0.5)

# Cuộn chuột (clicks > 0: lên, clicks < 0: xuống)
ctrl.scroll(-5)

# Gõ văn bản & phím tắt
ctrl.type_text("Hello World!")
ctrl.press_key("enter")
ctrl.hotkey("ctrl", "c")
ctrl.hotkey("alt", "tab")
```

> **🛡️ Cơ chế An toàn (Fail-Safe):**  
> Mặc định tính năng Fail-Safe luôn bật. Nếu agent thao tác ngoài ý muốn, bạn chỉ cần **di chuyển chuột thật nhanh vào 1 trong 4 góc màn hình**, chương trình sẽ dừng ngay lập tức.

---

### B. Chụp màn hình & Tạo lưới tọa độ (`ScreenController`)

```python
from computer_use import ScreenController

screen = ScreenController()

# 1. Chụp ảnh màn hình chính
img = screen.capture()
img.save("desktop.png")

# 2. Tạo Coordinate Grid Overlay (hỗ trợ Vision AI định vị chính xác điểm click)
grid_img = screen.draw_grid_overlay(img, spacing=100)
grid_img.save("desktop_grid.png")

# 3. Đánh dấu điểm hoặc Bounding Box để debug
highlighted = screen.highlight_point(img, 450, 320, label="Search Box")
highlighted.save("debug_marker.png")
```

---

### C. Tìm kiếm phần tử bằng OCR & Template Matching

```python
from computer_use import ScreenController, OCRDetector, TemplateMatcher, InputController

screen = ScreenController()
ocr = OCRDetector()
matcher = TemplateMatcher()
input_ctrl = InputController()

img = screen.capture()

# 1. Tìm chữ bất kỳ trên màn hình và click vào
matches = ocr.find_text(img, "Chrome")
if matches:
    best = matches[0]
    print(f"Tìm thấy '{best.text}' tại tọa độ tâm: {best.center}")
    input_ctrl.click(best.center[0], best.center[1])

# 2. Tìm kiếm icon/nút bấm theo ảnh mẫu (template image)
icon_match = matcher.find_template(img, "icons/submit_btn.png", threshold=0.85)
if icon_match:
    input_ctrl.click(icon_match.center[0], icon_match.center[1])
```

---

### D. Chạy Autonomous AI Agent với Gemini Vision (`ComputerUseAgent`)

```python
import os
from computer_use import ComputerUseAgent

# Cấu hình API key
os.environ["GEMINI_API_KEY"] = "your_gemini_api_key_here"

agent = ComputerUseAgent()

# Chạy vòng lặp tự động hóa
steps = agent.run_task(
    goal="Mở trình duyệt, tìm kiếm 'thời tiết hôm nay' và nhấn Enter",
    max_steps=10,
    use_grid=True,                      # Dùng lưới tọa độ để AI click chuẩn xác
    save_screenshots_dir="agent_logs"   # Lưu lại ảnh chụp từng bước
)

for step in steps:
    print(f"Bước {step.step_number}: {step.action.action} -> {step.result.message}")
```

---

## 🛠️ 4. Sử dụng qua Command Line Interface (CLI)

Bộ công cụ đi kèm CLI tiện lợi để kiểm tra và tương tác trực tiếp:

```bash
# 1. Chụp ảnh màn hình (kèm lưới tọa độ)
python -m computer_use.cli screenshot -o my_screen.png --grid

# 2. Xem tọa độ chuột hiện tại
python -m computer_use.cli mouse-pos

# 3. Click vào tọa độ cụ thể
python -m computer_use.cli click 500 300 --button left

# 4. Gõ văn bản
python -m computer_use.cli type "Hello World" --enter

# 5. Tìm chữ trên màn hình bằng OCR và click
python -m computer_use.cli find-text "Notepad" --click

# 6. Xem danh sách các cửa sổ đang mở
python -m computer_use.cli list-windows

# 7. Chạy Autonomous AI Agent
python -m computer_use.cli run-agent --goal "Open notepad and type text" --max-steps 10
```

---

## 📂 5. Các ví dụ mẫu sẵn có (`examples/`)

- `computer_use/examples/01_basic_actions.py`: Thao tác chuột, bàn phím, hotkeys cơ bản.
- `computer_use/examples/02_screen_grid.py`: Chụp ảnh màn hình và sinh ảnh lưới tọa độ.
- `computer_use/examples/03_find_and_click.py`: OCR quét text trên màn hình và click tự động.
- `computer_use/examples/04_ai_vision_agent.py`: Chạy agent loop với Gemini Vision.
