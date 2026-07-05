"""FastAPI-зависимость авторизации Web App (двухрежимная — Фаза 11.1).

Заголовок Authorization несёт ЛИБО серверный сессионный токен (`session:<uuid>`, обычный
путь после bootstrap), ЛИБО сырой initData (bootstrap И фолбэк). Различаем по форме:
initData — это query-string (всегда содержит `=`), токен — hex uuid (без `=`).

Почему оба: сессия (Redis) быстрее и даёт свой TTL/ревок, но initData-путь оставлен как
**fail-open** — HMAC-валидация не требует Redis, поэтому падение Redis не ломает вход
(клиент просто шлёт initData). Контейнер dishka кладёт middleware в request.state.
"""

from __future__ import annotations

from datetime import UTC, datetime

from dishka import AsyncContainer
from fastapi import Depends, Header, HTTPException, Request

from app.application.ports.repositories import UserRepository
from app.application.ports.security import InitDataError
from app.application.ports.session import SessionStore
from app.application.services.auth_service import AuthService
from app.domain.entities.user import User


async def get_current_user(
    request: Request,
    authorization: str = Header(..., description="session-токен или Telegram initData"),
) -> User:
    container: AsyncContainer = request.state.dishka_container
    if "=" in authorization:
        # initData (bootstrap/фолбэк): stateless HMAC-валидация, Redis не нужен.
        auth = await container.get(AuthService)
        try:
            return await auth.authenticate(authorization)
        except InitDataError as exc:
            raise HTTPException(status_code=401, detail="invalid_init_data") from exc
    # Сессионный токен: смотрим Redis → грузим свежего User из БД (статус/срок — правда там).
    # Явные аннотации: dishka .get(Protocol) типизируется как Any, иначе теряем тип.
    sessions: SessionStore = await container.get(SessionStore)
    session = await sessions.get(authorization)
    if session is None:
        raise HTTPException(status_code=401, detail="session_expired")
    users: UserRepository = await container.get(UserRepository)
    user = await users.get(session.user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="session_expired")
    return user


async def require_active_access(user: User = Depends(get_current_user)) -> User:
    """Гейт «только подписчикам»: 403, если нет активной подписки.

    Единый источник правды — `User.has_active_access` (Фаза 6). Просмотр каталога
    свободный, поэтому вешается точечно на эндпоинты с контентом по подписке.
    """
    if not user.has_active_access(datetime.now(UTC)):
        raise HTTPException(status_code=403, detail="no_access")
    return user
