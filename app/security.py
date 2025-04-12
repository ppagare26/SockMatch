from fastapi import Request, HTTPException
from app.config.config import API_KEY, ALLOWED_CLIENT
import logging

logger = logging.getLogger("sockmatch-api")

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
