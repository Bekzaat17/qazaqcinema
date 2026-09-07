"""Публикации в публичный канал: фильм дня (ежедневно) и новинки (по факту заливки).

Единая точка «что и как постится в канал» — по образцу `BroadcastService` для личек.
Триггеры (джоб планировщика, визард `/add`) зовут этот сервис, а не публикатор
напрямую: тексты, кнопка и адрес постера считаются в одном месте.

Зависит только от портов (`ChannelPublisher`, `DailyMovieService`) + двух примитивов из
конфига — origin для постера и @-имя бота для кнопки.
"""

from __future__ import annotations

import logging
from datetime import datetime
from urllib.parse import urljoin

from app.application.ports.channel import ChannelPost, ChannelPublisher
from app.application.services.daily_service import DailyMovieService
from app.domain.channel.post import render_daily_movie, render_new_movie
from app.domain.entities.movie import Movie

logger = logging.getLogger(__name__)

_DAILY_BUTTON = "🍿 Тегін көру"
_NEW_MOVIE_BUTTON = "🍿 Көру"


class ChannelService:
    def __init__(
        self,
        publisher: ChannelPublisher,
        daily: DailyMovieService,
        webapp_url: str,
        bot_username: str,
    ) -> None:
        self._publisher = publisher
        self._daily = daily
        self._webapp_url = webapp_url
        self._bot_username = bot_username

    def _poster_url(self, poster_url: str) -> str | None:
        """Абсолютный адрес постера (Telegram качает его сам).

        Локально (`http://localhost`) Telegram до нашей машины не достанет, но URL всё
        равно строим: адаптер поймает `TelegramBadRequest` и опубликует текстом. Своего
        условия «а виден ли мы снаружи» здесь не держим — оно было бы догадкой о сети.
        """
        if not self._webapp_url.startswith("http"):
            return None
        return urljoin(self._webapp_url, poster_url)

    def _movie_url(self, movie: Movie) -> str | None:
        """Deep-link на карточку фильма в Mini App: `t.me/<bot>?startapp=m_<id>`.

        Именно ссылка, а не `web_app`-кнопка: в канале Telegram принимает только `url`
        (см. `ports/channel`). Тот же формат уже отдаёт SEO-страница (`SeoBuilder`), и
        фронт умеет его читать (`getStartMovieId`) — человек попадает сразу на фильм,
        а не на главную, где его ещё надо искать.
        """
        if not self._bot_username or movie.id is None:
            return None
        return f"https://t.me/{self._bot_username}?startapp=m_{movie.id}"

    def _post(self, movie: Movie, text: str, button_text: str) -> ChannelPost:
        url = self._movie_url(movie)
        return ChannelPost(
            text=text,
            photo_url=self._poster_url(movie.poster_url),
            button_text=button_text if url else None,
            button_url=url,
        )

    async def publish_new_movie(self, movie: Movie) -> bool:
        """Пост о новинке. Зовёт `MovieIngestionService` после сохранения фильма."""
        sent = await self._publisher.publish(
            self._post(movie, render_new_movie(movie), _NEW_MOVIE_BUTTON)
        )
        return sent is not None

    async def publish_daily_movie(self, now: datetime) -> bool:
        """Пост про сегодняшний бесплатный фильм. Зовёт джоб планировщика раз в сутки.

        Фильм берём у `DailyMovieService` — того же источника правды, что рисует hero
        главной и пускает `PlaybackService`. Иначе канал пообещал бы одно кино, а
        приложение открыло другое, и «тегін көру» из поста вело бы в пэйволл.

        Пустой каталог → постить нечего (не ошибка): `False` и тишина.
        """
        movie = await self._daily.today(now)
        if movie is None:
            logger.info("Фильм дня не выбран (каталог пуст) — пост в канал не публикуем")
            return False
        sent = await self._publisher.publish(
            self._post(movie, render_daily_movie(movie), _DAILY_BUTTON)
        )
        return sent is not None
