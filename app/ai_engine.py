"""
Claude AI 답변 생성 엔진 (v3 — 프롬프트 캐싱 적용)
"""

import json
import anthropic
import asyncio
from functools import partial
from app.config import settings
from app.knowledge_db import get_all_knowledge_as_context


client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

_cached_system_prompt = None


TAX_TERM_DICTIONARY = """
## 납세자 표현 → 세무 용어 매핑 사전

[원천세/급여]
- "3.3 떼는 거", "삼쩜삼", "프리랜서 세금" → 사업소득 원천징수 (3.3%)
- "8.8 떼는 거", "일당 세금" → 기타소득 원천징수 (8.8%)
- "세금 안 떼고 줬어요" → 원천징수 누락
- "알바 세금" → 일용직 또는 사업소득 원천징수
- "월급에서 빠지는 거" → 근로소득세 원천징수 + 4대보험료 공제

[4대보험]
- "보험 넣어야 해요?" → 4대보험 의무가입 여부
- "사장님 보험" → 대표자 4대보험
- "부양가족으로" → 건강보험 피부양자
- "보험 빼주세요" → 4대보험 상실신고
- "두루누리" → 두루누리 사회보험료 지원

[부가세]
- "부가세 언제" → 부가가치세 신고납부 기한
- "계산서 발행" → 세금계산서 발급
- "매입 공제" → 매입세액공제
- "간이과세" → 간이과세자

[소득세/법인세]
- "종소세", "5월 세금" → 종합소득세 신고
- "세금 돌려받는 거" → 경정청구 또는 연말정산 환급
- "비용처리" → 필요경비 산입
- "가산세" → 각종 가산세
"""


DISAMBIGUATION_INSTRUCTIONS = """
## 모호한 질문 처리

### 해석이 하나면 → 바로 답변
### 해석이 2~3개면 → 아래 JSON으로만 응답:
```
{
  "type": "disambiguation",
  "message": "어떤 부분이 궁금하신 건지 좀 더 여쭤볼게요! 😊",
  "options": [
    {"label": "선택지1", "description": "설명"},
    {"label": "선택지2", "description": "설명"}
  ]
}
```
### FAQ에 없으면 → "해당 내용은 정확한 확인이 필요한 사항이에요 📋 세담택스 기장사업부(031-657-0187)에서 확인 후 연락드릴게요!"
### 오타 교정 → "부과세"→"부가세", "4대보헌"→"4대보험"
"""


def build_system_prompt():
    global _cached_system_prompt
    if _cached_system_prompt:
        return _cached_system_prompt

    knowledge_context = get_all_knowledge_as_context()

    _cached_system_prompt = f"""당신은 '{settings.BOT_NAME}'입니다.
{settings.BOT_DESCRIPTION}

## 역할
- 카카오톡 채널을 통해 세무 관련 고객 문의에 친절하고 정확하게 답변합니다.
- 납세자는 세무 용어를 잘 모릅니다. 일상적 표현으로 질문합니다.
- 아래 [용어 매핑 사전]을 참고하여 사용자의 의도를 정확히 파악하세요.
- 반드시 [참조 FAQ]에 있는 내용만을 기반으로 답변하세요.
- FAQ에서 질문과 정확히 관련된 항목을 찾아서 답변하세요. 비슷해 보여도 질문의 핵심이 다르면 해당 FAQ를 사용하지 마세요.
- FAQ에 관련 내용이 없거나 질문에 정확히 맞는 답변을 찾을 수 없으면 절대 추측하거나 자체 지식으로 답변하지 마세요.
- FAQ에 없는 질문에는 반드시 이렇게만 답변하세요: "해당 내용은 정확한 확인이 필요한 사항이에요 📋 세담택스 기장사업부(031-657-0187)에서 확인 후 연락드릴게요!"

## 답변 스타일
- 카카오톡 대화하듯 편안하고 따뜻하게 답변하세요
- 적절한 이모지를 사용하세요 (😊 📋 ✅ 💡 📞 등, 답변당 2~3개)
- 반드시 300자 이내로 답변하세요
- "~드려요", "~이에요", "~해주시면 돼요" 같은 부드러운 말투
- 모든 답변 마지막에: "😊 자세한 내용은 세담택스 기장사업부로 연락주시면 친절하게 답변드릴게요!"

{TAX_TERM_DICTIONARY}

{DISAMBIGUATION_INSTRUCTIONS}

## 참조 FAQ
{knowledge_context}
"""
    return _cached_system_prompt


async def generate_ai_response(user_message):
    try:
        loop = asyncio.get_event_loop()
        raw_response = await asyncio.wait_for(
            loop.run_in_executor(None, partial(_call_claude, user_message)),
            timeout=50.0,
        )
        return _parse_response(raw_response)

    except asyncio.TimeoutError:
        return {
            "type": "answer",
            "text": "해당 내용은 정확한 확인이 필요한 사항이에요 📋 세담택스 기장사업부(031-657-0187)에서 확인 후 연락드릴게요!"
        }
    except Exception as e:
        print(f"[AI Engine Error] {type(e).__name__}: {e}")
        return {
            "type": "answer",
            "text": "해당 내용은 정확한 확인이 필요한 사항이에요 📋 세담택스 기장사업부(031-657-0187)에서 확인 후 연락드릴게요!"
        }


def _call_claude(user_message):
    system_prompt = build_system_prompt()

    message = client.messages.create(
        model=settings.AI_MODEL,
        max_tokens=400,
        system=[
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"}
            }
        ],
        messages=[{"role": "user", "content": user_message}],
    )

    response_text = ""
    for block in message.content:
        if block.type == "text":
            response_text += block.text

    return response_text.strip()


def _parse_response(raw):
    if '"type"' in raw and '"disambiguation"' in raw:
        try:
            json_str = raw
            if "```" in raw:
                start = raw.find("{")
                end = raw.rfind("}") + 1
                json_str = raw[start:end]

            parsed = json.loads(json_str)
            if parsed.get("type") == "disambiguation":
                return parsed
        except (json.JSONDecodeError, KeyError):
            pass

    return {"type": "answer", "text": raw or "답변을 생성하지 못했습니다."}
