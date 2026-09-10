"""Юнит-тесты BroadcastService на фейках: аудитория, контент, тумблер."""

from __future__ import annotations

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
    def __init__(self, notifiable: list[int]) -> None:
        self._notifiable = notifiable
        self.toggles: list[tuple[int, bool]] = []

    async def list_notifiable(self) -> list[int]:
        return self._notifiable

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
