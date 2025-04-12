import os
import imghdr
from fastapi import UploadFile, HTTPException
from app.config.config import ALLOWED_EXTENSIONS

def validate_uploaded_file(file: UploadFile, request_id: str):
    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail={"request_id": request_id, "status": "error", "error": "No file uploaded."}
        )

    _, ext = os.path.splitext(file.filename.lower())
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail={"request_id": request_id, "status": "error", "error": f"Unsupported file type {ext}. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"}
        )

def verify_file_is_image(file_path: str, request_id: str):
    if imghdr.what(file_path) is None:
        os.remove(file_path)
        raise HTTPException(
            status_code=400,
            detail={"request_id": request_id, "status": "error", "error": "Uploaded file is not a valid image."}
        )
