"""Публикации в публичный канал: фильм дня (ежедневно) и новинки (по факту заливки).

Единая точка «что и как постится в канал» — по образцу `BroadcastService` для личек.
Триггеры (джоб планировщика, визард `/add`) зовут этот сервис, а не публикатор
напрямую: тексты, кнопка и адрес постера считаются в одном месте.

Зависит только от портов (`ChannelPublisher`, `DailyMovieService`, `PosterStorage`) и
@-имени бота из конфига (для кнопки-диплинка).
"""

from __future__ import annotations

import logging
from datetime import datetime

from app.application.ports.channel import ChannelPost, ChannelPublisher
from app.application.ports.storage import PosterStorage
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
        posters: PosterStorage,
        bot_username: str,
    ) -> None:
        self._publisher = publisher
        self._daily = daily
        self._posters = posters
        self._bot_username = bot_username

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
        """Пост о фильме: постер ФАЙЛОМ С ДИСКА + текст + кнопка-диплинк.

        Именно файлом, а не ссылкой: по URL картинку качает сам Telegram со своих
        серверов, а входящий трафик с его диапазонов к нам режет хостер (тот же повод,
        что у `BOT_FORCE_POLLING`) — постер молча не доезжал, и пост уходил текстом.
        Файла нет на диске → `local_path` вернёт None, пост уйдёт текстом (не ошибка).
        """
        url = self._movie_url(movie)
        return ChannelPost(
            text=text,
            photo_path=self._posters.local_path(movie.poster_url),
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
