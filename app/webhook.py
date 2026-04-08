"""
웹훅 라우터 (v2 — 모호한 질문 되묻기 지원)

처리 흐름:
1. 특수 명령어 확인 (처음으로, 상담원 연결 등)
2. 지식 DB 정확 매칭 검색
3. Claude AI 호출 → 답변 or 되묻기(disambiguation) 분기
4. 되묻기인 경우 quickReplies 버튼으로 선택지 제시
"""

from fastapi import APIRouter, Request, Header, HTTPException
from typing import Optional

from app.config import settings
from app import kakao_response as kr
from app.knowledge_db import (
    search_knowledge,
    log_chat,
    add_knowledge,
    update_knowledge,
    delete_knowledge,
    list_knowledge,
    bulk_insert_knowledge,
    get_recent_logs,
)
from app.ai_engine import generate_ai_response


# ── 카카오 웹훅 라우터 ──

webhook_router = APIRouter()


@webhook_router.post("/webhook")
async def handle_kakao_webhook(request: Request):
    """카카오 i 오픈빌더 스킬 서버 엔드포인트"""
    try:
        body = await request.json()
    except Exception:
        return kr.error_response()

    user_request = body.get("userRequest", {})
    utterance = user_request.get("utterance", "").strip()
    user_id = user_request.get("user", {}).get("id", "unknown")

    if not utterance:
        return kr.error_response("메시지를 인식하지 못했습니다. 다시 입력해 주세요.")

    # ── 특수 명령어 ──
    if utterance in ("처음으로", "시작", "메뉴"):
        return kr.simple_text(
            text=f"안녕하세요! {settings.BOT_NAME}입니다.\n무엇이 궁금하신가요?",
            quick_replies=[
                kr.make_quick_reply("원천세/급여"),
                kr.make_quick_reply("4대보험"),
                kr.make_quick_reply("부가세"),
                kr.make_quick_reply("종합소득세"),
                kr.make_quick_reply("상담원 연결"),
            ],
        )

    if utterance in ("상담원 연결", "상담원", "사람", "직접 상담"):
        return kr.basic_card(
            title="상담원 연결",
            description="아래 버튼을 눌러 전화 상담을 받으시거나,\n메시지를 남겨주시면 담당자가 확인 후 연락드리겠습니다.",
            buttons=[
                kr.make_button_phone("전화 상담", "02XXXXXXXX"),
            ],
        )

    # ── Step 1: 지식 DB 정확 매칭 ──
    db_result = search_knowledge(utterance)

    if db_result:
        answer = db_result["answer"]
        log_chat(user_id, utterance, answer, source="db")
        return kr.simple_text(
            text=answer,
            quick_replies=[
                kr.make_quick_reply("다른 질문하기", "처음으로"),
                kr.make_quick_reply("상담원 연결"),
            ],
        )

    # ── Step 2: Claude AI 호출 ──
    ai_result = await generate_ai_response(utterance)

    # ── Step 3: AI 응답 분기 처리 ──

    if ai_result["type"] == "disambiguation":
        # 되묻기: 선택지를 quickReplies 버튼으로 변환
        message = ai_result.get("message", "어떤 부분이 궁금하신지 선택해 주세요!")
        options = ai_result.get("options", [])

        quick_replies = []
        for opt in options[:5]:  # 카카오 quickReplies 최대 5개
            label = opt.get("label", "")[:14]  # 라벨 최대 14자
            # 사용자가 버튼을 누르면 label이 발화로 전송됨
            # → 다시 webhook으로 들어와서 이번엔 더 구체적인 매칭 가능
            quick_replies.append(kr.make_quick_reply(label))

        quick_replies.append(kr.make_quick_reply("상담원 연결"))

        log_chat(user_id, utterance, f"[되묻기] {message}", source="ai_disambig")
        return kr.simple_text(text=message, quick_replies=quick_replies)

    else:
        # 일반 답변
        answer = ai_result.get("text", "")
        log_chat(user_id, utterance, answer, source="ai")
        return kr.simple_text(
            text=answer,
            quick_replies=[
                kr.make_quick_reply("다른 질문하기", "처음으로"),
                kr.make_quick_reply("상담원 연결"),
            ],
        )


# ── 관리자 API 라우터 ──

admin_router = APIRouter(prefix="/admin", tags=["admin"])


def verify_admin(x_admin_key: Optional[str] = Header(None)):
    if x_admin_key != settings.ADMIN_API_KEY:
        raise HTTPException(status_code=403, detail="인증 실패")


@admin_router.get("/knowledge")
async def api_list_knowledge(x_admin_key: Optional[str] = Header(None)):
    verify_admin(x_admin_key)
    items = list_knowledge()
    return {"items": items, "count": len(items)}


@admin_router.post("/knowledge")
async def api_add_knowledge(request: Request, x_admin_key: Optional[str] = Header(None)):
    verify_admin(x_admin_key)
    data = await request.json()
    for field in ["question", "answer"]:
        if field not in data:
            raise HTTPException(status_code=400, detail=f"'{field}' 필드 필요")
    new_id = add_knowledge(
        category=data.get("category", "일반"),
        question=data["question"],
        answer=data["answer"],
        keywords=data.get("keywords", ""),
    )
    return {"id": new_id, "message": "추가 완료"}


@admin_router.put("/knowledge/{knowledge_id}")
async def api_update_knowledge(
    knowledge_id: int, request: Request, x_admin_key: Optional[str] = Header(None)
):
    verify_admin(x_admin_key)
    data = await request.json()
    if not update_knowledge(knowledge_id, **data):
        raise HTTPException(status_code=404, detail="해당 항목 없음")
    return {"message": "수정 완료"}


@admin_router.delete("/knowledge/{knowledge_id}")
async def api_delete_knowledge(
    knowledge_id: int, x_admin_key: Optional[str] = Header(None)
):
    verify_admin(x_admin_key)
    if not delete_knowledge(knowledge_id):
        raise HTTPException(status_code=404, detail="해당 항목 없음")
    return {"message": "삭제 완료"}


@admin_router.post("/knowledge/bulk")
async def api_bulk_insert(request: Request, x_admin_key: Optional[str] = Header(None)):
    verify_admin(x_admin_key)
    items = await request.json()
    if not isinstance(items, list):
        raise HTTPException(status_code=400, detail="JSON 배열 형식 필요")
    count = bulk_insert_knowledge(items)
    return {"message": f"{count}건 추가 완료"}


@admin_router.get("/logs")
async def api_get_logs(limit: int = 50, x_admin_key: Optional[str] = Header(None)):
    verify_admin(x_admin_key)
    return {"logs": get_recent_logs(limit)}
