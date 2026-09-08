"""ORM-модели. Намеренно отделены от доменных сущностей (мапятся в репозиториях).

Статус/способ/категория хранятся как VARCHAR (а не PG-ENUM): добавить новое
значение можно без миграции типа. telegram_id и user_id — BIGINT без автоинкремента
(это Telegram ID, не суррогатный ключ).
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
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
    # Рассылки о новинках: opt-out, по умолчанию ВКЛ. server_default → backfill
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
    # Telegram Premium (`is_premium` в initData). Единственный признак платёжеспособности,
    # который платформа отдаёт бесплатно: человек, уже платящий Telegram, — совсем другая
    # аудитория для пэйволла, чем тот, кто не платил никогда. Копим, чтобы видеть, есть ли
    # разница в конверсии; в правах доступа НЕ участвует. server_default false → backfill
    # старых строк без отдельного UPDATE (для них признак просто неизвестен).
    is_premium: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false"), nullable=False
    )


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


class SearchQueryModel(Base):
    """Поисковый запрос в каталоге — спрос, высказанный словами (см. `domain/analytics/search`).

    Отдельная таблица, а не вид `UserEventModel`: у факта два измерения (что спросили
    и сколько нашлось), а `user_events` держит ровно одно свободное поле `meta`.
    Кодировать счётчик найденного в строку, чтобы потом разбирать её при группировке
    растущей многоцелевой таблицы, — цена без выгоды.

    `query` хранится УЖЕ нормализованным (`normalize_query`): таблица существует ради
    частоты запроса, а без сведения регистра и пробелов к одной форме топ рассыпался бы
    на варианты написания одного и того же спроса. Сырой ввод не храним — он нужен был
    бы только для чтения глазами, а читать мы будем как раз сводку.

    `found = 0` — главная строка этой таблицы: человек назвал, за чем пришёл, и ушёл ни
    с чем. Отсортированный по частоте список таких запросов и есть очередь на озвучку.
    """

    __tablename__ = "search_queries"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"))
    query: Mapped[str] = mapped_column(String(64))
    found: Mapped[int] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Один индекс по времени: и дневное окно отчёта, и недельное окно дайджеста ходят
    # именно по нему, а группировка внутри окна идёт хэш-агрегацией по `query` — своего
    # индекса ей не нужно. Отдельный индекс под `found = 0` тоже не заводим: нулевые
    # запросы отбираются уже внутри окна, срезанного этим индексом.
    __table_args__ = (Index("ix_search_queries_created_at", "created_at"),)


class SeriesModel(Base):
    """Сериал — только название; группировка сезонов (см. `SeasonModel`)."""

    __tablename__ = "series"

    id: Mapped[int] = mapped_column(primary_key=True)
    title_kk: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SeasonModel(Base):
    """Сезон — держатель постера/названия/категорий/описания на ВСЕ свои серии
   : это спрашивается один раз при создании сезона, как у
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
    hero_image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Счётчик просмотров: +1 при успешной выдаче видео; сортировка «Танымал»
    # и каталога «по просмотрам». server_default 0 → backfill без отдельного UPDATE.
    play_count: Mapped[int] = mapped_column(BigInteger, server_default=text("0"), nullable=False)
    # Счётчик избранного — денормализация, как и play_count: сортировка «Танымал» идёт по
    # формуле из обоих счётчиков (`domain/catalog/popularity.py`), и считать её джойном с
    # `favorites` на каждой странице каталога было бы дороже без всякой пользы.
    favorites_count: Mapped[int] = mapped_column(
        BigInteger, server_default=text("0"), nullable=False
    )
    # Сериалы: NULL у обоих — обычный самостоятельный фильм.
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


