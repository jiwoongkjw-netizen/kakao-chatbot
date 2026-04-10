"""
웹훅 라우터
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


webhook_router = APIRouter()


@webhook_router.post("/webhook")
async def handle_kakao_webhook(request: Request):
    try:
        body = await request.json()
    except Exception:
        return kr.error_response()

    user_request = body.get("userRequest", {})
    utterance = user_request.get("utterance", "").strip()
    user_id = user_request.get("user", {}).get("id", "unknown")

    if not utterance:
        return kr.error_response("메시지를 인식하지 못했습니다. 다시 입력해 주세요.")

    # ── 카테고리 선택 ──
    category_map = {
        "원천세/급여 문의": "원천세",
        "원천세/급여": "원천세",
        "원천세": "원천세",
        "4대보험 문의": "4대보험",
        "4대보험": "4대보험",
        "사대보험": "4대보험",
        "사대보험 문의": "4대보험",
        "부가세 문의": "부가세",
        "부가세": "부가세",
        "부가가치세": "부가세",
        "소득세/법인세 문의": "소득세",
        "소득세/법인세": "소득세",
        "종합소득세": "소득세",
        "소득세": "소득세",
        "법인세": "소득세",
        "종소세": "소득세",
    }

    if utterance in category_map:
        return kr.simple_text(
            text=f"{utterance} 관련 궁금한 내용을 자유롭게 질문해 주세요!\n\n예시:\n- 프리랜서 세금 어떻게 떼나요?\n- 4대보험 가입 기준이 어떻게 되나요?\n- 부가세 신고 기한이 언제예요?",
            quick_replies=[
                kr.make_quick_reply("상담원 연결"),
                kr.make_quick_reply("처음으로"),
            ],
        )

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

    # ── 상담원 연결 ──
    if utterance in ("상담원 연결", "상담원", "사람", "직접 상담"):
        from datetime import datetime, timezone, timedelta
        kst = timezone(timedelta(hours=9))
        now = datetime.now(kst)
        weekday = now.weekday()
        hour = now.hour
        month = now.month

        if month in (1, 3, 5, 6, 7):
            close_hour = 18
        else:
            close_hour = 17

        if weekday < 5 and 9 <= hour < close_hour:
            return kr.basic_card(
                title="상담원 연결",
                description="아래 버튼을 눌러 전화 상담을 받으시거나,\n연락처를 남겨주시면 담당자가 확인 후 연락드리겠습니다.",
                buttons=[
                    kr.make_button_phone("전화 상담 031-657-0187", "031-657-0187"),
                ],
            )
        else:
            close_text = f"{close_hour}:00"
            return kr.simple_text(
                text=f"지금은 기장사업부 업무시간이 아닙니다.\n(업무시간: 평일 09:00~{close_text})\n\n업무시간에 다시 연락주시거나, 연락처를 남겨주시면 확인 후 연락드리겠습니다.",
                quick_replies=[
                    kr.make_quick_reply("질문하기", "처음으로"),
                ],
            )

    # ── Claude AI 호출 ──
    ai_result = await generate_ai_response(utterance)

    if ai_result["type"] == "disambiguation":
        message = ai_result.get("message", "어떤 부분이 궁금하신지 선택해 주세요!")
        options = ai_result.get("options", [])

        quick_replies = []
        for opt in options[:5]:
            label = opt.get("label", "")[:14]
            quick_replies.append(kr.make_quick_reply(label))

        quick_replies.append(kr.make_quick_reply("상담원 연결"))

        log_chat(user_id, utterance, f"[되묻기] {message}", source="ai_disambig")
        return kr.simple_text(text=message, quick_replies=quick_replies)

    else:
        answer = ai_result.get("text", "")
        if len(answer) > 900:
            answer = answer[:900] + "\n\n😊 자세한 내용은 세담택스 기장사업부로 연락주시면 친절하게 답변드릴게요!"
        log_chat(user_id, utterance, answer, source="ai")
        return kr.simple_text(
            text=answer,
            quick_replies=[
                kr.make_quick_reply("다른 질문하기", "처음으로"),
                kr.make_quick_reply("상담원 연결"),
            ],
        )


# ── 관리자 API ──

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
