"""
웹훅 라우터
"""

import re
import httpx
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

PHONE_PATTERN = re.compile(r'01[016789]\d{7,8}')

TEAMS_WEBHOOK_URL = "https://defaulte88931741bb4474d856effc3a3d992.ee.environment.api.powerplatform.com:443/powerautomate/automations/direct/workflows/387e0d861e2d442f8dc30d6fe471b745/triggers/manual/paths/invoke?api-version=1&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0&sig=kOTe2ECVRm62P8Zol4653vs4mcOIgvP6HHdwpgRIgwk"


def has_phone_number(text):
    cleaned = text.replace("-", "").replace(" ", "").replace(".", "")
    return bool(PHONE_PATTERN.search(cleaned))


def send_teams_notification(utterance):
    """팀즈 그룹 채팅방에 문의 접수 알림 전송"""
    try:
        parts = utterance.replace("/", " ").split()
        phone_found = ""
        name_found = ""
        content_parts = []
        for p in parts:
            cleaned = p.replace("-", "")
            if cleaned.isdigit() and len(cleaned) >= 10:
                phone_found = p
            elif not name_found and not cleaned.isdigit():
                name_found = p
            else:
                content_parts.append(p)
        content = " ".join(content_parts) if content_parts else "내용 없음"

        message = {
            "type": "message",
            "attachments": [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": {
                        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                        "type": "AdaptiveCard",
                        "version": "1.4",
                        "body": [
                            {
                                "type": "TextBlock",
                                "text": "📋 새 문의 접수",
                                "weight": "Bolder",
                                "size": "Medium",
                                "color": "Attention"
                            },
                            {
                                "type": "FactSet",
                                "facts": [
                                    {"title": "이름", "value": name_found or "미입력"},
                                    {"title": "연락처", "value": phone_found or "미입력"},
                                    {"title": "문의내용", "value": content}
                                ]
                            },
                            {
                                "type": "TextBlock",
                                "text": "👉 [문의 접수함 확인](https://sedam-chatbot.onrender.com/admin/page)",
                                "wrap": True,
                                "spacing": "Medium"
                            }
                        ]
                    }
                }
            ]
        }

        with httpx.Client(timeout=5) as client:
            client.post(TEAMS_WEBHOOK_URL, json=message)
    except Exception as e:
        print(f"[Teams 알림 실패] {e}")


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

    # ── 처음으로 / 시작 ──
    if utterance in ("처음으로", "시작", "메뉴"):
        return kr.simple_text(
            text=f"안녕하세요! 😊 {settings.BOT_NAME}입니다.\n무엇을 도와드릴까요?",
            quick_replies=[
                kr.make_quick_reply("질문하기"),
                kr.make_quick_reply("상담원 연결"),
                kr.make_quick_reply("문의하기"),
            ],
        )

    # ── 질문하기 ──
    if utterance == "질문하기":
        return kr.simple_text(
            text="궁금한 내용을 자유롭게 질문해 주세요! 😊\n\n예시:\n- 프리랜서 세금 어떻게 떼나요?\n- 4대보험 가입 기준이 어떻게 되나요?\n- 부가세 신고 기한이 언제예요?",
        )

    # ── 문의하기 ──
    if utterance == "문의하기":
        return kr.simple_text(
            text="이름, 연락처, 문의내용을 남겨주시면\n기장사업부에서 확인 후 최대한 빨리 연락드릴게요! 😊\n\n예시: 홍길동 010-1234-5678 프리랜서 세금 관련 문의",
        )

    # ── 문의 접수 감지 (전화번호가 포함된 메시지) ──
    if has_phone_number(utterance):
        log_chat(user_id, utterance, "[문의 접수 완료]", source="inquiry")
        send_teams_notification(utterance)
        return kr.simple_text(
            text="문의가 접수되었습니다! ✅\n기장사업부에서 확인 후 최대한 빨리 연락드리겠습니다.\n\n감사합니다 😊",
            quick_replies=[
                kr.make_quick_reply("질문하기"),
                kr.make_quick_reply("처음으로"),
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
                text=f"지금은 기장사업부 업무시간이 아닙니다.\n(업무시간: 평일 09:00~{close_text})\n\n전화가 어려우시면 문의를 남겨주세요! 😊",
                quick_replies=[
                    kr.make_quick_reply("문의하기"),
                    kr.make_quick_reply("처음으로"),
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
                kr.make_quick_reply("질문하기"),
                kr.make_quick_reply("상담원 연결"),
                kr.make_quick_reply("문의하기"),
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
