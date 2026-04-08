"""
카카오 비즈니스 채널 AI 챗봇 - 메인 서버

실행 방법:
  uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
"""

from fastapi import FastAPI
from contextlib import asynccontextmanager

from app.config import settings
from app.knowledge_db import init_db, seed_from_json
from app.webhook import webhook_router, admin_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """서버 시작/종료 시 실행되는 라이프사이클 핸들러"""
    # ── 시작 ──
    print(f"[{settings.BOT_NAME}] 서버 시작 중...")
    init_db()
    seeded = seed_from_json()
    if seeded:
        print(f"  → 초기 FAQ 데이터 {seeded}건 로드 완료")
    print(f"  → AI 모델: {settings.AI_MODEL}")
    print(f"  → DB 경로: {settings.DB_PATH}")
    print(f"  → 서버 준비 완료!")
    yield
    # ── 종료 ──
    print(f"[{settings.BOT_NAME}] 서버 종료")


app = FastAPI(
    title=settings.BOT_NAME,
    description="카카오 비즈니스 채널 AI 챗봇 스킬 서버",
    version="1.0.0",
    lifespan=lifespan,
)


# ── 라우터 등록 ──
app.include_router(webhook_router)
app.include_router(admin_router)


# ── 헬스체크 ──
@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "bot_name": settings.BOT_NAME,
        "ai_model": settings.AI_MODEL,
    }


# ── 루트 ──
@app.get("/")
async def root():
    return {
        "message": f"{settings.BOT_NAME} 스킬 서버가 정상 작동 중입니다.",
        "endpoints": {
            "webhook": "POST /webhook",
            "health": "GET /health",
            "admin_faq_list": "GET /admin/knowledge",
            "admin_faq_add": "POST /admin/knowledge",
            "admin_logs": "GET /admin/logs",
        },
    }


# ── 직접 실행 시 ──
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.PORT, reload=True)
