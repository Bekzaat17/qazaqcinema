"""FastAPI-зависимость авторизации по Telegram initData.

initData приходит в заголовке Authorization. Достаём request-scope контейнер dishka
(его кладёт middleware setup_dishka в request.state.dishka_container) и валидируем
через AuthService. Невалидный initData → 401.
"""

from __future__ import annotations

from datetime import UTC, datetime

from dishka import AsyncContainer
from fastapi import Depends, Header, HTTPException, Request

from app.application.ports.security import InitDataError
from app.application.services.auth_service import AuthService
from app.domain.entities.user import User


async def get_current_user(
    request: Request,
    authorization: str = Header(..., description="Telegram WebApp initData"),
) -> User:
    container: AsyncContainer = request.state.dishka_container
    auth = await container.get(AuthService)
    try:
        return await auth.authenticate(authorization)
    except InitDataError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


async def require_active_access(user: User = Depends(get_current_user)) -> User:
    """Гейт «только подписчикам»: 403, если нет активной подписки.

    Единый источник правды — `User.has_active_access` (Фаза 6). Просмотр каталога
    свободный, поэтому вешается точечно на эндпоинты с контентом по подписке.
    """
    if not user.has_active_access(datetime.now(UTC)):
        raise HTTPException(status_code=403, detail="no_access")
    return user
