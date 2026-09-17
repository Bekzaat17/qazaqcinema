"""Юнит-тесты BroadcastService на фейках: аудитория, контент, тумблер."""

from __future__ import annotations

from datetime import UTC, date, datetime

from app.application.ports.broadcast import BroadcastMessage
from app.application.services.broadcast_service import BroadcastService
from app.domain.entities.movie import Movie


class _FakeQueue:
    def __init__(self) -> None:
        self.calls: list[tuple[BroadcastMessage, list[int]]] = []

    async def enqueue(self, message: BroadcastMessage, recipient_ids: list[int]) -> int:
        self.calls.append((message, recipient_ids))
        return len(recipient_ids)


class _FakePosters:
    """Хранилище постеров: `/posters/x.jpg` → `posters/x.jpg`; `missing` — файла нет."""

    async def save(self, data: bytes, *, thumb: bytes) -> str:
        return "/posters/new.jpg"

    def local_path(self, poster_url: str) -> str | None:
        name = poster_url.rsplit("/", 1)[-1]
        return None if name == "missing.jpg" else f"posters/{name}"


class _FakeUsers:
    def __init__(
        self,
        notifiable: list[int],
        pickers: list[int] | None = None,
        idle: list[int] | None = None,
    ) -> None:
        self._notifiable = notifiable
        self._pickers = pickers or []
        self._idle = idle or []
        self.toggles: list[tuple[int, bool]] = []
        self.asked_weeks: list[date] = []

    async def list_notifiable(self) -> list[int]:
        return self._notifiable

    async def list_weekly_pickers(self, week: date, now: datetime) -> list[int]:
        self.asked_weeks.append(week)
        return self._pickers

    async def list_weekly_idle(self, week: date, now: datetime) -> list[int]:
        self.asked_weeks.append(week)
        return self._idle

    async def set_notifications(self, telegram_id: int, enabled: bool) -> None:
        self.toggles.append((telegram_id, enabled))


def _movie(poster_url: str = "/posters/x.jpg") -> Movie:
    return Movie(
        title_kk="Аладдин",
        description="Ертегі " * 400,  # длинное описание → проверим подрезку подписи
        categories=["disney"],
        poster_url=poster_url,
        telegram_file_id="fid",
        year=1992,
    )


async def test_notify_new_movie_targets_only_notifiable() -> None:
    queue = _FakeQueue()
    service = BroadcastService(
        queue, _FakeUsers([10, 20, 30]), _FakePosters(), "https://cinema.example/"
    )

    assert await service.notify_new_movie(_movie()) == 3

    message, recipients = queue.calls[0]
    assert recipients == [10, 20, 30]
    assert "Аладдин" in message.text
    assert len(message.text) <= 900  # подпись подрезана под лимит Telegram
    assert message.photo_path == "posters/x.jpg"            # постер файлом с диска
    assert message.button_url == "https://cinema.example/"  # кнопка «Көру»


async def test_notify_new_movie_without_webapp_url_still_carries_the_poster() -> None:
    """Нет origin Web App → нет кнопки, но постер уходит: он берётся с диска, не по URL."""
    queue = _FakeQueue()
    service = BroadcastService(queue, _FakeUsers([1]), _FakePosters(), "")

    await service.notify_new_movie(_movie())

    message, _ = queue.calls[0]
    assert message.photo_path == "posters/x.jpg"
    assert message.button_url is None


async def test_notify_new_movie_without_the_poster_file_still_goes_out() -> None:
    """Файла на диске нет → письмо уходит текстом, а не отменяется."""
    queue = _FakeQueue()
    service = BroadcastService(queue, _FakeUsers([1]), _FakePosters(), "https://c.example/")

    await service.notify_new_movie(_movie(poster_url="/posters/missing.jpg"))

    message, _ = queue.calls[0]
    assert message.photo_path is None
    assert message.text


async def test_broadcast_custom_sends_text_to_audience() -> None:
    queue = _FakeQueue()
    service = BroadcastService(queue, _FakeUsers([1, 2]), _FakePosters(), "https://c.example/")

    assert await service.broadcast_custom("Сәлем, жаңалық бар!") == 2

    message, recipients = queue.calls[0]
    assert recipients == [1, 2]
    assert message.text == "Сәлем, жаңалық бар!"


async def test_set_user_notifications_toggles_flag() -> None:
    users = _FakeUsers([])
    service = BroadcastService(_FakeQueue(), users, _FakePosters(), "https://c.example/")

    await service.set_user_notifications(42, enabled=False)

    assert users.toggles == [(42, False)]


# --- недельный выбор: два письма в неделю, и ни одним больше --------------------------

_MONDAY = datetime(2026, 9, 28, 6, 0, tzinfo=UTC)  # понедельник 11:00 по Алматы
_SATURDAY = datetime(2026, 10, 3, 6, 0, tzinfo=UTC)


def _service(users: _FakeUsers, queue: _FakeQueue) -> BroadcastService:
    return BroadcastService(queue, users, _FakePosters(), "https://qazaqcinema.kz/")  # type: ignore[arg-type]


async def test_monday_letter_goes_to_last_weeks_pickers_only() -> None:
    """Аудитория узкая намеренно: человек уже выбирал — значит механика ему нужна.

    Спросить надо именно про ПРОШЛУЮ неделю: на текущей ещё никто ничего не взял, и
    запрос по ней вернул бы пустоту каждый понедельник.
    """
    users, queue = _FakeUsers([1, 2, 3], pickers=[7, 9]), _FakeQueue()

    sent = await _service(users, queue).notify_weekly_pick_open(_MONDAY)

    assert sent == 2
    assert users.asked_weeks == [date(2026, 9, 21)]  # прошлый понедельник
    message, audience = queue.calls[0]
    assert audience == [7, 9]
    assert "Жаңа апта" in message.text
    assert message.button_url == "https://qazaqcinema.kz/"


async def test_saturday_letter_goes_to_those_who_have_not_picked_this_week() -> None:
    """Это же лечит слабость общего окна: взявший в воскресенье получает вечер, не неделю."""
    users, queue = _FakeUsers([1], idle=[5]), _FakeQueue()

    sent = await _service(users, queue).notify_weekly_pick_closing(_SATURDAY)

    assert sent == 1
    assert users.asked_weeks == [date(2026, 9, 28)]  # ключ ТЕКУЩЕЙ недели
    message, audience = queue.calls[0]
    assert audience == [5]
    # «Жексенбіде», а не «ертең»: письмо читают вечером субботы, и «завтра» превращается
    # в «уже сегодня».
    assert "жексенбіде" in message.text


async def test_no_audience_means_no_queue_call() -> None:
    """Пустая рассылка не должна доходить до очереди: worker разбирал бы пустоту."""
    users, queue = _FakeUsers([1, 2]), _FakeQueue()
    service = _service(users, queue)

    assert await service.notify_weekly_pick_open(_MONDAY) == 0
    assert await service.notify_weekly_pick_closing(_SATURDAY) == 0
    assert queue.calls == []
