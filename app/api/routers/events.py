"""Журнал воронки со стороны Mini App: события, о которых знает только фронт.

Почти все значимые факты сервер узнаёт сам — по запросу за видео, по активации подписки.
Пэйволл — исключение: доступа нет, подарок потрачен, и фронт рисует шторку «оплатите», не
спрашивая никого. Сервер об этой развилке не узнавал НИКОГДА, поэтому счётчик `paywall`
стоял на нуле всё время своего существования, создавая иллюзию, что в стену никто не
упирается. Эта ручка и есть недостающая половина метрики.

Гейта подписки тут нет намеренно: событие пишет как раз тот, у кого доступа нет.
"""

from __future__ import annotations

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps.auth import get_current_user
from app.api.deps.rate_limit import rate_limit
from app.application.services.activity_service import UserActivityService
from app.domain.entities.user import User

# Rate-limit (данные): пэйволл человек видит по нескольку раз за заход (потыкал разные
# фильмы), поэтому лимит щедрее обычных write-ручек, но потолок нужен — ручка пишет
# строки в журнал от имени любого авторизованного. Ключ — IP (см. api/deps/rate_limit.py).
_rate_limited = Depends(rate_limit(limit=60, window_seconds=60, scope="events"))

router = APIRouter(prefix="/api/events", tags=["events"], route_class=DishkaRoute)


class PaywallIn(BaseModel):
    """Какой фильм упёрся в стену. None — пэйволл открыт не с карточки (кнопка в профиле)."""

    movie_id: int | None = None


@router.post("/paywall", status_code=204, dependencies=[_rate_limited])
async def track_paywall(
    body: PaywallIn,
    activity: FromDishka[UserActivityService],
    user: User = Depends(get_current_user),
) -> None:
    """Записать «показан пэйволл». Ответ пустой: фронт шлёт это фоном и результата не ждёт.

    Возврат `None`, а не `Response(204)`: при 204 FastAPI запрещает описанное тело ответа,
    и аннотация `-> Response` роняет приложение прямо на регистрации маршрута (assert в
    `_populate_api_route_state`). Так же сделаны 204-ручки избранного.
    """
    await activity.register_paywall(user.telegram_id, body.movie_id)
