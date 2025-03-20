import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    OWNER_ID = int(os.getenv("OWNER_ID", 8021921380))
    API_ID_VALIDATION = r"^\d+$"
    SESSION_DIR = "sessions/"
