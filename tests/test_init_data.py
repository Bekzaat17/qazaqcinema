from __future__ import annotations

import hashlib
import hmac
import json
from urllib.parse import urlencode

import pytest
from app.application.ports.security import InitDataError
from app.infrastructure.telegram.init_data import TelegramInitDataVerifier
from pydantic import SecretStr

TOKEN = "123456:TESTTOKEN"
AUTH_DATE = 1_700_000_000
FRESH_NOW = AUTH_DATE + 60  # спустя минуту после выдачи — в пределах TTL


def _sign(fields: dict[str, str], token: str = TOKEN) -> str:
    """Подписать произвольный набор полей ключом бота (как это делает Telegram)."""
    data_check_string = "\n".join(f"{k}={fields[k]}" for k in sorted(fields))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    signature = hmac.new(secret, data_check_string.encode(), hashlib.sha256).hexdigest()
    return urlencode({**fields, "hash": signature})


def _make_init_data(
    user: dict[str, object], token: str = TOKEN, auth_date: int = AUTH_DATE
) -> str:
    return _sign({"auth_date": str(auth_date), "user": json.dumps(user)}, token)


def test_valid_init_data_returns_user() -> None:
    verifier = TelegramInitDataVerifier(SecretStr(TOKEN))
    user = verifier.verify(_make_init_data({"id": 42, "username": "neo"}), now=FRESH_NOW)
    assert user.id == 42
    assert user.username == "neo"


def test_tampered_init_data_rejected() -> None:
    verifier = TelegramInitDataVerifier(SecretStr(TOKEN))
    tampered = _make_init_data({"id": 42}).replace("42", "43")
    with pytest.raises(InitDataError):
        verifier.verify(tampered, now=FRESH_NOW)


def test_wrong_token_rejected() -> None:
    init_data = _make_init_data({"id": 42})
    verifier = TelegramInitDataVerifier(SecretStr("999999:OTHER"))
    with pytest.raises(InitDataError):
        verifier.verify(init_data, now=FRESH_NOW)


def test_expired_init_data_rejected() -> None:
    # Валидная подпись, но auth_date старше TTL → реплей отклонён.
    verifier = TelegramInitDataVerifier(SecretStr(TOKEN), max_age_seconds=86400)
    init_data = _make_init_data({"id": 42})
    with pytest.raises(InitDataError):
        verifier.verify(init_data, now=AUTH_DATE + 86401)


def test_fresh_init_data_within_ttl_ok() -> None:
    verifier = TelegramInitDataVerifier(SecretStr(TOKEN), max_age_seconds=86400)
    user = verifier.verify(_make_init_data({"id": 42}), now=AUTH_DATE + 86399)
    assert user.id == 42


def test_missing_auth_date_rejected() -> None:
    # Корректно подписан, но без auth_date — свежесть не проверить → отклоняем.
    verifier = TelegramInitDataVerifier(SecretStr(TOKEN))
    signed = _sign({"user": json.dumps({"id": 42})})
    with pytest.raises(InitDataError):
        verifier.verify(signed, now=FRESH_NOW)
