# Configuration for the local LLM endpoint
import os
from dotenv import load_dotenv

# Load .env if it exists
load_dotenv()

class Config:
    # Telegram Settings
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
    
    # LLM Settings (Empty string defaults to the official OpenAI API)
    BASE_URL = os.getenv("LLM_BASE_URL", "")
    API_KEY = os.getenv("LLM_API_KEY", "VLLM_API_KEY")
    DEFAULT_MODEL = os.getenv("LLM_MODEL", "qwen3.5-9b-mlx")
    VISION_MODEL = os.getenv("VISION_MODEL", "qwen2-vl-7b-instruct")
    
    # Flask Settings
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "nodabot-dev-secret")
    PORT = int(os.getenv("FLASK_PORT", 5001))
    DEBUG = os.getenv("FLASK_DEBUG", "True").lower() == "true"
    
    # Paths
    SCREENSHOT_DIR = os.getenv("SCREENSHOT_DIR", "screenshots")
    SESSIONS_DIR = os.getenv("SESSIONS_DIR", "sessions")
    
    # Execution Limits
    TIMEOUT = int(os.getenv("TIMEOUT", 300))
