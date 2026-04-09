"""카카오 i 오픈빌더 응답 JSON 포맷 빌더"""
from typing import Optional


class KakaoResponse:
    @staticmethod
    def simple_text(text, quick_replies=None):
        response = {
            "version": "2.0",
            "template": {
                "outputs": [{"simpleText": {"text": text}}]
            }
        }
        if quick_replies:
            response["template"]["quickReplies"] = quick_replies
        return response

    @staticmethod
    def basic_card(title, description, thumbnail_url=None, buttons=None):
        card = {"title": title, "description": description}
        if thumbnail_url:
            card["thumbnail"] = {"imageUrl": thumbnail_url}
        if buttons:
            card["buttons"] = buttons
        return {
            "version": "2.0",
            "template": {"outputs": [{"basicCard": card}]}
        }

    @staticmethod
    def make_quick_reply(label, message_text=None):
        return {
            "messageText": message_text or label,
            "action": "message",
            "label": label,
        }

    @staticmethod
    def make_phone_button(label, phone_number):
        return {"action": "phone", "label": label, "phoneNumber": phone_number}

    @staticmethod
    def error_response(message="죄송합니다. 일시적인 오류가 발생했습니다."):
        return KakaoResponse.simple_text(message)


simple_text = KakaoResponse.simple_text
basic_card = KakaoResponse.basic_card
make_quick_reply = KakaoResponse.make_quick_reply
make_button_phone = KakaoResponse.make_phone_button
error_response = KakaoResponse.error_response
