"""FastAPI-зависимость rate-limit поверх порта `RateLimiter`.

Фабрика `rate_limit(limit, window_seconds, scope)` → зависимость, которую вешают на
роутер/эндпоинт через `Depends`. Ключ — клиент: за reverse-proxy (Caddy) это реальный IP из
`X-Forwarded-For` (первый в списке), в dev — прямой `request.client`. Ключуем по IP
осознанно: лимит применяется ДО резолва сессии (даже несмотря на сессии 11.1) — так он
работает и для анонимных/битых запросов, не завися от auth.
⚠️ Мобильные юзеры Telegram часто за одним CGNAT-IP → лимиты держим щедрыми, чтобы
не ловить ложные 429 (более точную пер-юзер справедливость дал бы ключ из сессии).

Fail-open живёт в адаптере (`RedisRateLimiter`): Redis down → `hit` вернёт True →
эта зависимость никого не блокирует.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from dishka import AsyncContainer
from fastapi import HTTPException, Request

from app.application.ports.rate_limit import RateLimiter


def _client_key(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        # Reverse-proxy кладёт цепочку "client, proxy1, ..."; берём исходный клиентский IP.
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def rate_limit(
    limit: int, window_seconds: int = 1, scope: str = "api"
) -> Callable[[Request], Awaitable[None]]:
    async def dependency(request: Request) -> None:
        container: AsyncContainer = request.state.dishka_container
        limiter = await container.get(RateLimiter)
        key = f"{scope}:{_client_key(request)}"
        if not await limiter.hit(key, limit, window_seconds):
            raise HTTPException(status_code=429, detail="too_many_requests")

    return dependency
