# main.py
import uvicorn
from app.app import app  # Directly import the app from app.py

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
