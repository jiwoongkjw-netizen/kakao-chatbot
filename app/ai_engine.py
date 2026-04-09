"""
Claude AI 답변 생성 엔진 (v2 — 모호한 질문 처리 강화)

핵심 전략:
1. 용어 매핑 사전 → 납세자의 일상 표현을 세무 용어로 정규화
2. 의도 분기 감지 → 질문이 2개 이상 FAQ에 걸릴 때 선택지 제시
3. FAQ alias → 각 FAQ에 "이렇게도 물어볼 수 있다"는 변형 포함
"""

import json
import anthropic
import asyncio
from functools import partial
from app.config import settings
from app.knowledge_db import get_all_knowledge_as_context


client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)


# ──────────────────────────────────────────────
# 1단계: 납세자 일상 표현 → 세무 용어 매핑 사전
# ──────────────────────────────────────────────
TAX_TERM_DICTIONARY = """
## 납세자 표현 → 세무 용어 매핑 사전
아래는 납세자들이 실제로 자주 쓰는 표현과 그에 대응하는 세무 용어입니다.
사용자 발화에 이런 표현이 나오면 괄호 안의 세무 개념으로 해석하세요.

[원천세/급여 관련]
- "3.3 떼는 거", "삼쩜삼", "프리랜서 세금" → 사업소득 원천징수 (3.3%)
- "8.8 떼는 거", "일당 세금" → 기타소득 원천징수 (8.8%)
- "세금 안 떼고 줬어요" → 원천징수 누락, 사후 신고
- "알바 세금", "아르바이트 세금" → 일용직 또는 사업소득 원천징수
- "월급에서 빠지는 거" → 근로소득세 원천징수 + 4대보험료 공제
- "연봉 실수령" → 근로소득세 + 4대보험료 계산

[4대보험 관련]
- "보험 넣어야 해요?", "보험 가입" → 4대보험 의무가입 여부
- "사장님 보험", "대표 보험" → 대표자 4대보험 가입
- "남편/아내 밑으로", "부양가족으로" → 건강보험 피부양자 등록
- "보험료 왜 이렇게 많아요" → 4대보험 보험료 산정 기준, 건강보험 정산
- "보험 빼주세요", "퇴사 처리" → 4대보험 상실신고
- "두루누리", "지원금" → 두루누리 사회보험료 지원
- "보험 얼마나 나와요" → 4대보험 보험료 산정기준
- "알바도 보험?" → 단시간/일용 근로자 4대보험 가입 기준

[부가세 관련]
- "부가세 신고", "부가세 언제" → 부가가치세 신고납부 기한
- "세금계산서 끊어야", "계산서 발행" → 세금계산서 발급
- "매입 공제", "환급 받을 수 있어요?" → 매입세액공제
- "간이과세", "간이 → 일반" → 간이과세자 관련
- "차 샀는데 공제", "차량 부가세" → 차량 매입세액공제 (불공제 사유 포함)
- "식대 공제", "밥값 공제" → 복리후생비 매입세액공제
- "카드 매입", "카드로 산 거" → 신용카드 매입세액공제

[소득세/법인세 관련]
- "종소세", "5월 세금" → 종합소득세 신고
- "세금 돌려받는 거" → 경정청구 또는 연말정산 환급
- "세금 많이 나왔어요" → 세액 산출 구조, 절세 방법
- "비용처리", "경비처리" → 필요경비 산입
- "장부 써야 해요?" → 기장의무 (간편장부/복식부기)
- "성실신고" → 성실신고확인대상
- "가산세" → 각종 가산세 (무신고, 과소신고, 납부지연 등)
- "기한 놓쳤어요", "늦게 신고" → 기한후신고, 가산세
- "연말정산", "13월의 월급" → 근로소득 연말정산

[기타 자주 쓰는 표현]
- "세무사 상담", "직접 얘기하고 싶어요" → 상담원 연결
- "비용 얼마예요", "수수료" → 기장료/서비스 비용 안내
- "서류 뭐 필요해요" → 필요 서류 안내
- "언제까지 해야 해요" → 신고/납부 기한
"""


