"""ORM-модели. Намеренно отделены от доменных сущностей (мапятся в репозиториях).

Статус/способ/категория хранятся как VARCHAR (а не PG-ENUM): добавить новое
значение можно без миграции типа. telegram_id и user_id — BIGINT без автоинкремента
(это Telegram ID, не суррогатный ключ).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.entities.enums import PaymentStatus, UserStatus
from app.infrastructure.db.base import Base


class UserModel(Base):
    __tablename__ = "users"

    telegram_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default=UserStatus.NEW.value)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    selected_tariff: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # Рассылки о новинках (Фаза 12): opt-out, по умолчанию ВКЛ. server_default → backfill
    # существующих строк в True при миграции без отдельного UPDATE.
    notifications_enabled: Mapped[bool] = mapped_column(
        Boolean, server_default=text("true"), nullable=False
    )
    # Когда человек открыл чат с ботом (нажал /start). NULL — чата нет, бот не имеет
    # права написать первым, и «Көру» для него не сработает. server_default НЕ ставим:
    # умолчание тут именно NULL, а старым строкам факт проставляет миграция по журналу.
    bot_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Когда юзер появился. Нужен для «сколько новых за сегодня» в ежедневном отчёте и
    # как база любой когортной аналитики. server_default → старые строки заполняются
    # моментом миграции (точной даты для них взять неоткуда).
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # Подарочный первый фильм. NULL = подарок не потрачен; заполняется атомарно
    # (`claim_free_view`: UPDATE ... WHERE free_view_used_at IS NULL), иначе два
    # параллельных тапа на плохом инете раздали бы два бесплатных фильма.
    free_view_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Какой именно фильм подарен: он остаётся бесплатным и после того, как чистка снесёт
    # видео из чата (~40 ч). FK нет намеренно — удаление фильма из каталога не должно
    # ронять историю подарка, а сравнение идёт по id.
    free_view_movie_id: Mapped[int | None] = mapped_column(nullable=True)


class FavoriteModel(Base):
    """Избранное («Таңдаулы»): личный список фильмов, ничем не связанный с доступом.

    Составной первичный ключ (user_id, movie_id) сам по себе гарантирует «одна звезда на
    фильм» — отдельный уникальный индекс и проверка «уже в избранном?» перед вставкой не
    нужны. `created_at` хранится не для показа, а как база рекомендаций: по нему видно,
    что и когда людям нравилось.

    ON DELETE CASCADE у movie_id: снятый с каталога фильм не должен оставлять висячие
    строки в чужих списках.
    """

    __tablename__ = "favorites"

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.telegram_id"), primary_key=True, autoincrement=False
    )
    movie_id: Mapped[int] = mapped_column(
        ForeignKey("movies.id", ondelete="CASCADE"), primary_key=True, autoincrement=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Индекс под «избранное юзера, свежие сверху» — основной запрос вкладки.
    __table_args__ = (Index("ix_favorites_user_created_at", "user_id", "created_at"),)


class UserEventModel(Base):
    """Значимые действия пользователя (см. `domain/analytics/events.EventKind`).

    Не полный лог поведения, а срез из пяти событий: start / open / play / subscribe /
    expire. По нему считается ежевечерний отчёт и, при желании, любая ретро-аналитика
    (когда человек пришёл, вернулся ли, дошёл ли до оплаты).

    kind — VARCHAR (не PG-ENUM): новый вид события не требует миграции типа.
    meta — свободная привязка «к чему относится» (id фильма у play, slug тарифа у
    subscribe); отдельные колонки под каждый вид завели бы разреженную таблицу.
    """

    __tablename__ = "user_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"), index=True)
    kind: Mapped[str] = mapped_column(String(32))
    meta: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Составной индекс под запросы отчёта: «событий вида X за период» (kind → created_at).
    __table_args__ = (Index("ix_user_events_kind_created_at", "kind", "created_at"),)


class SeriesModel(Base):
    """Сериал — только название; группировка сезонов (см. `SeasonModel`)."""

    __tablename__ = "series"

    id: Mapped[int] = mapped_column(primary_key=True)
    title_kk: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SeasonModel(Base):
    """Сезон — держатель постера/названия/категорий/описания на ВСЕ свои серии
    (решение 2026-08-28): это спрашивается один раз при создании сезона, как у
    обычного фильма. Серии внутри своего названия не имеют — только номер
    (`MovieModel.episode_number`); при сохранении серии эти поля копируются сюда же.
    """

    __tablename__ = "series_seasons"

    id: Mapped[int] = mapped_column(primary_key=True)
    series_id: Mapped[int] = mapped_column(ForeignKey("series.id", ondelete="CASCADE"), index=True)
    season_number: Mapped[int] = mapped_column()
    poster_url: Mapped[str] = mapped_column(Text)
    title_kk: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    categories: Mapped[list[str]] = mapped_column(ARRAY(String(32)))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("uq_season_series_number", "series_id", "season_number", unique=True),)


class MovieModel(Base):
    __tablename__ = "movies"

    # Триграммные GIN-индексы по названиям (для поиска pg_trgm + unaccent) и сам
    # immutable-враппер f_unaccent создаются вручную в миграции (autogenerate их не видит).
    id: Mapped[int] = mapped_column(primary_key=True)
    title_kk: Mapped[str] = mapped_column(String(255))
    title_ru: Mapped[str | None] = mapped_column(String(255), nullable=True)
    title_original: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str] = mapped_column(Text)
    # Мультикатегории: массив slug'ов (film может быть fantasy+disney+…). GIN-индекс для
    # overlap-запросов (`categories && ARRAY[...]`) создаётся вручную в миграции.
    categories: Mapped[list[str]] = mapped_column(ARRAY(String(32)))
    poster_url: Mapped[str] = mapped_column(Text)
    telegram_file_id: Mapped[str] = mapped_column(Text)
    year: Mapped[int | None] = mapped_column(nullable=True)
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Наследие курируемого hero (до 2026-08-19). Читателей больше нет — hero стал
    # фильмом дня и берёт весь каталог по очереди. Колонку не сносим: она с
    # server_default, вставкам не мешает, а миграция ради мёртвого флага — лишний риск.
    is_featured: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false"), nullable=False
    )
    hero_image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Счётчик просмотров (Фаза 13): +1 при успешной выдаче видео; сортировка «Танымал»
    # и каталога «по просмотрам». server_default 0 → backfill без отдельного UPDATE.
    play_count: Mapped[int] = mapped_column(BigInteger, server_default=text("0"), nullable=False)
    # Счётчик избранного — денормализация, как и play_count: сортировка «Танымал» идёт по
    # формуле из обоих счётчиков (`domain/catalog/popularity.py`), и считать её джойном с
    # `favorites` на каждой странице каталога было бы дороже без всякой пользы.
    favorites_count: Mapped[int] = mapped_column(
        BigInteger, server_default=text("0"), nullable=False
    )
    # Сериалы (решение 2026-08-28): NULL у обоих — обычный самостоятельный фильм.
    # Заполнены — строка есть серия конкретного сезона (`SeasonModel`); ON DELETE SET
    # NULL у FK — снос сезона не должен молча утащить за собой сами серии.
    season_id: Mapped[int | None] = mapped_column(
        ForeignKey("series_seasons.id", ondelete="SET NULL"), nullable=True, index=True
    )
    episode_number: Mapped[int | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class VideoDeliveryModel(Base):
    __tablename__ = "video_deliveries"

    # Выданные подписчику видео-сообщения: удаляем их по возрасту (ежечасно, ~40 ч) и при
    # истечении подписки, чтобы оплаченный контент не оставался в чате навсегда. chat_id
    # хранится отдельно от user_id (для лички они равны, но выдача концептуально «в чат»).
    # message_id — BIGINT: id сообщения Telegram, по нему bot.delete_message.
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.telegram_id"), index=True
    )
    chat_id: Mapped[int] = mapped_column(BigInteger)
    message_id: Mapped[int] = mapped_column(BigInteger)
    # index — по нему ходит ежечасная чистка (`list_due`: WHERE created_at < cutoff).
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    # Ретраи удаления. attempts — сколько раз Telegram отвечал ВРЕМЕННЫМ сбоем (сеть/5xx);
    # исчерпали лимит → строку сносим. next_attempt_at — когда пробовать снова; NULL = «сразу».
    # Без next_attempt_at цикл чистки зациклился бы: сбойная строка возвращалась бы тем же
    # запросом внутри одного прогона. Срок в будущем убирает её из выборки → цикл движется.
    attempts: Mapped[int] = mapped_column(server_default=text("0"), nullable=False)
    next_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class PaymentRequestModel(Base):
    __tablename__ = "payment_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.telegram_id"), index=True
    )
    tariff: Mapped[str] = mapped_column(String(20))
    method: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default=PaymentStatus.PENDING.value, index=True)
    proof_file_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    external_charge_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
