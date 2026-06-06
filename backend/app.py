import os
import shutil
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.image_processor import process_cable_image

app = FastAPI(title="Cable Insulation Measurement API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("backend/uploads", exist_ok=True)
os.makedirs("backend/outputs", exist_ok=True)

# Önce outputs klasörünü yayınlıyoruz
app.mount("/outputs", StaticFiles(directory="backend/outputs"), name="outputs")


@app.post("/api/measure")
async def measure_cable(
    image: UploadFile = File(...),
    cable_type: str = Form("Tek damarlı kablo"),
    section_id: str = Form("SECTION-001"),
    section_date: str = Form("2026-05-14"),
    pixel_to_mm: float = Form(0.02),
    measurement_count: int = Form(6)
):
    upload_path = os.path.join("backend", "uploads", image.filename)

    with open(upload_path, "wb") as buffer:
        shutil.copyfileobj(image.file, buffer)

    result = process_cable_image(
        image_path=upload_path,
        image_name=image.filename,
        cable_type=cable_type,
        section_id=section_id,
        section_date=section_date,
        pixel_to_mm=pixel_to_mm,
        measurement_count=measurement_count
    )

    return result


# BUNU EN SONA KOYUYORUZ
# Çünkü "/" tüm yolları yakalayabilir.
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")