# ──────────────────────────────────────────────
# 2단계: 의도 분기 감지 로직 (시스템 프롬프트에 포함)
# ──────────────────────────────────────────────
DISAMBIGUATION_INSTRUCTIONS = """
## 모호한 질문 처리 규칙

사용자의 질문이 명확하지 않을 때는 아래 규칙을 따르세요.

### 규칙 1: 해석이 하나로 좁혀지면 → 바로 답변
"프리랜서 세금 어떻게 해요?" → 사업소득 원천징수 3.3% 설명

### 규칙 2: 해석이 2~3개로 갈리면 → 선택지 제시
이 경우 반드시 아래 JSON 형식으로만 응답하세요:
```
{
  "type": "disambiguation",
  "message": "어떤 부분이 궁금하신 건지 좀 더 여쭤볼게요!",
  "options": [
    {"label": "선택지1 (10자 이내)", "description": "부연설명"},
    {"label": "선택지2 (10자 이내)", "description": "부연설명"},
    {"label": "선택지3 (10자 이내)", "description": "부연설명"}
  ]
}
```

예시:
- "세금계산서 문의" → 발행 방법 / 수정 발행 / 가산세 중 뭘 묻는지 모름
- "보험 문의" → 가입 / 상실 / 보험료 / 피부양자 중 뭘 묻는지 모름
- "세금 돌려받고 싶어요" → 경정청구 / 연말정산 환급 / 부가세 환급 중 뭘 묻는지 모름

### 규칙 3: 아예 관련 FAQ가 없으면 → 솔직히 안내
"해당 부분은 정확한 상담이 필요합니다. 전화(02-XXXX-XXXX)로 문의해 주시면 자세히 안내드리겠습니다."

### 규칙 4: 질문에 오류가 있어도 교정하여 해석
- "부과세" → "부가세"로 해석
- "4대보헌" → "4대보험"으로 해석
- "원천징수세" → "원천세"로 해석
- 맞춤법, 띄어쓰기 오류는 무시하고 의도를 파악
"""


def build_system_prompt() -> str:
    """시스템 프롬프트 (용어 매핑 + 분기 로직 + FAQ 컨텍스트)"""
    knowledge_context = get_all_knowledge_as_context()

    return f"""당신은 '{settings.BOT_NAME}'입니다.
{settings.BOT_DESCRIPTION}

## 역할
- 카카오톡 채널을 통해 세무 관련 고객 문의에 친절하고 정확하게 답변합니다.
- 납세자는 세무 용어를 잘 모릅니다. 일상적 표현으로 질문합니다.
- 아래 [용어 매핑 사전]을 참고하여 사용자의 의도를 정확히 파악하세요.
- 반드시 [참조 FAQ]에 있는 내용만을 기반으로 답변하세요.
- FAQ에서 질문과 정확히 관련된 항목을 찾아서 답변하세요. 비슷해 보여도 질문의 핵심이 다르면 해당 FAQ를 사용하지 마세요.
- FAQ에 관련 내용이 없거나, 질문에 정확히 맞는 답변을 찾을 수 없으면 절대 추측하거나 자체 지식으로 답변하지 마세요.
- FAQ에 없는 질문에는 반드시 이렇게만 답변하세요: "해당 내용은 정확한 확인이 필요한 사항입니다. 세담택스 기장사업부(031-657-0187)에서 확인 후 연락드리겠습니다."## 역할
- 카카오톡 채널을 통해 세무 관련 고객 문의에 친절하고 정확하게 답변합니다.
- 납세자는 세무 용어를 잘 모릅니다. 일상적 표현으로 질문합니다.
- 아래 [용어 매핑 사전]을 참고하여 사용자의 의도를 정확히 파악하세요.
- 반드시 [참조 FAQ]에 있는 내용만을 기반으로 답변하세요.
- FAQ에서 질문과 정확히 관련된 항목을 찾아서 답변하세요. 비슷해 보여도 질문의 핵심이 다르면 해당 FAQ를 사용하지 마세요.
- FAQ에 관련 내용이 없거나, 질문에 정확히 맞는 답변을 찾을 수 없으면 절대 추측하거나 자체 지식으로 답변하지 마세요.
- FAQ에 없는 질문에는 반드시 이렇게만 답변하세요: "해당 내용은 정확한 확인이 필요한 사항입니다. 세담택스 기장사업부(031-657-0187)에서 확인 후 연락드리겠습니다."

## 답변 스타일
- 카카오톡 대화하듯 편안하고 따뜻하게 답변하세요
- 적절한 이모지를 사용하세요 (😊 📋 ✅ 💡 📞 등, 답변당 2~3개 정도)
- 너무 길지 않게 핵심만 간결하게 (200자 이내 권장)
- "~입니다", "~합니다" 보다는 "~드려요", "~이에요", "~해주시면 돼요" 같은 부드러운 말투
- 세무 용어를 쓸 때는 괄호로 쉬운 설명을 덧붙이세요
  예: "경정청구(이미 낸 세금을 돌려받는 절차)"
- 모든 답변 마지막에 반드시 이 문구를 추가하세요: "😊 자세한 내용은 세담택스 기장사업부로 연락주시면 친절하게 답변드릴게요!"

예시:
- 변경 전: "프리랜서에게 지급 시 3.3%를 원천징수해야 합니다."
- 변경 후: "프리랜서분께 지급하실 때는 3.3%를 떼고 지급해주시면 돼요! ✅"

{TAX_TERM_DICTIONARY}

{DISAMBIGUATION_INSTRUCTIONS}

## 참조 FAQ
{knowledge_context}
"""


