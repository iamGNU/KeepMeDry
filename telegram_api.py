"""Minimal Telegram Bot API client.

Errors never include the request URL, because it contains the bot token.
"""

import requests


class TelegramError(Exception):
    def __init__(self, description: str, code: int | None = None):
        super().__init__(description)
        self.code = code


class BotBlocked(TelegramError):
    """The user blocked the bot or deleted their account."""


class TelegramAPI:
    def __init__(self, token: str):
        self._base = f"https://api.telegram.org/bot{token}/"

    def _call(self, method: str, payload: dict):
        try:
            response = requests.post(self._base + method, json=payload, timeout=30)
            result = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise TelegramError(f"{method}: {type(exc).__name__}") from None
        if not result.get("ok"):
            code = result.get("error_code")
            description = f"{method}: {result.get('description', 'unknown error')}"
            if code == 403:
                raise BotBlocked(description, code)
            raise TelegramError(description, code)
        return result["result"]

    def get_updates(self, offset: int) -> list[dict]:
        return self._call(
            "getUpdates",
            {"offset": offset, "timeout": 0, "allowed_updates": ["message"]},
        )

    def send_message(self, chat_id: int | str, text: str, reply_markup: dict | None = None) -> None:
        payload = {"chat_id": chat_id, "text": text}
        if reply_markup:
            payload["reply_markup"] = reply_markup
        self._call("sendMessage", payload)
