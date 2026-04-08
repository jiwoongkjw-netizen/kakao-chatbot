#!/usr/bin/env python3
"""
로컬 테스트 스크립트

서버 실행 후 이 스크립트로 웹훅 동작을 확인할 수 있습니다.

사용법:
  1. 서버 실행:  uvicorn app.main:app --reload
  2. 테스트:     python test_webhook.py
"""

import httpx
import json
import sys

BASE_URL = "http://localhost:8000"


def make_kakao_payload(utterance: str) -> dict:
    """카카오 오픈빌더가 보내는 것과 동일한 형식의 테스트 페이로드"""
    return {
        "userRequest": {
            "timezone": "Asia/Seoul",
            "utterance": utterance,
            "lang": "ko",
            "user": {
                "id": "test_user_001",
                "type": "botUserKey",
                "properties": {
                    "plusfriendUserKey": "test_plusfriend_001"
                }
            }
        },
        "bot": {
            "id": "test_bot",
            "name": "테스트봇"
        },
        "action": {
            "name": "test_skill",
            "clientExtra": None,
            "params": {},
            "id": "test_action",
            "detailParams": {}
        }
    }


def test_health():
    """헬스체크 테스트"""
    print("=" * 50)
    print("[1] 헬스체크 테스트")
    print("=" * 50)
    r = httpx.get(f"{BASE_URL}/health")
    print(f"상태: {r.status_code}")
    print(json.dumps(r.json(), indent=2, ensure_ascii=False))
    print()


def test_webhook(utterance: str):
    """웹훅 테스트"""
    print(f"[발화] \"{utterance}\"")
    payload = make_kakao_payload(utterance)
    r = httpx.post(f"{BASE_URL}/webhook", json=payload, timeout=10.0)
    result = r.json()

    # 응답에서 텍스트 추출
    outputs = result.get("template", {}).get("outputs", [])
    for output in outputs:
        if "simpleText" in output:
            print(f"[응답] {output['simpleText']['text']}")
        elif "basicCard" in output:
            card = output["basicCard"]
            print(f"[카드] {card.get('title', '')} - {card.get('description', '')}")

    quick_replies = result.get("template", {}).get("quickReplies", [])
    if quick_replies:
        labels = [qr["label"] for qr in quick_replies]
        print(f"[바로가기] {', '.join(labels)}")

    print()


def test_admin_api():
    """관리자 API 테스트"""
    print("=" * 50)
    print("[3] 관리자 API 테스트")
    print("=" * 50)
    headers = {"X-Admin-Key": "your-admin-secret-key-change-this"}

    # FAQ 목록 조회
    r = httpx.get(f"{BASE_URL}/admin/knowledge", headers=headers)
    data = r.json()
    print(f"등록된 FAQ: {data['count']}건")

    # FAQ 추가
    r = httpx.post(
        f"{BASE_URL}/admin/knowledge",
        headers=headers,
        json={
            "category": "테스트",
            "question": "테스트 질문입니다",
            "answer": "테스트 답변입니다.",
            "keywords": "테스트,시험"
        }
    )
    print(f"FAQ 추가: {r.json()}")

    # 대화 로그 조회
    r = httpx.get(f"{BASE_URL}/admin/logs?limit=5", headers=headers)
    logs = r.json().get("logs", [])
    print(f"최근 대화 로그: {len(logs)}건")
    print()


if __name__ == "__main__":
    try:
        # 1. 헬스체크
        test_health()

        # 2. 웹훅 테스트
        print("=" * 50)
        print("[2] 웹훅 테스트")
        print("=" * 50)

        test_cases = [
            "처음으로",
            "영업시간이 어떻게 되나요?",
            "상담 예약하고 싶어요",
            "부가세 신고 기한",
            "경정청구가 뭔가요",
            "상담원 연결",
            "법인 설립 비용이 얼마예요?",  # DB에 정확히 없는 질문 → AI 답변
        ]

        for case in test_cases:
            test_webhook(case)

        # 3. 관리자 API
        test_admin_api()

        print("✅ 모든 테스트 완료!")

    except httpx.ConnectError:
        print("❌ 서버에 연결할 수 없습니다.")
        print("   먼저 서버를 실행하세요: uvicorn app.main:app --reload")
        sys.exit(1)