async def generate_ai_response(user_message: str) -> dict:
    """
    Claude API를 호출하여 답변을 생성합니다.

    Returns:
        dict with either:
        - {{"type": "answer", "text": "답변 내용"}}
        - {{"type": "disambiguation", "message": "...", "options": [...]}}
    """
    try:
        loop = asyncio.get_event_loop()
        raw_response = await asyncio.wait_for(
            loop.run_in_executor(None, partial(_call_claude, user_message)),
            timeout=4.0,
        )
        return _parse_response(raw_response)

    except asyncio.TimeoutError:
        return {
            "type": "answer",
            "text": "죄송합니다. 답변 생성에 시간이 걸리고 있습니다. 잠시 후 다시 질문해 주세요."
        }
    except Exception as e:
        print(f"[AI Engine Error] {type(e).__name__}: {e}")
        return {
            "type": "answer",
            "text": "죄송합니다. 일시적인 오류가 발생했습니다."
        }


def _call_claude(user_message: str) -> str:
    """Claude API 동기 호출"""
    message = client.messages.create(
        model=settings.AI_MODEL,
        max_tokens=400,
        system=build_system_prompt(),
        messages=[{"role": "user", "content": user_message}],
    )

    response_text = ""
    for block in message.content:
        if block.type == "text":
            response_text += block.text

    return response_text.strip()


def _parse_response(raw: str) -> dict:
    """
    AI 응답을 파싱합니다.
    - disambiguation JSON이면 선택지 구조로 변환
    - 일반 텍스트면 그대로 answer로 반환
    """
    # JSON 블록이 포함되어 있는지 확인
    if '"type"' in raw and '"disambiguation"' in raw:
        try:
            # ```json ... ``` 블록 추출
            json_str = raw
            if "```" in raw:
                start = raw.find("{")
                end = raw.rfind("}") + 1
                json_str = raw[start:end]

            parsed = json.loads(json_str)
            if parsed.get("type") == "disambiguation":
                return parsed
        except (json.JSONDecodeError, KeyError):
            pass  # JSON 파싱 실패 시 일반 텍스트로 처리

    # 일반 답변
    return {"type": "answer", "text": raw or "답변을 생성하지 못했습니다."}
