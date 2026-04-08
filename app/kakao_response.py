"""
카카오 i 오픈빌더 응답 JSON 포맷 빌더

카카오 스킬 응답 형식:
{
    "version": "2.0",
    "template": {
        "outputs": [...],
        "quickReplies": [...]
    }
}
"""
from typing import Optional


class KakaoResponse:
    """카카오 오픈빌더 스킬 응답 빌더"""

    @staticmethod
    def simple_text(text: str, quick_replies: Optional[list[dict]] = None) -> dict:
        """
        단순 텍스트 응답을 생성합니다.

        Args:
            text: 응답 텍스트 (최대 1000자)
            quick_replies: 바로가기 응답 버튼 리스트
        """
        response = {
            "version": "2.0",
            "template": {
                "outputs": [
                    {
                        "simpleText": {
                            "text": text
                        }
                    }
                ]
            }
        }

        if quick_replies:
            response["template"]["quickReplies"] = quick_replies

        return response

    @staticmethod
    def simple_image(image_url: str, alt_text: str) -> dict:
        """단순 이미지 응답을 생성합니다."""
        return {
            "version": "2.0",
            "template": {
                "outputs": [
                    {
                        "simpleImage": {
                            "imageUrl": image_url,
                            "altText": alt_text
                        }
                    }
                ]
            }
        }

    @staticmethod
    def basic_card(
        title: str,
        description: str,
        thumbnail_url: Optional[str] = None,
        buttons: Optional[list[dict]] = None,
    ) -> dict:
        """기본 카드형 응답을 생성합니다."""
        card = {
            "title": title,
            "description": description,
        }

        if thumbnail_url:
            card["thumbnail"] = {"imageUrl": thumbnail_url}

        if buttons:
            card["buttons"] = buttons

        return {
            "version": "2.0",
            "template": {
                "outputs": [
                    {"basicCard": card}
                ]
            }
        }

    @staticmethod
    def text_with_quick_replies(text: str, reply_labels: list[str]) -> dict:
        """텍스트 + 바로가기 버튼 응답을 생성합니다."""
        quick_replies = [
            {
                "messageText": label,
                "action": "message",
                "label": label,
            }
            for label in reply_labels
        ]

        return KakaoResponse.simple_text(text, quick_replies)

    @staticmethod
    def callback_response() -> dict:
        """
        콜백 활성화 응답을 반환합니다.
        5초 이내에 응답을 줄 수 없을 때 사용합니다.
        """
        return {
            "version": "2.0",
            "useCallback": True,
            "template": {
                "outputs": [
                    {
                        "simpleText": {
                            "text": "잠시만 기다려 주세요. 답변을 준비하고 있습니다... 💬"
                        }
                    }
                ]
            }
        }

    @staticmethod
    def make_weblink_button(label: str, url: str) -> dict:
        return {"action": "webLink", "label": label, "webLinkUrl": url}

    @staticmethod
    def make_message_button(label: str, message_text: str) -> dict:
        return {"action": "message", "label": label, "messageText": message_text}

    @staticmethod
    def make_phone_button(label: str, phone_number: str) -> dict:
        return {"action": "phone", "label": label, "phoneNumber": phone_number}
