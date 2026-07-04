"""Валидация Telegram WebApp initData (HMAC-SHA256 по токену бота).

Алгоритм Telegram (Validating data received via the Mini App):
  secret_key   = HMAC_SHA256(key="WebAppData", msg=bot_token)
  check_hash   = HMAC_SHA256(key=secret_key,   msg=data_check_string)
  data_check_string — пары "key=value" (кроме hash), отсортированные по ключу, через \\n.
Реализовано полностью: это критично для безопасности.

Дополнительно проверяем свежесть `auth_date` (TTL): HMAC валиден вечно, поэтому без
проверки времени украденный/утёкший initData можно переигрывать бесконечно. `auth_date`
входит в data_check_string (подписан), так что подделать его нельзя — сверяем ПОСЛЕ HMAC.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

from pydantic import SecretStr

from app.application.ports.security import InitDataError, TelegramUser

_DEFAULT_MAX_AGE = 86400  # 24 ч — окно валидности initData против реплея


class TelegramInitDataVerifier:
    def __init__(self, bot_token: SecretStr, max_age_seconds: int = _DEFAULT_MAX_AGE) -> None:
        self._token = bot_token.get_secret_value()
        self._max_age_seconds = max_age_seconds

    def verify(self, init_data: str, *, now: float | None = None) -> TelegramUser:
        """Проверить подпись и свежесть initData; вернуть пользователя.

        `now` — только для тестов (по умолчанию текущее время); в проде не передаётся,
        поэтому сигнатура порта `verify(init_data)` остаётся совместимой.
        """
        try:
            pairs = dict(parse_qsl(init_data, strict_parsing=True))
        except ValueError as exc:
            raise InitDataError("битый init_data") from exc

        received_hash = pairs.pop("hash", None)
        if not received_hash:
            raise InitDataError("нет поля hash")

        data_check_string = "\n".join(f"{key}={pairs[key]}" for key in sorted(pairs))
        secret_key = hmac.new(b"WebAppData", self._token.encode(), hashlib.sha256).digest()
        calculated = hmac.new(
            secret_key, data_check_string.encode(), hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(calculated, received_hash):
            raise InitDataError("подпись initData не совпала")

        self._check_freshness(pairs.get("auth_date"), now)
        return self._extract_user(pairs.get("user"))

    def _check_freshness(self, raw_auth_date: str | None, now: float | None) -> None:
        if raw_auth_date is None:
            raise InitDataError("нет поля auth_date")
        try:
            auth_date = int(raw_auth_date)
        except ValueError as exc:
            raise InitDataError("auth_date не число") from exc
        current = time.time() if now is None else now
        if current - auth_date > self._max_age_seconds:
            raise InitDataError("initData просрочен")

    @staticmethod
    def _extract_user(raw_user: str | None) -> TelegramUser:
        if not raw_user:
            raise InitDataError("нет поля user")
        try:
            data = json.loads(raw_user)
        except json.JSONDecodeError as exc:
            raise InitDataError("user не является JSON") from exc
        user_id = data.get("id")
        if not isinstance(user_id, int):
            raise InitDataError("user.id отсутствует")
        return TelegramUser(
            id=user_id,
            username=data.get("username"),
            first_name=data.get("first_name"),
        )
