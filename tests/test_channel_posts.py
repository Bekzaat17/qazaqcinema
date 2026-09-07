"""Посты публичного канала: текст (домен) + сборка поста (сервис). Без Telegram и БД.

Проверяем не «отправилось ли», а три правила, из-за которых пост вообще работает:
хэштеги должны быть кликабельными (пробел и дефис Telegram считает концом тега),
кнопка обязана быть ССЫЛКОЙ на конкретный фильм (Web App-кнопку канал не принимает),
и фильм дня в канале обязан совпадать с тем, что пустит `PlaybackService`.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.application.ports.channel import ChannelPost
from app.application.services.channel_service import ChannelService
from app.domain.channel.post import (
    CAPTION_LIMIT,
    MAX_HASHTAGS,
    hashtags,
    render_daily_movie,
    render_new_movie,
)
from app.domain.entities.movie import Movie

_NOW = datetime(2026, 9, 7, 5, 0, tzinfo=UTC)


def _movie(**overrides: object) -> Movie:
    base: dict[str, object] = {
        "id": 42,
        "title_kk": "Кунг-фу панда 2",
        "description": "сипаттама",
        "categories": ["disney", "kids", "comedy"],
        "poster_url": "/posters/x.jpg",
        "telegram_file_id": "fid",
        "year": 2011,
        "rating": 7.2,
    }
    return Movie(**(base | overrides))  # type: ignore[arg-type]


class _FakePublisher:
    def __init__(self) -> None:
        self.posts: list[ChannelPost] = []

    async def publish(self, post: ChannelPost) -> int | None:
        self.posts.append(post)
        return len(self.posts)

    async def remove_buttons(self, message_id: int) -> bool:
        return True


class _FakeDaily:
    def __init__(self, movie: Movie | None) -> None:
        self._movie = movie

    async def today(self, now: datetime) -> Movie | None:
        return self._movie


def _service(publisher: _FakePublisher, movie: Movie | None = None) -> ChannelService:
    return ChannelService(
        publisher,
        _FakeDaily(movie),  # type: ignore[arg-type]
        webapp_url="https://qazaqcinema.kz/",
        bot_username="qazaqcinema_bot",
    )


# ── Домен: текст ─────────────────────────────────────────────────────────────


def test_hashtags_are_clickable() -> None:
    """Пробел и дефис — конец тега для Telegram, поэтому слова склеиваем.

    Без этого «Қиял-ғажайып» дал бы кликабельным только «#Қиял», а «Шытырман оқиға» —
    «#Шытырман»: половина тега превращалась бы в обычный текст. Склеиваем в CamelCase,
    а не в один нижний регистр, — иначе границы слов в теге перестают читаться.
    """
    assert hashtags(["fantasy"]) == "#ҚиялҒажайып"
    assert hashtags(["adventure"]) == "#ШытырманОқиға"
    assert hashtags(["short"]) == "#ҚысқаМетр"
    assert hashtags(["disney"]) == "#Мультфильмдер"  # одно слово — как есть


def test_hashtags_are_capped_and_skip_unknown_slugs() -> None:
    """Простыня тегов читается как спам; незнакомый slug — не тег (нет казахской подписи)."""
    many = ["disney", "kids", "comedy", "family", "adventure"]
    assert len(hashtags(many).split()) == MAX_HASHTAGS
    assert hashtags(["disney", "нетакой"]) == "#Мультфильмдер"
    assert hashtags([]) == ""


def test_new_movie_post_names_the_dub_and_the_title() -> None:
    text = render_new_movie(_movie())
    assert "Жаңа фильм" in text
    assert "<b>Кунг-фу панда 2</b> (2011)" in text
    # Дубляж — главное, что нас отличает: он в посте всегда.
    assert "Қазақша дубляж" in text
    assert "⭐️ 7.2" in text
    assert "#Мультфильмдер" in text


def test_rating_is_omitted_when_unknown() -> None:
    """Пустой рейтинг — незаполненное поле визарда, а «⭐️ —» читалось бы как «плохое кино»."""
    text = render_new_movie(_movie(rating=None))
    assert "⭐️" not in text
    assert "Қазақша дубляж" in text


def test_daily_post_promises_free_and_only_today() -> None:
    """Смысл поста — «бесплатно и только сегодня»: это и есть причина открыть приложение."""
    text = render_daily_movie(_movie())
    assert "Күн фильмі" in text
    assert "тегін" in text.lower()
    assert "Тек бүгін" in text


def test_html_in_title_is_escaped() -> None:
    """Название вводит админ: неэкранированный `<` сломал бы HTML-парсинг всего поста."""
    text = render_new_movie(_movie(title_kk="Кино <b>жаңа</b>"))
    # Теги ИЗ НАЗВАНИЯ обезврежены…
    assert "&lt;b&gt;жаңа&lt;/b&gt;" in text
    # …при этом наша собственная разметка (жирное название) осталась живой разметкой.
    assert "<b>Кино &lt;b&gt;жаңа&lt;/b&gt;</b>" in text


def test_long_description_is_clipped_whole_post() -> None:
    """Режем пост ЦЕЛИКОМ: иначе Telegram обрубил бы хвост — то есть хэштеги и подвал."""
    text = render_daily_movie(_movie(description="а" * 2000))
    assert len(text) <= CAPTION_LIMIT


# ── Сервис: сборка поста ─────────────────────────────────────────────────────


async def test_post_button_is_a_deep_link_to_the_movie() -> None:
    """Кнопка ведёт на КАРТОЧКУ фильма, и это обычный url.

    `web_app`-кнопку Telegram принимает только в приватных чатах — в канале пост с ней
    не отправился бы вообще. А `startapp=m_<id>` открывает сразу нужный фильм, тогда
    как ссылка на главную заставила бы искать его руками.
    """
    publisher = _FakePublisher()
    await _service(publisher).publish_new_movie(_movie())

    post = publisher.posts[0]
    assert post.button_url == "https://t.me/qazaqcinema_bot?startapp=m_42"
    assert post.button_text
    assert post.photo_url == "https://qazaqcinema.kz/posters/x.jpg"


async def test_daily_post_takes_the_same_movie_as_playback() -> None:
    """Источник фильма дня — `DailyMovieService`, один на витрину, канал и выдачу.

    Разъедься они — пост обещал бы одно кино, а «тегін көру» вело бы в пэйволл.
    """
    publisher = _FakePublisher()
    movie = _movie(id=7, title_kk="Шрек 4")

    assert await _service(publisher, movie).publish_daily_movie(_NOW) is True
    assert "Шрек 4" in publisher.posts[0].text
    assert publisher.posts[0].button_url == "https://t.me/qazaqcinema_bot?startapp=m_7"


async def test_daily_post_is_skipped_on_empty_catalog() -> None:
    """Пустой каталог — не ошибка: постить нечего, публикации нет."""
    publisher = _FakePublisher()

    assert await _service(publisher, None).publish_daily_movie(_NOW) is False
    assert publisher.posts == []


async def test_post_without_bot_username_has_no_button() -> None:
    """Кнопку без адреса Telegram не примет — лучше пост без кнопки, чем отказ отправки."""
    publisher = _FakePublisher()
    service = ChannelService(
        publisher,  # type: ignore[arg-type]
        _FakeDaily(None),  # type: ignore[arg-type]
        webapp_url="https://qazaqcinema.kz/",
        bot_username="",
    )

    await service.publish_new_movie(_movie())

    post = publisher.posts[0]
    assert post.button_url is None
    assert post.button_text is None
