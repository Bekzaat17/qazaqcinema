"""Порты репозиториев (DIP). Сервисы зависят от этих Protocol, не от инфраструктуры.

Интерфейсы намеренно мелкие и раздельные (ISP): MovieRepository ≠ UserRepository ≠
PaymentRepository. Реализации — в app/infrastructure/db/repositories.py.
"""

from __future__ import annotations

from collections.abc import Collection
from datetime import datetime
from typing import Literal, Protocol

from app.domain.analytics.events import EventKind
from app.domain.entities.delivery import VideoDelivery
from app.domain.entities.enums import PaymentStatus
from app.domain.entities.movie import Movie
from app.domain.entities.subscription import PaymentRequest
from app.domain.entities.user import User

# Сортировка каталога (Фаза 13) — контракт между роутером, сервисом и репозиторием.
# Значения — белый список: репозиторий маппит их в колонки, сырую строку в SQL не пускаем.
SortField = Literal["year", "rating", "views"]  # year→год выпуска, rating→rating, views→play_count
SortDir = Literal["asc", "desc"]


class MovieRepository(Protocol):
    async def add(self, movie: Movie) -> Movie: ...
    async def get(self, movie_id: int) -> Movie | None: ...
    async def list_all(self, category: str | None = None) -> list[Movie]: ...
    async def search(self, query: str) -> list[Movie]: ...
    async def get_hero(self) -> Movie | None: ...

    async def list_hero_banners(self) -> list[Movie]:
        """Фильмы с горизонтальным баннером — пул ежедневной ротации hero.

        Только они и годятся на hero: без `hero_image_url` пришлось бы растягивать
        вертикальный постер. Выборка мелкая (баннер есть у единиц), поэтому целиком.
        """
        ...

    async def list_recent(self, limit: int) -> list[Movie]: ...
    async def list_popular(self, limit: int) -> list[Movie]: ...
    async def list_page(
        self,
        *,
        categories: list[str],
        sort: SortField,
        direction: SortDir,
        limit: int,
        offset: int,
    ) -> tuple[list[Movie], int]: ...
    async def category_counts(self) -> dict[str, int]: ...
    async def increment_play_count(self, movie_id: int) -> None: ...


class UserRepository(Protocol):
    async def get(self, telegram_id: int) -> User | None: ...
    async def upsert(self, user: User) -> User: ...
    async def list_expired(self, now: datetime) -> list[User]: ...
    async def list_notifiable(self) -> list[int]: ...
    async def set_notifications(self, telegram_id: int, enabled: bool) -> None: ...

    # ── Счётчики для ежедневного отчёта (агрегаты считает БД, строки наружу не тащим) ──
    # `exclude` — кого не учитывать (админы: они пользуются кинотеатром служебно, и в
    # отчёте их присутствие завышало бы аудиторию; см. `AdminBlindEventRepository`).
    async def count_all(self, exclude: Collection[int] = ()) -> int: ...
    async def count_created_since(self, since: datetime, exclude: Collection[int] = ()) -> int: ...
    async def count_active(self, now: datetime, exclude: Collection[int] = ()) -> int: ...


class UserEventRepository(Protocol):
    """Значимые действия пользователей (`domain/analytics/events.EventKind`).

    Порт отдельный от `UserRepository` (ISP): здесь только запись факта и агрегаты,
    ничего про профиль и доступ.
    """

    async def add(self, user_id: int, kind: EventKind, meta: str | None = None) -> None:
        """Записать событие. **Fail-open**: сбой записи не должен ронять основной сценарий.

        Аналитика — побочная запись: не выданное видео или не заведённая подписка
        куда хуже, чем дырка в статистике. Деградация — в адаптере (тот же принцип,
        что у Redis-адаптеров), поэтому вызывающему не нужен try/except.
        """
        ...

    async def count(self, kind: EventKind, since: datetime, until: datetime) -> int: ...

    async def count_unique_users(self, kind: EventKind, since: datetime, until: datetime) -> int:
        """Сколько РАЗНЫХ людей сделали это за период (открытия кинотеатра «по головам»)."""
        ...


class PaymentRepository(Protocol):
    async def add(self, request: PaymentRequest) -> PaymentRequest: ...
    async def get(self, request_id: int) -> PaymentRequest | None: ...
    async def set_status(
        self, request_id: int, status: PaymentStatus, reviewed_at: datetime
    ) -> PaymentRequest | None: ...


class VideoDeliveryRepository(Protocol):
    """Учёт выданных видео-сообщений — чтобы удалять их по возрасту и при истечении подписки.

    Мелкий отдельный порт (ISP): к User/Movie/Payment отношения не имеет.
    """

    async def add(self, user_id: int, chat_id: int, message_id: int) -> None: ...
    async def list_for_user(self, user_id: int) -> list[VideoDelivery]: ...

    async def list_due(
        self, older_than: datetime, now: datetime, limit: int
    ) -> list[VideoDelivery]:
        """Выдачи старше `older_than`, у которых подошёл срок попытки. Не более `limit`.

        Именно ПАЧКОЙ (limit), а не целиком: таблица растёт с трафиком, тянуть её в память
        одним списком незачем — вызывающий крутит цикл, пока пачки не кончатся.

        `now` фильтрует по `next_attempt_at`: строки, отложенные после сбоя, в выборку не
        попадают, пока их срок не наступит. Это и не даёт циклу зациклиться на сбойной
        пачке, и не даёт ей забить голову очереди, вытеснив свежие выдачи.
        """
        ...

    async def delete_many(self, ids: list[int]) -> None:
        """Удалить строки разобранной пачки по id."""
        ...

    async def reschedule(self, ids: list[int], next_attempt_at: datetime) -> None:
        """Отложить повтор: attempts += 1, next_attempt_at = срок (временный сбой)."""
        ...
