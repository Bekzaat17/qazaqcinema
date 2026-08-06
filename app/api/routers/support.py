"""Обращение в поддержку из Mini App (`POST /api/support`).

Тонкий роутер: валидация формы — pydantic, доставка — `SupportService` (порт нотифаера).
Ручка write-типа и «дешёвая» для клиента, но дорогая для админов (каждый вызов пишет им
в личку), поэтому лимит строгий — см. `_rate_limited`.
"""

from __future__ import annotations

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps.auth import get_current_user
from app.api.deps.rate_limit import rate_limit
from app.application.ports.telegram import AdminsUnreachableError
from app.application.services.support_service import (
    MAX_MESSAGE_LEN,
    EmptySupportMessageError,
    SupportService,
)
from app.domain.entities.user import User

# Rate-limit (данные): 5 обращений за 10 минут на IP. Живому человеку хватает с запасом,
# а спам-скрипт не превращает личку админов в ленту.
_rate_limited = Depends(rate_limit(limit=5, window_seconds=600, scope="support"))

router = APIRouter(prefix="/api/support", tags=["support"], route_class=DishkaRoute)


class SupportIn(BaseModel):
    # min_length=3 — отсекает случайный тап «отправить» с одним символом.
    text: str = Field(min_length=3, max_length=MAX_MESSAGE_LEN)


class SupportOut(BaseModel):
    status: str = "sent"


@router.post("", response_model=SupportOut, dependencies=[_rate_limited])
async def submit_support(
    body: SupportIn,
    support: FromDishka[SupportService],
    user: User = Depends(get_current_user),
) -> SupportOut:
    """Отправить сообщение админам. 502 — если не дошло ни до одного (см. порт)."""
    try:
        await support.submit(user, body.text)
    except EmptySupportMessageError:
        raise HTTPException(status_code=400, detail="empty_message") from None
    except AdminsUnreachableError:
        # Не 500: сервис жив, недоступны получатели. Фронт просит повторить позже.
        raise HTTPException(status_code=502, detail="admins_unreachable") from None
    return SupportOut(status="sent")
