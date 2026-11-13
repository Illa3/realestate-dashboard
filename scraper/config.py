import os

from dotenv import load_dotenv

load_dotenv(override=True)  # 시스템에 빈 ANTHROPIC_API_KEY 등이 이미 설정된 환경이 있어 override 필요

MOLIT_SERVICE_KEY = os.environ["MOLIT_SERVICE_KEY"]
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
