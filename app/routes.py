from fastapi import APIRouter, UploadFile, File, Request, HTTPException
from fastapi.responses import JSONResponse
from app.security import verify_request
from app.utils import validate_uploaded_file, verify_file_is_image
from app.match_logic.matcher import SockRecommender
import os
import shutil
import logging

router = APIRouter()
logger = logging.getLogger("sockmatch-api")

@router.get("/")
async def read_root():
    return {"message": "SockMatch AI API is running."}

@router.post("/match")
async def match_endpoint(file: UploadFile = File(...), request: Request = None):
    request_id = verify_request(request)
    file_location = None

    try:
        validate_uploaded_file(file, request_id)

        file_location = f"temp_{request_id}_{file.filename}"
        with open(file_location, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        verify_file_is_image(file_location, request_id)

        sock_recommender = SockRecommender()
        result = sock_recommender.match_socks(file_location)

        return JSONResponse(content={
            "request_id": request_id,
            "status": "success",
            "result": result
        })

    except HTTPException:
        raise

    except Exception as e:
        logger.exception(f"[{request_id}] Internal server error: {e}")
        raise HTTPException(
            status_code=500,
            detail={"request_id": request_id, "status": "error", "error": "Internal server error while processing the image."}
        )

    finally:
        if file_location and os.path.exists(file_location):
            os.remove(file_location)
