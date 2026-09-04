# AutoScanText - Web App OCR Bóc Tách Kích Thước & Dung Sai Bản Vẽ Kỹ Thuật

Ứng dụng Web App chuyên dụng dành cho kỹ sư cơ khí, kỹ sư thiết kế và bộ phận QA/QC để bóc tách kích thước danh nghĩa (Nominal), dung sai đối xứng (±), dung sai 1 phía cùng dấu (+ + / - -), dung sai 2 tầng (Stacked Tolerance) và tự động áp dụng dung sai chung (Global Constraints).

## 🚀 Cách Khởi Động
Chỉ cần **click đúp vào file `run.bat`**, hệ thống sẽ tự động khởi động server và mở trình duyệt tại địa chỉ:
`http://localhost:8000`

Hoặc chạy lệnh trong terminal:
```bash
python app.py
```

## 📐 Các Tính Năng Nổi Bật
1. **Hỗ trợ bản vẽ PDF chuyên sâu**:
   - Render PDF sang ảnh chất lượng cao 200-300 DPI bằng PyMuPDF.
   - Chiến lược bóc tách kép: Vector Text trực tiếp (nếu PDF từ CAD) hoặc RapidOCR (ONNX Runtime, PP-OCRv4) cho bản vẽ scan.
2. **Quy tắc vàng `Nominal > Tolerance`**:
   - Đảm bảo số đo danh nghĩa luôn lớn hơn dung sai, triệt tiêu việc nhận diện nhầm số.
3. **Bóc tách mọi dạng dung sai**:
   - Dung sai cùng dấu: `2.5 +0.1 +0.2`, `2.5 -0.1 -0.2`
   - Dung sai đối xứng: `50 ± 0.05`
   - Dung sai lệch khác dấu: `25 +0.1 / -0.05`
   - Dung sai 1 phía có số 0: `20 +0.05 / 0`, `30 0 / -0.02`
   - Kích thước giới hạn: `50.05 / 49.95`
   - Ký hiệu tiền tố: `Ø`, `R`, `M`, `4x`, `C`, `□`
4. **Hệ thống Global Constraints**:
   - Tự động điền dung sai chung khi kích thước không ghi dung sai riêng (theo số chữ số thập phân hoặc tiêu chuẩn ISO 2768).
5. **Thao tác mượt mà trên Canvas**:
    - Chuột trái: Kéo ô crop ảo màu dạ quang.
    - Giữ Ctrl (hoặc Chuột phải / Space): Kéo di chuyển bản vẽ (Pan).
    - Con lăn chuột: Zoom in/out tâm trỏ chuột.
6. **Bảng kết quả & Xuất file**:
   - Cho phép sửa trực tiếp từng ô (Inline editing).
   - Xuất dữ liệu ra file **Excel (.xlsx)** có định dạng màu sắc đẹp mắt và **CSV**.
