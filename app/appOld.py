from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.match_logic.matcher import SockRecommender
import shutil
import os
import imghdr
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sockmatch-api")

app = FastAPI()

# Secure constants
API_KEY = os.getenv("SOCKMATCH_API_KEY")
ALLOWED_CLIENT = "sock-match-ai"

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update this in prod!
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def read_root():
    return {"message": "SockMatch AI API is running."}


def verify_request(request: Request):
    api_key = request.headers.get("Authorization")
    client_source = request.headers.get("X-Client-Source")
    request_id = request.headers.get("X-Request-ID", "unknown-id")

    if api_key != f"Bearer {API_KEY}":
        logger.warning(f"[{request_id}] Invalid API Key.")
        raise HTTPException(
            status_code=403,
            detail={"request_id": request_id, "status": "error", "error": "Invalid API Key"}
        )

    if client_source != ALLOWED_CLIENT:
        logger.warning(f"[{request_id}] Invalid Client Source: {client_source}")
        raise HTTPException(
            status_code=403,
            detail={"request_id": request_id, "status": "error", "error": "Unauthorized client source"}
        )

    return request_id


def validate_uploaded_file(file: UploadFile, request_id: str):
    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail={"request_id": request_id, "status": "error", "error": "No file uploaded."}
        )

    # Check extension is an image (basic filtering)
    allowed_extensions = ['.jpg', '.jpeg', '.png', '.bmp','.webp']
    _, ext = os.path.splitext(file.filename.lower())
    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail={"request_id": request_id, "status": "error", "error": "Unsupported file type. Only image files allowed (.jpg, .jpeg, .png, .bmp)."}
        )


def verify_file_is_image(file_path: str, request_id: str):
    """Extra check to validate actual file content, not just extension."""
    if imghdr.what(file_path) is None:
        os.remove(file_path)  # Cleanup fake file
        raise HTTPException(
            status_code=400,
            detail={"request_id": request_id, "status": "error", "error": "Uploaded file is not a valid image."}
        )


@app.post("/match")
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

    except HTTPException as e:
        raise e

    except Exception as e:
        logger.exception(f"[{request_id}] Internal server error: {e}")
        raise HTTPException(
            status_code=500,
            detail={"request_id": request_id, "status": "error", "error": "Internal server error while processing the image."}
        )

    finally:
        if file_location and os.path.exists(file_location):
            os.remove(file_location)
