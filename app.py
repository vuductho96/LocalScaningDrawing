import socket
import _overlapped
import os
import uuid
import json
import base64
import io
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from pdf_processor import PDFProcessor, get_ocr_device_info, set_ocr_device
from tolerance_parser import global_adaptive_learner
from ai_vision_service import global_ai_vision_service
from export_service import ExportService

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(TEMPLATES_DIR, exist_ok=True)

app = FastAPI(title="AutoScanText - OCR Ban Ve Ky Thuat", version="1.0.0")

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

pdf_processor = PDFProcessor(upload_dir=UPLOAD_DIR)

# Luu danh sach file theo id
active_files = {}

def get_or_restore_file(file_id: str) -> Optional[Dict[str, Any]]:
    if not file_id:
        return None
    if file_id in active_files:
        return active_files[file_id]

    # 1. Thu tim file sample mac dinh neu la sample_107 hoac sample
    if file_id in ["sample_107", "sample"]:
        sample_path = os.path.join(BASE_DIR, "107-M1457.pdf")
        if not os.path.exists(sample_path):
            sample_path = os.path.join(UPLOAD_DIR, "sample_drawing.pdf")
        if os.path.exists(sample_path):
            try:
                info = pdf_processor.get_pdf_info(sample_path)
                active_files[file_id] = {
                    "filename": os.path.basename(sample_path),
                    "path": sample_path,
                    "page_count": info["page_count"],
                    "pages": info["pages"]
                }
                return active_files[file_id]
            except Exception:
                pass

    # 2. Quet UPLOAD_DIR tim file da upload bat dau voi file_id_
    if os.path.exists(UPLOAD_DIR):
        for fname in os.listdir(UPLOAD_DIR):
            if fname.startswith(f"{file_id}_") and fname.lower().endswith(".pdf"):
                full_path = os.path.join(UPLOAD_DIR, fname)
                try:
                    info = pdf_processor.get_pdf_info(full_path)
                    orig_name = fname[len(file_id) + 1:]
                    active_files[file_id] = {
                        "filename": orig_name,
                        "path": full_path,
                        "page_count": info["page_count"],
                        "pages": info["pages"]
                    }
                    return active_files[file_id]
                except Exception:
                    pass

        # 3. Fallback: file co the luu nguyen ten hoac trung ten
        direct_path = os.path.join(UPLOAD_DIR, file_id)
        if os.path.exists(direct_path) and direct_path.lower().endswith(".pdf"):
            try:
                info = pdf_processor.get_pdf_info(direct_path)
                active_files[file_id] = {
                    "filename": file_id,
                    "path": direct_path,
                    "page_count": info["page_count"],
                    "pages": info["pages"]
                }
                return active_files[file_id]
            except Exception:
                pass

    return None

# ==============================================================================
# REQUEST & DATA SCHEMAS
# ==============================================================================

class CropRequest(BaseModel):
    file_id: str
    page_num: int = 0
    crop_box: Dict[str, float]  # { x, y, width, height } tu 0.0 den 1.0
    global_constraints: Optional[Dict[str, Any]] = None
    page_rotation: int = 0  # Goc xoay cua trang PDF: 0, 90, 180, 270
    crop_rotation: int = 0  # Goc xoay rieng cua vung crop: 0, 90, 180, 270

class ExportRequest(BaseModel):
    drawing_name: Optional[str] = "BanVeKyThuat"
    global_constraints_summary: Optional[str] = ""
    rows: List[Dict[str, Any]]

class CorrectionFeedbackRequest(BaseModel):
    raw_text: str
    corrected: Dict[str, Any]

class ParseTextRequest(BaseModel):
    raw_text: str
    global_constraints: Optional[Dict[str, Any]] = None

class AIVisionConfigRequest(BaseModel):
    api_key: str
    model_name: Optional[str] = "gemini-flash-latest"
    billing_tier: Optional[str] = "free"
    custom_rpd_limit: Optional[int] = 0

class AIInspectCropRequest(BaseModel):
    file_id: str
    page_num: int = 0
    crop_box: Dict[str, float]
    raw_ocr_hint: Optional[str] = ""
    page_rotation: int = 0
    crop_rotation: int = 0

class AIAutoDetectRequest(BaseModel):
    file_id: str
    page_num: int = 0
    page_rotation: int = 0
    global_constraints: Optional[Dict[str, Any]] = None
    force_ocr: Optional[bool] = False