class DailyReportModel(Base):
    """Ежедневный снимок `domain/analytics/report.DailyReport` — один на сутки.

    `day` — сам ключ (не суррогатный id): «снимок за 13.08» и есть естественная
    единица этой таблицы, второй строки на ту же дату быть не может (upsert в
    `PgDailyReportRepository.save`). Числа — как в дата-классе один в один, без
    производных величин (проценты считает `render_report`, не хранится).
    """

    __tablename__ = "daily_reports"

    day: Mapped[date] = mapped_column(Date, primary_key=True)
    users_total: Mapped[int] = mapped_column()
    users_new: Mapped[int] = mapped_column()
    subs_active: Mapped[int] = mapped_column()
    catalog_size: Mapped[int] = mapped_column()
    opens_total: Mapped[int] = mapped_column()
    opens_unique: Mapped[int] = mapped_column()
    starts: Mapped[int] = mapped_column()
    plays: Mapped[int] = mapped_column()
    free_plays: Mapped[int] = mapped_column()
    daily_plays: Mapped[int] = mapped_column()
    paywalls: Mapped[int] = mapped_column()
    subscribes: Mapped[int] = mapped_column()
    expires: Mapped[int] = mapped_column()
    # Когда СТРОКА записана/перезаписана — техническое поле, не путать с `day` (тот —
    # какие сутки описаны; misfire мог дописать их и на следующий день). Обновление на
    # конфликте — явно в `set_` репозитория (upsert идёт через Core, ORM-`onupdate`
    # каллбэк на нём не срабатывает).
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class MilestoneModel(Base):
    """Веха роста — см. `domain/analytics/milestone`. Пишется вручную командой `/milestone`."""

    __tablename__ = "milestones"

    id: Mapped[int] = mapped_column(primary_key=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    label: Mapped[str] = mapped_column(String(255))
    created_by: Mapped[int] = mapped_column(BigInteger)


class ContentItemModel(Base):
    """Пул контента канала (см. `domain/channel/content`, PLAN.md §4).

    `kind`/`topic` — VARCHAR (форма и рубрика — данные, новая = без миграции типа).
    `payload` — JSONB: у форм разные поля (варианты квиза, список терминов), а
    разреженные колонки под каждую были бы хуже; в домен он приходит уже dataclass'ом
    (`content_codec`). `slug` — натуральный ключ сидера: тот же slug в YAML → upsert.
    `last_posted_at`/`post_count` — состояние ротации, сидер их не трогает.
    """

    __tablename__ = "content_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True)
    kind: Mapped[str] = mapped_column(String(32), index=True)
    topic: Mapped[str] = mapped_column(String(32))
    title_kk: Mapped[str] = mapped_column(String(255))
    body_kk: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text, server_default="", nullable=False)
    image_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_credit: Mapped[str] = mapped_column(Text, server_default="", nullable=False)
    payload: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    scheduled_for: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    post_count: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ChannelPostLogModel(Base):
    """Журнал публикаций контента: что, когда и каким сообщением ушло в канал.

    `slot_key` UNIQUE (`2026-09-14:quiz-mon`) — идемпотентность слота на уровне БД:
    рестарт, misfire, вторая реплика дубля в канале не дадут. `channel_message_id` —
    к нему привязываются ответы кнопками и разбор; `group_message_id` — id авто-форварда
    в группе обсуждений, по нему узнаются комментарии (`message_thread_id`).
    """

    __tablename__ = "channel_post_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    slot_key: Mapped[str] = mapped_column(String(64), unique=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("content_items.id"), index=True)
    kind: Mapped[str] = mapped_column(String(32))
    channel_message_id: Mapped[int] = mapped_column(BigInteger, index=True)
    group_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    posted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    quiz_closes_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    result_posted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class QuizAnswerModel(Base):
    """Ответы на квиз: первый ответ каждого человека на каждый пост.

    UNIQUE(post_id, user_id) — «А Б В Г Д» пятью сообщениями не работает: засчитан первый.
    `user_id` БЕЗ FK на `users`: отвечающий из канала/группы мог никогда не жать /start.
    `first_name` — для «алғашқы үшеу» в разборе (username есть не у всех).
    """

    __tablename__ = "quiz_answers"

    id: Mapped[int] = mapped_column(primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("channel_post_log.id"), index=True)
    user_id: Mapped[int] = mapped_column(BigInteger)
    first_name: Mapped[str] = mapped_column(String(128))
    text: Mapped[str] = mapped_column(String(255))
    is_correct: Mapped[bool] = mapped_column(Boolean)
    answered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (UniqueConstraint("post_id", "user_id", name="uq_quiz_answers_post_user"),)
