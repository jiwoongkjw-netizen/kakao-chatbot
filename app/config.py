"""환경변수 설정 로드"""

import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    AI_MODEL: str = os.getenv("AI_MODEL", "claude-haiku-4-5-20251001")
    BOT_NAME: str = os.getenv("BOT_NAME", "AI 상담봇")
    BOT_DESCRIPTION: str = os.getenv("BOT_DESCRIPTION", "문의에 답변하는 AI 챗봇입니다.")
    ADMIN_API_KEY: str = os.getenv("ADMIN_API_KEY", "change-me")
    PORT: int = int(os.getenv("PORT", "8000"))
    DB_PATH: str = os.getenv("DB_PATH", "data/knowledge.db")


settings = Settings()
