import os
from dotenv import load_dotenv

load_dotenv()

IOL_USERNAME = os.getenv("IOL_USERNAME", "")
IOL_PASSWORD = os.getenv("IOL_PASSWORD", "")
IOL_SANDBOX = os.getenv("IOL_SANDBOX", "true").lower() == "true"
IOL_BASE_URL = (
    "https://api-sandbox.invertironline.com"
    if IOL_SANDBOX
    else "https://api.invertironline.com"
)

SEC_USER_AGENT = os.getenv("SEC_USER_AGENT", "BolsaTracker dev@example.com")

REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID", "")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET", "")
REDDIT_USERNAME = os.getenv("REDDIT_USERNAME", "")
REDDIT_PASSWORD = os.getenv("REDDIT_PASSWORD", "")

FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GROK_API_KEY = os.getenv("GROK_API_KEY", "")

PORT = int(os.getenv("PORT", "8000"))
DATABASE_PATH = os.getenv("DATABASE_PATH", "./data/bolsa-tracker.db")
