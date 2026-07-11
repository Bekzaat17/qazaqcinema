"""Юнит-тест FastAPI-зависимости `rate_limit`: 429 при превышении, ключ по IP.

Порт RateLimiter — фейк (сам лимитер покрыт в test_cache.py). Здесь проверяем, что
зависимость: строит ключ по клиенту (предпочитая X-Forwarded-For за reverse-proxy) и
превращает «лимит исчерпан» в HTTP 429.
"""

from __future__ import annotations

import pytest
from app.api.deps.rate_limit import rate_limit
from fastapi import HTTPException
from starlette.requests import Request


class _FakeLimiter:
    def __init__(self, *, allowed: bool) -> None:
        self._allowed = allowed
        self.keys: list[str] = []

    async def hit(self, key: str, limit: int, window_seconds: int) -> bool:
        self.keys.append(key)
        return self._allowed


class _FakeContainer:
    def __init__(self, limiter: _FakeLimiter) -> None:
        self._limiter = limiter

    async def get(self, tp: object) -> _FakeLimiter:
        return self._limiter


def _request(container: _FakeContainer, *, xff: str | None, client_host: str) -> Request:
    headers = [(b"x-forwarded-for", xff.encode())] if xff else []
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": headers,
        "client": (client_host, 0),
        "state": {},
    }
    request = Request(scope)
    request.state.dishka_container = container
    return request


async def test_passes_under_limit() -> None:
    limiter = _FakeLimiter(allowed=True)
    dep = rate_limit(limit=5, window_seconds=1, scope="catalog")

    await dep(_request(_FakeContainer(limiter), xff=None, client_host="9.9.9.9"))  # не бросает

    assert limiter.keys == ["catalog:9.9.9.9"]


async def test_raises_429_over_limit() -> None:
    limiter = _FakeLimiter(allowed=False)
    dep = rate_limit(limit=5, window_seconds=1, scope="catalog")

    with pytest.raises(HTTPException) as exc:
        await dep(_request(_FakeContainer(limiter), xff=None, client_host="9.9.9.9"))

    assert exc.value.status_code == 429
    assert exc.value.detail == "too_many_requests"


async def test_prefers_forwarded_for_over_client() -> None:
    limiter = _FakeLimiter(allowed=True)
    dep = rate_limit(limit=5, window_seconds=1, scope="catalog")

    await dep(_request(_FakeContainer(limiter), xff="1.2.3.4, 10.0.0.1", client_host="9.9.9.9"))

    assert limiter.keys == ["catalog:1.2.3.4"]  # исходный клиент, не proxy
