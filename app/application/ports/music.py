"""Порты музыкального раздела: каталог треков, коллекции, плейлисты, файлы и Telegram.

Порты мелкие по концерну (ISP): каталог ≠ личная коллекция ≠ плейлисты. Сервисы зависят
только от них; SQL, aiogram и файловая система живут в `infrastructure/`.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from typing import Protocol

from app.domain.music.chart import ChartEntry
from app.domain.music.playlist import Playlist
from app.domain.music.track import Track


@dataclass(frozen=True, slots=True)
class TrackStats:
    """Живые цифры трека для его страницы: социальное доказательство «это слушают»."""

    listeners: int   # РАЗНЫХ людей, хоть раз отправивших трек себе
    playlists: int   # в скольких плейлистах лежит
    saves: int       # сколько забрали в «Менің музыкам»


class TrackRepository(Protocol):
    async def get(self, track_id: int) -> Track | None:
        """Трек по id; скрытый админом — как отсутствующий."""
        ...

    async def by_unique_id(self, file_unique_id: str) -> Track | None:
        """Тот же файл, присланный повторно (Telegram даёт один `file_unique_id`).

        Скрытые тоже возвращаются: иначе убранный по жалобе трек вернулся бы в каталог
        следующей же пересылкой.
        """
        ...

    async def add(self, track: Track) -> Track:
        """Сохранить новый трек. Дубль по `file_unique_id` → вернуть существующий.

        Уникальность держит схема: два человека, одновременно переславшие один и тот же
        файл, не создадут двух строк.
        """
        ...

    async def find_duplicate(self, key: str, duration_sec: int) -> Track | None:
        """Та же песня другим файлом: тот же ключ и длительность ±`DUPLICATE_SECONDS`."""
        ...

    async def rename(self, track_id: int, title: str, performer: str) -> None:
        """Исправить название; поисковый ключ пересчитывается вместе с ним."""
        ...

    async def list_by_ids(self, track_ids: Sequence[int]) -> list[Track]:
        """Треки в порядке переданных id (скрытые и удалённые пропускаются)."""
        ...

    async def list_recent(self, limit: int, offset: int = 0) -> list[Track]: ...
    async def list_popular(self, limit: int, offset: int = 0) -> list[Track]: ...

    async def search(self, key: str, limit: int, offset: int = 0) -> list[Track]:
        """Поиск по уже сведённому ключу запроса (`search.fold`): все слова в любом
        порядке выше, опечатки — нечётким сравнением ниже."""
        ...

    async def increment_play_count(self, track_id: int) -> None: ...

    async def hide(self, track_id: int) -> bool:
        """Убрать трек из каталога (жалоба, правообладатель). True — был виден."""
        ...

    async def top_tracks(self, since: datetime, until: datetime, limit: int) -> list[Track]:
        """Треки с наибольшим числом РАЗНЫХ слушателей за окно (подборка «хиты недели»)."""
        ...

    async def top_played(self, since: datetime, until: datetime, limit: int) -> list[ChartEntry]:
        """Самые прослушиваемые за окно — по журналу прослушиваний, а не по счётчику."""
        ...

    async def count_added(self, since: datetime, until: datetime) -> int: ...

    async def count_uploaded(self, uploader_id: int) -> int:
        """Сколько видимых треков человек добавил в каталог («Сіз N ән қостыңыз»)."""
        ...

    async def stats(self, track_id: int) -> TrackStats: ...

    async def by_performer(self, performer_key: str, limit: int) -> list[Track]:
        """Треки исполнителя по ключу `fold(исполнитель)`, сначала популярные."""
        ...

    async def co_listened(self, track_id: int, limit: int) -> list[Track]:
        """«Ұқсас әндер»: что чаще всего лежит в тех же плейлистах, что и этот трек.

        Совместное присутствие в плейлистах — самый честный сигнал похожести, который у
        нас есть: жанров и тегов у присланных файлов нет, а люди складывают вместе то,
        что слушают вместе.
        """
        ...

    async def performers(self, limit: int) -> list[tuple[str, int]]:
        """Исполнители каталога и число их треков — для SEO-страниц и sitemap."""
        ...

    async def list_all(self) -> list[Track]:
        """Все видимые треки — только для sitemap (он обязан перечислить каждый URL)."""
        ...


class LibraryRepository(Protocol):
    """«Менің музыкам» — треки, которые слушатель забрал себе из общего каталога.

    `add`/`remove` идемпотентны и возвращают, изменилось ли состояние: по этому признаку
    двигается денормализованный `tracks.saves_count` (участвует в «Танымал»).
    """

    async def add(self, user_id: int, track_id: int, at: datetime) -> bool: ...
    async def remove(self, user_id: int, track_id: int) -> bool: ...
    async def list_for_user(self, user_id: int, limit: int, offset: int = 0) -> list[Track]: ...
    async def list_ids(self, user_id: int) -> list[int]: ...


class PlaylistAddOutcome(StrEnum):
    ADDED = "added"
    DUPLICATE = "duplicate"   # трек уже в плейлисте — не ошибка, повторный тап
    FULL = "full"             # достигнут `MAX_TRACKS_PER_PLAYLIST`


class PlaylistRepository(Protocol):
    async def create(self, playlist: Playlist) -> Playlist: ...
    async def get(self, playlist_id: int) -> Playlist | None: ...
    async def by_share_code(self, share_code: str) -> Playlist | None: ...
    async def list_for_owner(self, owner_id: int) -> list[Playlist]: ...
    async def count_for_owner(self, owner_id: int) -> int: ...
    async def rename(self, playlist_id: int, title: str, at: datetime) -> None: ...
    async def set_public(self, playlist_id: int, is_public: bool, at: datetime) -> None: ...

    async def list_public(self, limit: int) -> list[Playlist]:
        """Открытые всем и непустые: сначала самые сохраняемые."""
        ...

    async def increment_saves(self, playlist_id: int) -> None: ...

    async def public_with_track(self, track_id: int, limit: int) -> list[Playlist]:
        """Открытые всем плейлисты, где есть этот трек («Осы ән бар плейлистер»)."""
        ...
    async def delete(self, playlist_id: int) -> None: ...

    async def add_track(
        self, playlist_id: int, track_id: int, at: datetime, limit: int
    ) -> PlaylistAddOutcome:
        """Добавить трек в конец. Проверка предела и вставка — одной транзакцией."""
        ...

    async def add_tracks(
        self, playlist_id: int, track_ids: Sequence[int], at: datetime, limit: int
    ) -> int:
        """Добавить пачку в конец (копия чужого плейлиста); вернуть сколько вошло."""
        ...

    async def remove_track(self, playlist_id: int, track_id: int, at: datetime) -> bool: ...

    async def reorder(self, playlist_id: int, track_ids: Sequence[int], at: datetime) -> bool:
        """Задать порядок целиком. False — набор id не совпал с плейлистом (устарел экран)."""
        ...

    async def track_ids(self, playlist_id: int) -> list[int]:
        """id треков в порядке плейлиста."""
        ...


@dataclass(frozen=True, slots=True)
class MusicRequest:
    query: str
    votes: int
    requested_at: datetime


class MusicRequestRepository(Protocol):
    """Запросы «этой песни нет» — очередь для тех, у кого она есть."""

    async def vote(self, user_id: int, key: str, query: str, at: datetime) -> int:
        """Поддержать запрос (создать, если его нет). Вернуть число РАЗНЫХ людей."""
        ...

    async def list_open(self, limit: int) -> list[MusicRequest]: ...

    async def fulfil(self, keys: Sequence[str], at: datetime) -> list[int]:
        """Закрыть запросы, совпавшие с добавленным треком; вернуть РАЗНЫХ людей, которые
        их оставляли, — им бот напишет, что песня появилась."""
        ...


class MusicChartLog(Protocol):
    """Журнал еженедельных хит-парадов: одна публикация на неделю (UNIQUE по дате)."""

    async def posted(self, week: date) -> bool: ...
    async def record(self, week: date, message_id: int, at: datetime) -> None: ...


class AudioSender(Protocol):
    """Аудио в личку слушателю — единственный способ слушать, как «Көру» у фильмов.

    Сервер файл не хранит и не стримит: плеер Telegram играет присланные треки в фоне и
    подряд, в том числе с выключенным экраном. Ошибки — как у видео:
    `RecipientUnreachableError` (чат закрыт) и `TelegramTemporarilyUnavailableError`
    (флуд-лимит, сеть).
    """

    async def send_audio(self, chat_id: int, file_id: str, caption: str) -> int: ...

    async def send_audio_album(self, chat_id: int, file_ids: Sequence[str], caption: str) -> int:
        """Пачка до 10 треков одним сообщением-альбомом; вернуть сколько ушло."""
        ...


class RequestNotifier(Protocol):
    """Личное письмо «сіз сұраған ән қосылды» тем, кто оставлял запрос на песню.

    Fail-open: недоставка (чат закрыт, флуд-лимит) не роняет приём трека — адаптер
    возвращает False и пишет в лог.
    """

    async def request_fulfilled(self, user_id: int, track: Track) -> bool: ...


class MusicArchive(Protocol):
    """Приватный канал-хранилище музыки (как архив видео, но отдельный).

    Копия в канале — страховка каталога: файл остаётся у бота, даже если приславший
    удалит свой чат. Канал не настроен → `None`, трек всё равно попадает в каталог.
    """

    async def store(self, file_id: str, caption: str) -> int | None: ...