class OCRDeviceRequest(BaseModel):
    device: str

class CropCoordsRequest(BaseModel):
    file_id: str
    page_num: int = 0
    x: float
    y: float
    w: float
    h: float
    crop_rotation: int = 0
    global_constraints: Optional[Dict[str, Any]] = None

@app.get("/", response_class=FileResponse)
async def index(request: Request):
    html_path = os.path.join(TEMPLATES_DIR, "index.html")
    return FileResponse(html_path, media_type="text/html")

@app.get("/api/load-sample")
async def load_sample():
    sample_path = os.path.join(BASE_DIR, "107-M1457.pdf")
    if not os.path.exists(sample_path):
        sample_path = os.path.join(UPLOAD_DIR, "sample_drawing.pdf")
    
    file_id = "sample_107"
    filename = os.path.basename(sample_path)
    info = pdf_processor.get_pdf_info(sample_path)
    active_files[file_id] = {
        "filename": filename,
        "path": sample_path,
        "page_count": info["page_count"],
        "pages": info["pages"]
    }
    cache_path, w, h = pdf_processor.render_page(sample_path, page_num=0, dpi=200)
    return {
        "success": True,
        "file_id": file_id,
        "filename": filename,
        "page_count": info["page_count"],
        "page_width": w,
        "page_height": h,
        "initial_page_url": f"/api/page_image?file_id={file_id}&page=0"
    }

