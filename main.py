import os
import uvicorn
from app.app import app

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))  # Railway sets PORT env var
    uvicorn.run(app, host="0.0.0.0", port=port)
