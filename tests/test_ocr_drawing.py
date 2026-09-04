"""
Direct in-memory OCR & Crop Evaluation for 107-M1457.pdf drawing
"""

import os
import sys
import json

# Ensure UTF-8 output on Windows terminal
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pdf_processor import PDFProcessor
from tolerance_parser import ToleranceParser


def main():
    print("=== ĐÁNH GIÁ CHI TIẾT OCR & BÓC TÁCH BẢN VẼ 107-M1457.pdf ===\n")
    pdf_path = "107-M1457.pdf"
    processor = PDFProcessor()
    
    # 1. Render trang PDF
    cache_path, w, h = processor.render_page(pdf_path, page_num=0, dpi=200)
    print(f"1. Render trang PDF thành công: {w}x{h} px (DPI: 200)")

    # 2. Quét toàn bộ phần tử văn bản trên trang
    elements = processor._get_page_ocr_elements(cache_path)
    print(f"2. Tổng số cụm ký tự nhận diện được trên bản vẽ: {len(elements)}\n")

    parser = ToleranceParser()

    # 3. Phân tích các kích thước và dung sai
    dimensions = []
    for el in elements:
        txt = el.get("text", "").strip()
        if any(c.isdigit() for c in txt):
            bx = int(el["x0"])
            by = int(el["y0"])
            bw = int(el["x1"] - el["x0"])
            bh = int(el["y1"] - el["y0"])
            
            # Giả lập crop trực tiếp bằng crop_and_extract của PDFProcessor
            norm_box = {
                "x": max(0, bx - 10) / w,
                "y": max(0, by - 10) / h,
                "width": min(w, bw + 20) / w,
                "height": min(h, bh + 20) / h
            }
            
            crop_res = processor.crop_and_extract(
                pdf_path=pdf_path,
                page_num=0,
                crop_box=norm_box,
                global_constraints={
                    "mode": "decimals",
                    "fixed_value": 0.1,
                    "decimals": { "0": 0.2, "1": 0.1, "2": 0.05, "3": 0.01, "4": 0.005, "5": 0.001 }
                },
                dpi=200
            )

            dimensions.append({
                "raw": txt,
                "box": (bx, by, bw, bh),
                "center": (int(el["cx"]), int(el["cy"])),
                "nominal": crop_res.get("nominal"),
                "upper_tol": crop_res.get("upper_tol"),
                "lower_tol": crop_res.get("lower_tol"),
                "callout": crop_res.get("full_callout"),
                "tol_type": crop_res.get("tol_type"),
                "prefix": crop_res.get("prefix")
            })

    # In kết quả chi tiết
    print("=" * 105)
    print(f"{'STT':<4} | {'Raw OCR Text':<25} | {'Nominal':<9} | {'Upper Tol':<10} | {'Lower Tol':<10} | {'Full Callout':<24} | {'Loại'}")
    print("=" * 105)

    for i, d in enumerate(dimensions, 1):
        nom = str(d['nominal']) if d['nominal'] is not None else '-'
        up = str(d['upper_tol']) if d['upper_tol'] else '-'
        low = str(d['lower_tol']) if d['lower_tol'] else '-'
        callout = str(d['callout']) if d['callout'] else '-'
        ttype = str(d['tol_type']) if d['tol_type'] else '-'
        raw_clean = d['raw'].replace('\n', ' ')
        print(f"{i:<4} | {raw_clean:<25} | {nom:<9} | {up:<10} | {low:<10} | {callout:<24} | {ttype}")

    print("=" * 105)
    print(f"\n=> Đã phân tích thành công {len(dimensions)} kích thước trên bản vẽ 107-M1457.pdf!")

    # Lưu kết quả ra file JSON
    with open("ocr_test_results.json", "w", encoding="utf-8") as f:
        json.dump(dimensions, f, ensure_ascii=False, indent=2)
    print("=> Đã lưu chi tiết vào tệp 'ocr_test_results.json'")


if __name__ == "__main__":
    main()