@app.post("/api/upload")
async def upload_pdf(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Chi chap nhan file dinh dang .pdf")
    
    file_id = str(uuid.uuid4())[:8]
    save_name = f"{file_id}_{file.filename}"
    save_path = os.path.join(UPLOAD_DIR, save_name)

    with open(save_path, "wb") as f:
        content = await file.read()
        f.write(content)

    try:
        info = pdf_processor.get_pdf_info(save_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Loi doc file PDF: {str(e)}")

    active_files[file_id] = {
        "filename": file.filename,
        "path": save_path,
        "page_count": info["page_count"],
        "pages": info["pages"]
    }

    # Render truoc trang 0
    try:
        cache_path, w, h = pdf_processor.render_page(save_path, page_num=0, dpi=200)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Loi render trang PDF: {str(e)}")

    return {
        "success": True,
        "file_id": file_id,
        "filename": file.filename,
        "page_count": info["page_count"],
        "page_width": w,
        "page_height": h,
        "initial_page_url": f"/api/page_image?file_id={file_id}&page=0"
    }

@app.get("/api/page_image")
async def get_page_image(file_id: str, page: int = 0, rotation: int = 0):
    file_info = get_or_restore_file(file_id)
    if not file_info:
        raise HTTPException(status_code=404, detail="Khong tim thay file PDF da upload")
    
    pdf_path = file_info["path"]
    
    try:
        cache_path, w, h = pdf_processor.render_page(pdf_path, page_num=page, dpi=200, rotation=rotation)
        return FileResponse(cache_path, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Loi lay anh trang {page}: {str(e)}")

@app.post("/api/crop-ocr")
async def crop_ocr(req: CropRequest):
    file_info = get_or_restore_file(req.file_id)
    if not file_info:
        raise HTTPException(status_code=404, detail="Khong tim thay file PDF (vui long f5 hoac tai lai file)")

    pdf_path = file_info["path"]
    
    try:
        result = pdf_processor.crop_and_extract(
            pdf_path=pdf_path,
            page_num=req.page_num,
            crop_box=req.crop_box,
            global_constraints=req.global_constraints,
            dpi=200,
            page_rotation=req.page_rotation,
            crop_rotation=req.crop_rotation
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Loi OCR: {str(e)}")

@app.post("/api/parse-text")
async def parse_text_endpoint(req: ParseTextRequest):
    """
    Phan tich truc tiep chuoi raw text bang ToleranceParser va AdaptiveLearner.
    Dung khi nguoi dung chinh sua truc tiep o Raw Text tren bang.
    """
    try:
        from tolerance_parser import ToleranceParser
        parser = ToleranceParser(global_constraints=req.global_constraints)
        result = parser.parse(req.raw_text)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Loi phan tich text: {str(e)}")

@app.post("/api/feedback/correct")
async def save_correction_feedback(req: CorrectionFeedbackRequest):
    """
    Nhan du lieu chinh sua tu con nguoi va hoc thich ung lap tuc (1-Shot / Generalized).
    """
    try:
        res = global_adaptive_learner.learn_correction(req.raw_text, req.corrected)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Loi luu phan hoi thich ung: {str(e)}")

@app.get("/api/feedback/rules")
async def get_adaptive_rules():
    """
    Lay danh sach cac quy tac da hoc tu nguoi dung de hien thi / quan ly tren UI.
    """
    return {
        "exact_matches": global_adaptive_learner.exact_matches,
        "generalized_rules": global_adaptive_learner.generalized_rules,
        "char_replacements": global_adaptive_learner.char_replacements
    }

@app.delete("/api/feedback/rules")
async def delete_adaptive_rule(key: str, rule_type: str = "exact"):
    """
    Xoa mot quy tac thich ung neu nguoi dung nhap nham.
    """
    success = global_adaptive_learner.delete_rule(key, rule_type)
    if not success:
        raise HTTPException(status_code=404, detail="Khong tim thay quy tac de xoa")
    return {"success": True, "message": f"Da xoa quy tac {key}"}

# ==============================================================================
# AI VISION ENDPOINTS (Gemini Multimodal Vision LLM)
# ==============================================================================

@app.get("/api/ai-vision/status")
async def get_ai_vision_status():
    """Kiem tra trang thai cau hinh va san sang cua AI Vision."""
    return global_ai_vision_service.check_status()

@app.get("/api/ai-vision/usage")
async def get_ai_vision_usage():
    """Lay thong tin phan tram va so luong request / quota cua API Key."""
    return global_ai_vision_service.get_usage_stats()

@app.post("/api/ai-vision/config")
async def set_ai_vision_config(req: AIVisionConfigRequest):
    """Luu API key va cau hinh model AI Vision."""
    saved = global_ai_vision_service.save_config(
        api_key=req.api_key,
        model_name=req.model_name,
        billing_tier=req.billing_tier,
        custom_rpd_limit=req.custom_rpd_limit
    )
    status = global_ai_vision_service.check_status()
    return {"success": saved, "status": status}

@app.delete("/api/ai-vision/config")
async def clear_ai_vision_config():
    """Gỡ bỏ API key hoàn toàn khỏi hệ thống."""
    global_ai_vision_service.clear_config()
    status = global_ai_vision_service.check_status()
    return {"success": True, "status": status}

@app.post("/api/ai-vision/inspect-crop")
async def ai_inspect_crop(req: AIInspectCropRequest):
    """
    Dung AI Vision (Gemini) phan tich sau anh crop de giai ma kich thuoc kho,
    chu xoay nghieng, ky hieu GD&T hoac dung sai dac biet.
    """
    file_info = get_or_restore_file(req.file_id)
    if not file_info:
        raise HTTPException(status_code=404, detail="Khong tim thay file PDF")

    pdf_path = file_info["path"]
    try:
        crop_res = pdf_processor.crop_and_extract(
            pdf_path=pdf_path,
            page_num=req.page_num,
            crop_box=req.crop_box,
            page_rotation=req.page_rotation,
            crop_rotation=req.crop_rotation
        )
        
        thumb_data = crop_res.get("thumbnail", "")
        if "," in thumb_data:
            thumb_b64 = thumb_data.split(",")[1]
            img_bytes = base64.b64decode(thumb_b64)
        else:
            raise ValueError("Khong the trich xuat anh thumbnail")

        ai_res = global_ai_vision_service.inspect_crop(
            img_bytes, 
            raw_ocr_hint=req.raw_ocr_hint or crop_res.get("raw_text", "")
        )
        
        if not ai_res.get("success"):
            return {**crop_res, "ai_error": ai_res.get("error")}

        # Merge ket qua AI Vision
        merged = {
            **crop_res,
            "nominal": ai_res.get("nominal", crop_res.get("nominal")),
            "nominal_str": ai_res.get("nominal_str") or crop_res.get("nominal_str"),
            "upper_tol": ai_res.get("upper_tol", crop_res.get("upper_tol")),
            "lower_tol": ai_res.get("lower_tol", crop_res.get("lower_tol")),
            "qty": ai_res.get("qty", crop_res.get("qty")),
            "prefix": ai_res.get("prefix", crop_res.get("prefix")),
            "suffix": ai_res.get("suffix", crop_res.get("suffix")),
            "tol_type": ai_res.get("tol_type", crop_res.get("tol_type")),
            "full_callout": ai_res.get("full_callout", crop_res.get("full_callout")),
            "ai_explanation": ai_res.get("explanation", ""),
            "source": ai_res.get("source", "ai_vision")
        }
        return merged
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Loi AI Vision Inspect: {str(e)}")

@app.post("/api/ai-vision/auto-detect")
async def ai_auto_detect(req: AIAutoDetectRequest):
    """
    Dung AI Vision quet toan bo trang ban ve va phat hien tat ca cac cum kich thuoc.
    """
    file_info = get_or_restore_file(req.file_id)
    if not file_info:
        raise HTTPException(status_code=404, detail="Khong tim thay file PDF")

    pdf_path = file_info["path"]
    try:
        cache_path, w, h = pdf_processor.render_page(
            pdf_path, 
            page_num=req.page_num, 
            dpi=200, 
            rotation=req.page_rotation
        )
        with open(cache_path, "rb") as f:
            img_bytes = f.read()

        res = global_ai_vision_service.auto_detect_dimensions(
            img_bytes, 
            page_width=w, 
            page_height=h
        )
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Loi AI Auto-Detect: {str(e)}")

@app.post("/api/local-auto-scan")
async def local_auto_scan(req: AIAutoDetectRequest):
    """
    Auto-Scan toan bo trang ban ve che do Local (Hybrid Vector-First + PP-OCRv6 Offline).
    """
    file_info = get_or_restore_file(req.file_id)
    if not file_info:
        raise HTTPException(status_code=404, detail="Khong tim thay file PDF")

    pdf_path = file_info["path"]
    try:
        res = pdf_processor.local_auto_detect(
            pdf_path=pdf_path,
            page_num=req.page_num,
            page_rotation=req.page_rotation,
            dpi=200,
            global_constraints=req.global_constraints,
            force_ocr=bool(req.force_ocr)
        )
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Loi Local Auto-Scan: {str(e)}")

@app.get("/api/ocr/device")
async def get_ocr_device_endpoint():
    """Lay thong tin thiet bi chay OCR hien tai (GPU DirectML / CPU)."""
    return get_ocr_device_info()

@app.post("/api/ocr/device")
async def set_ocr_device_endpoint(req: OCRDeviceRequest):
    """Chuyen doi thiet bi chay OCR giua GPU va CPU."""
    res = set_ocr_device(req.device)
    if res.get("success"):
        pdf_processor.clear_page_ocr_cache()
    return res

@app.post("/api/export-excel")
async def export_excel(req: ExportRequest):
    try:
        stream = ExportService.generate_excel(
            drawing_name=req.drawing_name or "BanVeKyThuat",
            global_constraints_summary=req.global_constraints_summary,
            rows=req.rows
        )
        filename = f"{req.drawing_name or 'BanVeKyThuat'}_Tolerances.xlsx"
        return StreamingResponse(
            stream,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Loi tao file Excel: {str(e)}")

@app.post("/api/export-csv")
async def export_csv(req: ExportRequest):
    try:
        output = ExportService.generate_csv(rows=req.rows)
        filename = f"{req.drawing_name or 'BanVeKyThuat'}_Tolerances.csv"
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode('utf-8-sig')),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Loi tao file CSV: {str(e)}")

@app.post("/api/crop-by-coords")
async def crop_by_coords(req: CropCoordsRequest):
    """
    Endpoint ho tro AI / Script debug: Tu dong crop theo toa do pixel chinh xac tren ban ve.
    """
    file_info = get_or_restore_file(req.file_id)
    if not file_info:
        raise HTTPException(status_code=404, detail="Khong tim thay file PDF da upload")

    pdf_path = file_info["path"]
    cache_path, img_w, img_h = pdf_processor.render_page(pdf_path, page_num=req.page_num, dpi=200)

    norm_box = {
        "x": max(0.0, req.x / img_w),
        "y": max(0.0, req.y / img_h),
        "width": min(1.0, req.w / img_w),
        "height": min(1.0, req.h / img_h)
    }

    try:
        result = pdf_processor.crop_and_extract(
            pdf_path=pdf_path,
            page_num=req.page_num,
            crop_box=norm_box,
            global_constraints=req.global_constraints,
            dpi=200,
            page_rotation=0,
            crop_rotation=req.crop_rotation
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Loi OCR theo toa do: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    print("Khoi dong AutoScanText Web Server tai http://localhost:8000 ...")
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=False)
