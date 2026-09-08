"""Pg-адаптер карточки юзера: доступ, подарочный фильм, флаги, счётчики для отчётов."""

from __future__ import annotations

from collections.abc import Collection
from datetime import datetime

from sqlalchemy import ColumnElement, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.analytics.events import EventKind
from app.domain.entities.enums import UserStatus
from app.domain.entities.user import User
from app.infrastructure.db.models import UserEventModel, UserModel
from app.infrastructure.db.sql import rowcount


def _user_to_domain(model: UserModel) -> User:
    return User(
        telegram_id=model.telegram_id,
        username=model.username,
        status=UserStatus(model.status),
        expires_at=model.expires_at,
        selected_tariff=model.selected_tariff,
        notifications_enabled=model.notifications_enabled,
        bot_started_at=model.bot_started_at,
        free_view_used_at=model.free_view_used_at,
        free_view_movie_id=model.free_view_movie_id,
        is_premium=model.is_premium,
    )


def _not_in(ids: Collection[int]) -> tuple[ColumnElement[bool], ...]:
    """Условие «кроме этих telegram_id» — пустой список не добавляет WHERE вовсе.

    Пустой `NOT IN ()` в SQL невалиден, а `NOT IN (NULL)` вернул бы 0 строк — поэтому
    именно кортеж условий, который разворачивается в `.where(*…)`.
    """
    return (UserModel.telegram_id.notin_(ids),) if ids else ()


class PgUserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, telegram_id: int) -> User | None:
        model = await self._session.get(UserModel, telegram_id)
        return _user_to_domain(model) if model else None

    async def upsert(self, user: User) -> User:
        values = {
            "telegram_id": user.telegram_id,
            "username": user.username,
            "status": user.status.value,
            "expires_at": user.expires_at,
            "selected_tariff": user.selected_tariff,
            "notifications_enabled": user.notifications_enabled,
            "is_premium": user.is_premium,
        }
        stmt = pg_insert(UserModel).values(**values)
        # notifications_enabled НЕ в set_ намеренно: upsert (логин/activate/expire/reject)
        # не должен трогать выбор юзера по рассылкам. Менять флаг — только set_notifications
        # (точечный UPDATE). На INSERT нового юзера значение берётся из values (default True).
        # `bot_started_at` — тоже НЕ здесь: это внешний факт (нажал /start / заблокировал
        # бота), а не часть карточки юзера. Попади он в upsert — вход в Mini App затирал бы
        # открытый чат в NULL, и человек снова видел бы кнопку «Ботты ашу».
        # Поля подарка (free_view_*) — по той же причине НЕ здесь ни в values, ни в set_:
        # их проставляет только атомарный `claim_free_view`. Попади они в upsert — активация
        # подписки или отказ модератора обнулили бы уже потраченный подарок, раздав второй.
        # `is_premium` — НАОБОРОТ, здесь и в values, и в set_: это часть карточки, которую
        # Telegram присылает в initData на каждом входе (как `username`), а не внешний факт.
        # Premium покупают и бросают, поэтому свежее значение из подписанного initData
        # всегда правдивее сохранённого. Вызовы без initData (`activate`, `expire`,
        # `/start`) передают сюда объект, прочитанный из БД, — то есть пишут своё же
        # значение и признак не сбрасывают.
        stmt = stmt.on_conflict_do_update(
            index_elements=["telegram_id"],
            set_={
                "username": stmt.excluded.username,
                "status": stmt.excluded.status,
                "expires_at": stmt.excluded.expires_at,
                "selected_tariff": stmt.excluded.selected_tariff,
                "is_premium": stmt.excluded.is_premium,
            },
        )
        await self._session.execute(stmt)
        await self._session.commit()
        return user

    async def list_expired(self, now: datetime) -> list[User]:
        stmt = select(UserModel).where(
            UserModel.status == UserStatus.ACTIVE.value,
            UserModel.expires_at.is_not(None),
            UserModel.expires_at < now,
        )
        result = await self._session.scalars(stmt)
        return [_user_to_domain(model) for model in result]

    async def set_bot_started(self, telegram_id: int, at: datetime | None) -> None:
        """Отметить, что чат с ботом открыт (`/start`), либо снять факт при недоставке.

        Одна ручка на оба случая: факт ровно один — «бот может писать этому человеку», —
        и меняют его две стороны, /start и провалившаяся отправка. Точечный UPDATE, а не
        upsert: остальные поля юзера тут ни при чём.
        """
        stmt = (
            update(UserModel)
            .where(UserModel.telegram_id == telegram_id)
            .values(bot_started_at=at)
        )
        await self._session.execute(stmt)
        await self._session.commit()

    async def claim_free_view(self, telegram_id: int, movie_id: int, now: datetime) -> bool:
        """Забрать право на подарочный фильм. True — забрали именно мы, False — уже потрачено.

        Ядро защиты от раздачи двух бесплатных фильмов. Проверка и запись — ОДИН
        `UPDATE ... WHERE free_view_used_at IS NULL`: сама СУБД сериализует конкурентов,
        и второй запрос увидит 0 строк. Схема «сначала SELECT, потом UPDATE» здесь не
        годится — два тапа по кнопке на плохой связи прошли бы проверку одновременно.
        """
        stmt = (
            update(UserModel)
            .where(UserModel.telegram_id == telegram_id, UserModel.free_view_used_at.is_(None))
            .values(free_view_used_at=now, free_view_movie_id=movie_id)
        )
        claimed = await rowcount(self._session, stmt) == 1
        await self._session.commit()
        return claimed

    async def release_free_view(self, telegram_id: int, movie_id: int) -> None:
        """Вернуть право, если подаренное видео так и не дошло (юзер не открыл чат с ботом).

        Без возврата человек терял бы подарок, ни разу его не увидев, — и упирался бы в
        пэйволл, так и не поняв, за что платит. Сверка по `movie_id` обязательна: за время
        неудачной отправки юзер мог успеть забрать подарок другим фильмом, и слепой сброс
        стёр бы уже состоявшийся подарок.
        """
        stmt = (
            update(UserModel)
            .where(UserModel.telegram_id == telegram_id, UserModel.free_view_movie_id == movie_id)
            .values(free_view_used_at=None, free_view_movie_id=None)
        )
        await self._session.execute(stmt)
        await self._session.commit()

    async def list_notifiable(self) -> list[int]:
        """telegram_id всех, кто согласен на рассылки о новинках (аудитория рассылки).

        Отдаём только id (не полные User) — рассылке больше ничего не нужно, а список
        может быть большим.
        """
        stmt = select(UserModel.telegram_id).where(
            UserModel.notifications_enabled.is_(True)
        )
        result = await self._session.scalars(stmt)
        return list(result)

    async def count_all(self, exclude: Collection[int] = ()) -> int:
        stmt = select(func.count()).select_from(UserModel).where(*_not_in(exclude))
        return int(await self._session.scalar(stmt) or 0)

    async def count_created_since(self, since: datetime, exclude: Collection[int] = ()) -> int:
        stmt = (
            select(func.count())
            .select_from(UserModel)
            .where(UserModel.created_at >= since, *_not_in(exclude))
        )
        return int(await self._session.scalar(stmt) or 0)

    async def count_active(self, now: datetime, exclude: Collection[int] = ()) -> int:
        """Активные подписки ПО ФАКТУ (`expires_at > now`), а не по колонке статуса.

        Статус гасит фоновый джоб раз в 15 минут, поэтому между прогонами ACTIVE-строк
        чуть больше, чем реально доступов. Отчёт должен показывать правду на момент
        отправки — тот же критерий, что и `User.has_active_access`.
        """
        stmt = (
            select(func.count())
            .select_from(UserModel)
            .where(
                UserModel.status == UserStatus.ACTIVE.value,
                UserModel.expires_at.is_not(None),
                UserModel.expires_at > now,
                *_not_in(exclude),
            )
        )
        return int(await self._session.scalar(stmt) or 0)

    async def count_premium(self, exclude: Collection[int] = ()) -> int:
        """Владельцев Telegram Premium в базе — прокси платёжеспособности аудитории."""
        stmt = (
            select(func.count())
            .select_from(UserModel)
            .where(UserModel.is_premium.is_(True), *_not_in(exclude))
        )
        return int(await self._session.scalar(stmt) or 0)

    async def count_returned(
        self,
        cohort_start: datetime,
        cohort_end: datetime,
        since: datetime,
        until: datetime,
        exclude: Collection[int] = (),
    ) -> int:
        """Из заведённых в `[cohort_start, cohort_end)` — сколько заходило в `[since, until)`.

        `EXISTS`, а не `JOIN` + `COUNT(DISTINCT)`: у одного человека за окно десятки
        `open`, и джойн раздул бы промежуточный результат, чтобы потом схлопнуть его
        обратно. `EXISTS` останавливается на первом же событии человека — ровно тот
        вопрос, который мы задаём («заходил ли вообще»).

        Событие берём `OPEN`, а не `START`: /start нажимают один раз, вернуться —
        значит снова ОТКРЫТЬ кинотеатр.
        """
        returned = (
            select(UserEventModel.id)
            .where(
                UserEventModel.user_id == UserModel.telegram_id,
                UserEventModel.kind == EventKind.OPEN.value,
                UserEventModel.created_at >= since,
                UserEventModel.created_at < until,
            )
            .exists()
        )
        stmt = (
            select(func.count())
            .select_from(UserModel)
            .where(
                UserModel.created_at >= cohort_start,
                UserModel.created_at < cohort_end,
                returned,
                *_not_in(exclude),
            )
        )
        return int(await self._session.scalar(stmt) or 0)

    async def set_notifications(self, telegram_id: int, enabled: bool) -> None:
        """Точечно переключить флаг рассылок (тумблер в профиле; worker → False при блоке).

        Единственный путь изменения `notifications_enabled` — upsert его сохраняет (см. выше).
        Точечный UPDATE без загрузки строки; несуществующий telegram_id → 0 строк (тихий no-op).
        """
        await self._session.execute(
            update(UserModel)
            .where(UserModel.telegram_id == telegram_id)
            .values(notifications_enabled=enabled)
        )
        await self._session.commit()
