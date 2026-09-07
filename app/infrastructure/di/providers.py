"""Composition root (dishka). Здесь — и ТОЛЬКО здесь — домен/сервисы связываются
с конкретной инфраструктурой. Сервисы зависят от портов, а порты привязываются к
адаптерам тут (DIP).

Две области видимости:
  • APP     — синглтоны на всё приложение (config, движок БД, Bot, провайдеры оплаты);
  • REQUEST — на один апдейт/HTTP-запрос (сессия БД, репозитории, сервисы).
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping

from aiogram import Bot
from dishka import AsyncContainer, Provider, Scope, make_async_container, provide
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.application.ports.broadcast import BroadcastQueue
from app.application.ports.catalog_cache import CatalogCache
from app.application.ports.channel import ChannelPublisher
from app.application.ports.content import ContentRepository, PostLogRepository
from app.application.ports.daily_pin import DailyPin
from app.application.ports.images import ImageProcessor
from app.application.ports.lock import Lock
from app.application.ports.payments import PaymentProvider
from app.application.ports.rate_limit import RateLimiter
from app.application.ports.repositories import (
    DailyReportRepository,
    FavoriteRepository,
    MilestoneRepository,
    MovieRepository,
    PaymentRepository,
    SearchQueryRepository,
    SeasonRepository,
    SeriesRepository,
    UserEventRepository,
    UserRepository,
    VideoDeliveryRepository,
)
from app.application.ports.security import InitDataVerifier
from app.application.ports.session import SessionStore
from app.application.ports.storage import PosterStorage
from app.application.ports.telegram import TelegramNotifier
from app.application.services.activity_service import UserActivityService
from app.application.services.analytics_service import AnalyticsService
from app.application.services.auth_service import AuthService
from app.application.services.broadcast_service import BroadcastService
from app.application.services.catalog_service import CatalogService
from app.application.services.channel_service import ChannelService
from app.application.services.content_posting_service import ContentPostingService
from app.application.services.content_seed_service import ContentSeedService
from app.application.services.daily_service import DailyMovieService
from app.application.services.favorite_service import FavoriteService
from app.application.services.ingestion_service import MovieIngestionService
from app.application.services.milestone_service import MilestoneService
from app.application.services.moderation_service import PaymentModerationService
from app.application.services.payment_service import PaymentService
from app.application.services.playback_service import PlaybackService
from app.application.services.seo_service import SeoBuilder
from app.application.services.series_service import SeriesService
from app.application.services.stars_service import StarsPaymentService
from app.application.services.subscription_service import SubscriptionService
from app.application.services.support_service import SupportService
from app.application.services.video_retention_service import VideoRetentionService
from app.config.settings import AppConfig, load_config
from app.domain.channel.content.kinds import ContentKind
from app.domain.channel.content.render import RENDERERS, ContentRenderer
from app.domain.entities.enums import PaymentMethod
from app.infrastructure.analytics.admin_filter import (
    AdminBlindEventRepository,
    AdminBlindSearchRepository,
)
from app.infrastructure.cache.broadcast import RedisBroadcastQueue
from app.infrastructure.cache.catalog import RedisCatalogCache
from app.infrastructure.cache.daily_pin import RedisDailyPin
from app.infrastructure.cache.lock import RedisLock
from app.infrastructure.cache.rate_limiter import RedisRateLimiter
from app.infrastructure.cache.session import RedisSessionStore
from app.infrastructure.db.content_repositories import PgContentRepository, PgPostLogRepository
from app.infrastructure.db.engine import create_engine, create_sessionmaker
from app.infrastructure.db.repositories import (
    PgDailyReportRepository,
    PgFavoriteRepository,
    PgMilestoneRepository,
    PgMovieRepository,
    PgPaymentRepository,
    PgSearchQueryRepository,
    PgSeasonRepository,
    PgSeriesRepository,
    PgUserEventRepository,
    PgUserRepository,
    PgVideoDeliveryRepository,
)
from app.infrastructure.images.pillow import PillowImageProcessor
from app.infrastructure.payments.kaspi import KaspiManualProvider
from app.infrastructure.payments.stars import TelegramStarsProvider
from app.infrastructure.storage.local import LocalPosterStorage
from app.infrastructure.telegram.channel import AiogramChannelPublisher
from app.infrastructure.telegram.init_data import TelegramInitDataVerifier
from app.infrastructure.telegram.notifier import AiogramNotifier


class AppProvider(Provider):
    scope = Scope.APP

    @provide
    def config(self) -> AppConfig:
        return load_config()

    @provide
    def bot(self, config: AppConfig) -> Bot:
        return Bot(config.bot.token.get_secret_value())

    @provide
    def engine(self, config: AppConfig) -> AsyncEngine:
        return create_engine(config.db.dsn)

    @provide
    def sessionmaker(self, engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
        return create_sessionmaker(engine)

    @provide
    async def redis(self, config: AppConfig) -> AsyncIterator[Redis]:
        # APP-scope синглтон-пул к Redis. Фундамент под сессии/кэш/rate-limit/локи
        # (Фаза 11). Закрывается при остановке контейнера (graceful).
        client = Redis.from_url(config.redis.dsn, decode_responses=True)
        try:
            yield client
        finally:
            await client.aclose()

    @provide
    def lock(self, redis: Redis) -> Lock:
        # Стейтлес-обёртка над APP-scope Redis → синглтон (Фаза 11.4, анти-двойной-клик).
        return RedisLock(redis)

    @provide
    def rate_limiter(self, redis: Redis) -> RateLimiter:
        # Тоже стейтлес-обёртка над Redis (Фаза 11.3, защита API от выкачки/спама).
        return RedisRateLimiter(redis)

    @provide
    def session_store(self, redis: Redis) -> SessionStore:
        # Серверные сессии Web App (Фаза 11.1): initData → токен в Redis, TTL 24 ч.
        return RedisSessionStore(redis)

    @provide
    def catalog_cache(self, redis: Redis) -> CatalogCache:
        # Cache-aside каталога (Фаза 11.2/13): namespace catalog:* (home/categories/browse),
        # инвалидация на /add чистит весь namespace.
        return RedisCatalogCache(redis)

    @provide
    def daily_pin(self, redis: Redis) -> DailyPin:
        # Закреп фильма дня админом (`/daily <id>`): ключ с TTL до местной полуночи.
        # Fail-open: Redis лёг → закрепа нет → работает обычная ротация.
        return RedisDailyPin(redis)

    @provide
    def broadcast_queue(self, redis: Redis) -> BroadcastQueue:
        # Надёжная очередь рассылок (Фаза 12): worker забирает пачками, соблюдая лимиты TG.
        return RedisBroadcastQueue(redis)

    @provide
    def seo_builder(self, config: AppConfig) -> SeoBuilder:
        # Стейтлес-сборщик SEO-метаданных публичных страниц (зависит лишь от адреса + @бота).
        return SeoBuilder(config.public_origin, config.bot.username)

    @provide
    def verifier(self, config: AppConfig) -> InitDataVerifier:
        return TelegramInitDataVerifier(config.bot.token)

    @provide
    def notifier(self, bot: Bot, config: AppConfig) -> TelegramNotifier:
        return AiogramNotifier(bot, config.bot.admin_chat_id, config.bot.admin_user_ids)

    @provide
    def channel_publisher(self, bot: Bot, config: AppConfig) -> ChannelPublisher:
        # APP-scope, как и нотификатор: состояния у публикатора нет, только Bot и id.
        # id = 0 → адаптер сам работает как no-op (см. `AiogramChannelPublisher`).
        return AiogramChannelPublisher(
            bot, config.bot.public_channel_id, config.media.root
        )

    @provide
    def content_renderers(self) -> Mapping[ContentKind, ContentRenderer]:
        # Реестр рендереров (Strategy по форме поста) → карта для сервиса публикации.
        # Наполняется саморегистрацией модулей `domain/channel/content/render/*` при
        # импорте пакета; новая форма = новый модуль + декоратор, этот код не меняется.
        return {ContentKind(slug): RENDERERS.get(slug)() for slug in RENDERERS.slugs()}

    @provide
    def poster_storage(self, config: AppConfig) -> PosterStorage:
        return LocalPosterStorage(config.media)

    @provide
    def image_processor(self) -> ImageProcessor:
        return PillowImageProcessor()

    @provide
    def payment_providers(
        self, config: AppConfig, bot: Bot
    ) -> Mapping[PaymentMethod, PaymentProvider]:
        # Новый способ = запись в этой карте, без правок PaymentService (OCP).
        return {
            PaymentMethod.KASPI: KaspiManualProvider(
                config.payments.kaspi_number,
                config.payments.kaspi_name,
                config.payments.kaspi_link,
            ),
            PaymentMethod.STARS: TelegramStarsProvider(bot),
        }


class RequestProvider(Provider):
    scope = Scope.REQUEST

    @provide
    async def session(
        self, maker: async_sessionmaker[AsyncSession]
    ) -> AsyncIterator[AsyncSession]:
        async with maker() as session:
            yield session

    movies = provide(PgMovieRepository, provides=MovieRepository)
    users = provide(PgUserRepository, provides=UserRepository)
    payments = provide(PgPaymentRepository, provides=PaymentRepository)
    # Имя атрибута обязано быть уникальным в пределах класса: одноимённый провайдер ниже
    # (FavoriteService) просто затёр бы этот, и репозиторий из контейнера пропал бы.
    favorite_repo = provide(PgFavoriteRepository, provides=FavoriteRepository)
    deliveries = provide(PgVideoDeliveryRepository, provides=VideoDeliveryRepository)
    series_repo = provide(PgSeriesRepository, provides=SeriesRepository)
    season_repo = provide(PgSeasonRepository, provides=SeasonRepository)
    daily_reports_repo = provide(PgDailyReportRepository, provides=DailyReportRepository)
    milestones_repo = provide(PgMilestoneRepository, provides=MilestoneRepository)
    content_repo = provide(PgContentRepository, provides=ContentRepository)
    post_log_repo = provide(PgPostLogRepository, provides=PostLogRepository)

    @provide
    def events(self, session: AsyncSession, config: AppConfig) -> UserEventRepository:
        # Pg-адаптер в декораторе: события админов в журнал не попадают (служебные заходы
        # не должны выглядеть живой аудиторией). Фильтр — снаружи, чтобы запись отсекалась
        # до БД, а не вычиталась потом при подсчёте.
        return AdminBlindEventRepository(
            PgUserEventRepository(session), config.bot.admin_user_ids
        )

    @provide
    def searches(self, session: AsyncSession, config: AppConfig) -> SearchQueryRepository:
        # Тот же приём, что и с журналом событий: админ ищет то, что ЗАЛИВАЕТ, поэтому
        # его запросы иначе возглавили бы список «искали, но не нашли» — то есть очередь
        # на озвучку заполнилась бы уже готовящимся к заливке.
        return AdminBlindSearchRepository(
            PgSearchQueryRepository(session), config.bot.admin_user_ids
        )

    auth = provide(AuthService)
    # Фильм дня — общий источник правды витрины (hero) и выдачи (PlaybackService):
    # оба обязаны считать «сегодня бесплатен» одинаково, иначе кнопка «Тегін көру»
    # приводила бы к 403.
    daily = provide(DailyMovieService)
    catalog = provide(CatalogService)
    favorites = provide(FavoriteService)  # избранное («Таңдаулы»), без гейта подписки
    ingestion = provide(MovieIngestionService)
    series = provide(SeriesService)  # сериалы/сезоны — справочник для визарда /add и каталога
    playback = provide(PlaybackService)
    retention = provide(VideoRetentionService)  # чистка видео: ежечасный джоб + истечение
    subscription = provide(SubscriptionService)
    payment = provide(PaymentService)
    moderation = provide(PaymentModerationService)
    support = provide(SupportService)  # обращения из Mini App → в личку админам
    stars = provide(StarsPaymentService)
    activity = provide(UserActivityService)  # /start → юзер в БД + событие «пришёл»

    @provide
    def channel(
        self, publisher: ChannelPublisher, daily: DailyMovieService, config: AppConfig
    ) -> ChannelService:
        # webapp_url и username бота — примитивы из конфига (как у BroadcastService):
        # сервис получает строки, а не весь AppConfig.
        return ChannelService(
            publisher, daily, config.bot.webapp_url, config.bot.username
        )
    milestones = provide(MilestoneService)  # лента вех роста — команда /milestone
    content_posting = provide(ContentPostingService)  # контент-план канала: ежечасный джоб
    content_seed = provide(ContentSeedService)  # заливка пула из YAML (tools/seed_content)

    @provide
    def analytics(
        self,
        users: UserRepository,
        events: UserEventRepository,
        movies: MovieRepository,
        reports: DailyReportRepository,
        milestones: MilestoneRepository,
        config: AppConfig,
    ) -> AnalyticsService:
        # admin_ids — примитив из конфига (как webapp_url у рассылок), поэтому явный
        # метод: сервис получает список id, а не весь AppConfig.
        return AnalyticsService(
            users, events, movies, reports, milestones, config.bot.admin_user_ids
        )

    @provide
    def broadcast(
        self, queue: BroadcastQueue, users: UserRepository, config: AppConfig
    ) -> BroadcastService:
        # webapp_url — примитив (как kaspi_number у провайдера), поэтому явный метод,
        # а не auto-wire: сервис получает чистую строку, не весь конфиг.
        return BroadcastService(queue, users, config.bot.webapp_url)


def build_container() -> AsyncContainer:
    return make_async_container(AppProvider(), RequestProvider())
