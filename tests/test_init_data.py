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


def _make_init_data(user: dict[str, object], token: str = TOKEN) -> str:
    fields = {"auth_date": "1700000000", "user": json.dumps(user)}
    data_check_string = "\n".join(f"{k}={fields[k]}" for k in sorted(fields))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    signature = hmac.new(secret, data_check_string.encode(), hashlib.sha256).hexdigest()
    return urlencode({**fields, "hash": signature})


def test_valid_init_data_returns_user() -> None:
    verifier = TelegramInitDataVerifier(SecretStr(TOKEN))
    user = verifier.verify(_make_init_data({"id": 42, "username": "neo"}))
    assert user.id == 42
    assert user.username == "neo"


def test_tampered_init_data_rejected() -> None:
    verifier = TelegramInitDataVerifier(SecretStr(TOKEN))
    tampered = _make_init_data({"id": 42}).replace("42", "43")
    with pytest.raises(InitDataError):
        verifier.verify(tampered)


def test_wrong_token_rejected() -> None:
    init_data = _make_init_data({"id": 42})
    verifier = TelegramInitDataVerifier(SecretStr("999999:OTHER"))
    with pytest.raises(InitDataError):
        verifier.verify(init_data)
