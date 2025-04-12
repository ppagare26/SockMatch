import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("SOCKMATCH_API_KEY")
ALLOWED_CLIENT = "sock-match-ai"

# Allowed image types
ALLOWED_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.bmp', '.webp']
