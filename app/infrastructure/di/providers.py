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
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.application.ports.payments import PaymentProvider
from app.application.ports.repositories import (
    MovieRepository,
    PaymentRepository,
    UserRepository,
)
from app.application.ports.security import InitDataVerifier
from app.application.ports.storage import PosterStorage
from app.application.ports.telegram import TelegramNotifier
from app.application.services.auth_service import AuthService
from app.application.services.catalog_service import CatalogService
from app.application.services.ingestion_service import MovieIngestionService
from app.application.services.moderation_service import PaymentModerationService
from app.application.services.payment_service import PaymentService
from app.application.services.playback_service import PlaybackService
from app.application.services.subscription_service import SubscriptionService
from app.config.settings import AppConfig, load_config
from app.domain.entities.enums import PaymentMethod
from app.infrastructure.db.engine import create_engine, create_sessionmaker
from app.infrastructure.db.repositories import (
    PgMovieRepository,
    PgPaymentRepository,
    PgUserRepository,
)
from app.infrastructure.payments.kaspi import KaspiManualProvider
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
    def verifier(self, config: AppConfig) -> InitDataVerifier:
        return TelegramInitDataVerifier(config.bot.token)

    @provide
    def notifier(self, bot: Bot, config: AppConfig) -> TelegramNotifier:
        return AiogramNotifier(bot, config.bot.admin_chat_id, config.bot.admin_user_ids)

    @provide
    def poster_storage(self, config: AppConfig) -> PosterStorage:
        return LocalPosterStorage(config.media)

    @provide
    def payment_providers(self, config: AppConfig) -> Mapping[PaymentMethod, PaymentProvider]:
        # Stars-провайдер добавится тут на Фазе 8 (PLAN), без правок сервисов.
        return {
            PaymentMethod.KASPI: KaspiManualProvider(
                config.payments.kaspi_number, config.payments.kaspi_name
            ),
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


def build_container() -> AsyncContainer:
    return make_async_container(AppProvider(), RequestProvider())
