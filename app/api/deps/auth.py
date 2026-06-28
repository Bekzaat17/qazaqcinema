"""FastAPI-зависимость авторизации по Telegram initData.

initData приходит в заголовке Authorization. Достаём request-scope контейнер dishka
(его кладёт middleware setup_dishka в request.state.dishka_container) и валидируем
через AuthService. Невалидный initData → 401.
"""

from __future__ import annotations

from dishka import AsyncContainer
from fastapi import Header, HTTPException, Request

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
