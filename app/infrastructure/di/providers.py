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
from app.application.ports.images import ImageProcessor
from app.application.ports.lock import Lock
from app.application.ports.payments import PaymentProvider
from app.application.ports.rate_limit import RateLimiter
from app.application.ports.repositories import (
    MovieRepository,
    PaymentRepository,
    UserRepository,
)
from app.application.ports.security import InitDataVerifier
from app.application.ports.session import SessionStore
from app.application.ports.storage import PosterStorage
from app.application.ports.telegram import TelegramNotifier
from app.application.services.auth_service import AuthService
from app.application.services.broadcast_service import BroadcastService
from app.application.services.catalog_service import CatalogService
from app.application.services.ingestion_service import MovieIngestionService
from app.application.services.moderation_service import PaymentModerationService
from app.application.services.payment_service import PaymentService
from app.application.services.playback_service import PlaybackService
from app.application.services.stars_service import StarsPaymentService
from app.application.services.subscription_service import SubscriptionService
from app.config.settings import AppConfig, load_config
from app.domain.entities.enums import PaymentMethod
from app.infrastructure.cache.broadcast import RedisBroadcastQueue
from app.infrastructure.cache.catalog import RedisCatalogCache
from app.infrastructure.cache.lock import RedisLock
from app.infrastructure.cache.rate_limiter import RedisRateLimiter
from app.infrastructure.cache.session import RedisSessionStore
from app.infrastructure.db.engine import create_engine, create_sessionmaker
from app.infrastructure.db.repositories import (
    PgMovieRepository,
    PgPaymentRepository,
    PgUserRepository,
)
from app.infrastructure.images.pillow import PillowImageProcessor
from app.infrastructure.payments.kaspi import KaspiManualProvider
from app.infrastructure.payments.stars import TelegramStarsProvider
from app.infrastructure.storage.local import LocalPosterStorage
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
    def broadcast_queue(self, redis: Redis) -> BroadcastQueue:
        # Надёжная очередь рассылок (Фаза 12): worker забирает пачками, соблюдая лимиты TG.
        return RedisBroadcastQueue(redis)

    @provide
    def verifier(self, config: AppConfig) -> InitDataVerifier:
        return TelegramInitDataVerifier(config.bot.token)

    @provide
    def notifier(self, bot: Bot, config: AppConfig) -> TelegramNotifier:
        return AiogramNotifier(bot, config.bot.admin_chat_id, config.bot.admin_user_ids)

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

    auth = provide(AuthService)
    catalog = provide(CatalogService)
    ingestion = provide(MovieIngestionService)
    playback = provide(PlaybackService)
    subscription = provide(SubscriptionService)
    payment = provide(PaymentService)
    moderation = provide(PaymentModerationService)
    stars = provide(StarsPaymentService)

    @provide
    def broadcast(
        self, queue: BroadcastQueue, users: UserRepository, config: AppConfig
    ) -> BroadcastService:
        # webapp_url — примитив (как kaspi_number у провайдера), поэтому явный метод,
        # а не auto-wire: сервис получает чистую строку, не весь конфиг.
        return BroadcastService(queue, users, config.bot.webapp_url)


def build_container() -> AsyncContainer:
    return make_async_container(AppProvider(), RequestProvider())
