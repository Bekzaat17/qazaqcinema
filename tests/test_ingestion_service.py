"""Юнит-тест MovieIngestionService на фейковых портах (без БД и aiogram)."""

from __future__ import annotations

from app.application.ports.images import POSTER, ImageSpec
from app.application.services.ingestion_service import MovieIngestionService
from app.domain.entities.movie import Movie
from app.domain.entities.season import Season


class _FakeMovies:
    def __init__(self) -> None:
        self.added: list[Movie] = []

    async def add(self, movie: Movie) -> Movie:
        movie.id = len(self.added) + 1
        self.added.append(movie)
        return movie

    async def list_by_season(self, season_id: int) -> list[Movie]:
        return [m for m in self.added if m.season_id == season_id]


class _FakeSeasons:
    def __init__(self, seasons: list[Season] | None = None) -> None:
        self._seasons = {s.id: s for s in (seasons or [])}

    async def get(self, season_id: int) -> Season | None:
        return self._seasons.get(season_id)


class _FakePosters:
    def __init__(self) -> None:
        self.saved: list[bytes] = []

    async def save(self, data: bytes) -> str:
        self.saved.append(data)
        return f"/posters/fake{len(self.saved)}.jpg"


class _FakeImages:
    def __init__(self) -> None:
        self.calls: list[tuple[bytes, ImageSpec]] = []

    async def normalize(self, data: bytes, spec: ImageSpec) -> bytes:
        self.calls.append((data, spec))
        return data  # в тесте пиксели не трогаем — важен факт вызова и spec


class _FakeNotifier:
    def __init__(self) -> None:
        self.messages: list[str] = []

    async def notify_admins(self, text: str) -> None:
        self.messages.append(text)


class _FakeCache:
    def __init__(self) -> None:
        self.invalidated = 0

    async def get(self, key: str) -> str | None:
        return None

    async def set(self, key: str, payload: str, ttl: int) -> None:
        pass

    async def invalidate(self) -> None:
        self.invalidated += 1


class _FakeBroadcast:
    def __init__(self) -> None:
        self.notified: list[Movie] = []

    async def notify_new_movie(self, movie: Movie) -> int:
        self.notified.append(movie)
        return 0


async def test_ingest_saves_poster_persists_and_notifies() -> None:
    movies = _FakeMovies()
    posters = _FakePosters()
    images = _FakeImages()
    notifier = _FakeNotifier()
    cache = _FakeCache()
    broadcast = _FakeBroadcast()
    service = MovieIngestionService(
        movies, _FakeSeasons(), notifier, posters, images, cache, broadcast
    )

    movie = await service.ingest(
        title_kk="Арыстан Патша",
        title_ru="Король Лев",
        title_original="The Lion King",
        categories=["disney"],
        description="сипаттама",
        year=1994,
        rating=8.5,
        notify=True,
        video_file_id="archive-file-id",
        poster_bytes=b"image-bytes",
    )

    assert movie.id == 1
    assert movie.telegram_file_id == "archive-file-id"
    assert movie.hero_image_url is None                # без баннера hero пуст
    assert posters.saved == [b"image-bytes"]           # только постер
    assert images.calls == [(b"image-bytes", POSTER)]  # нормализован к 2:3
    assert movies.added[0].title_ru == "Король Лев"
    assert any("Арыстан Патша" in message for message in notifier.messages)
    assert cache.invalidated == 1                       # кэш главной сброшен → новинка видна
    assert broadcast.notified == [movie]                # админ выбрал «хабарла» → рассылка


async def test_ingest_stores_exactly_one_image() -> None:
    """У фильма ровно одна картинка — постер (решение 2026-08-19).

    Широкий баннер больше не запрашивается: hero главной делает широкую поверхность из
    этого же постера, а вторая картинка к каждому из сотен фильмов — работа, которая
    ничего не добавляла.
    """
    movies, posters, images = _FakeMovies(), _FakePosters(), _FakeImages()
    service = MovieIngestionService(
        movies, _FakeSeasons(), _FakeNotifier(), posters, images, _FakeCache(), _FakeBroadcast()
    )

    movie = await service.ingest(
        title_kk="Наруто",
        title_ru=None,
        title_original="Naruto",
        categories=["anime"],
        description="сипаттама",
        year=2002,
        rating=8.3,
        notify=True,
        video_file_id="vid",
        poster_bytes=b"poster",
    )

    assert movie.hero_image_url is None            # баннера нет и взяться неоткуда
    assert posters.saved == [b"poster"]            # в хранилище ушёл один файл
    assert images.calls == [(b"poster", POSTER)]   # и нормализован он один раз


async def test_ingest_without_notify_keeps_the_queue_silent() -> None:
    """Админ выбрал «🔕 Жоқ» → фильм сохраняется, но рассылка НЕ ставится.

    Ради этого шаг и заведён: каталог заливают пачками, и безусловная рассылка давала
    десятки пушей за вечер каждому подписчику — прямой путь в блокировку бота.
    """
    movies, broadcast, cache = _FakeMovies(), _FakeBroadcast(), _FakeCache()
    service = MovieIngestionService(
        movies, _FakeSeasons(), _FakeNotifier(), _FakePosters(), _FakeImages(), cache, broadcast
    )

    movie = await service.ingest(
        title_kk="Тыныш фильм",
        title_ru=None,
        title_original=None,
        categories=["anime"],
        description="сипаттама",
        year=None,
        rating=None,
        notify=False,
        video_file_id="vid",
        poster_bytes=b"poster",
    )

    assert movie.id == 1              # фильм в каталоге
    assert cache.invalidated == 1     # и виден сразу (кэш сброшен)
    assert broadcast.notified == []   # но никого не разбудили


async def test_ingest_episode_of_existing_season_reuses_its_fields() -> None:
    """Серия УЖЕ СУЩЕСТВУЮЩЕГО сезона (решение 2026-08-28): постер/категории/описание
    берутся с сезона (визард их не спрашивал), номер серии — следующий по счёту, название
    авто-генерируется «<сезон> — N-бөлім»; постер повторно не нормализуется/не сохраняется.
    """
    season = Season(
        id=9,
        series_id=1,
        season_number=2,
        poster_url="/posters/season2.jpg",
        title_kk="Көліктер",
        description="Мультсериал туралы сипаттама",
        categories=["disney", "adventure"],
    )
    movies, posters, images = _FakeMovies(), _FakePosters(), _FakeImages()
    seasons = _FakeSeasons([season])
    service = MovieIngestionService(
        movies, seasons, _FakeNotifier(), posters, images, _FakeCache(), _FakeBroadcast()
    )

    first = await service.ingest(
        year=None, rating=None, notify=False, video_file_id="ep1", season_id=9
    )
    second = await service.ingest(
        year=None, rating=None, notify=False, video_file_id="ep2", season_id=9
    )

    assert first.title_kk == "Көліктер — 1-бөлім"
    assert second.title_kk == "Көліктер — 2-бөлім"   # счёт продолжается по существующим сериям
    assert first.episode_number == 1
    assert second.episode_number == 2
    assert first.categories == ["disney", "adventure"]
    assert first.description == "Мультсериал туралы сипаттама"
    assert first.poster_url == "/posters/season2.jpg"
    assert posters.saved == []       # постер сезона уже сохранён — повторно не грузим
    assert images.calls == []        # и не нормализуем заново
