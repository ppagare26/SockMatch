import os
import uvicorn
from app.app import app
import psutil
process = psutil.Process(os.getpid())
mem = process.memory_info().rss / 1024 / 1024
print(f"[BASE MEMORY] Process is using: {mem:.2f} MB at startup.")

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))  # Railway sets PORT env var
    uvicorn.run(app, host="0.0.0.0", port=port)
