"""Конфигурация приложения (pydantic-settings).

Каждая секция — отдельный `BaseSettings` со своим `env_prefix` и `env_file=".env"`.
Важно: вложенные `BaseSettings`, собранные через `default_factory`, НЕ наследуют
`env_file` родителя — поэтому каждая секция объявляет его сама (иначе `.env` не
читается при локальном запуске). Урок перенесён из проекта bekabot.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


def _split_csv_ints(value: object) -> object:
    """'1, 2 ,3' -> [1, 2, 3]. Позволяет задавать список в .env через запятую."""
    if isinstance(value, str):
        return [int(part) for part in value.split(",") if part.strip()]
    return value


def _split_csv_str(value: object) -> object:
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    return value


class BotConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="BOT_", env_file=".env", extra="ignore")

    token: SecretStr = SecretStr("")
    username: str = "qazaqcinema_bot"  # @-имя бота (без «@») для SEO deep-link t.me/<username>
    admin_chat_id: int = 0          # чат модерации (куда падают чеки)
    # NoDecode: не даём pydantic-settings JSON-декодить env-строку — её разберёт валидатор
    admin_user_ids: Annotated[list[int], NoDecode] = Field(default_factory=list)
    archive_channel_id: int = 0     # секретный канал-архив с видео

    # webapp_url и webhook_url НЕ задаются напрямую из env — их выводит
    # AppConfig._derive_from_public_origin из единого PUBLIC_ORIGIN (одна переменная
    # на весь домен). Здесь поля — лишь хранилище результата.
    webapp_url: str = ""            # URL Web App (кнопка 🍿); = PUBLIC_ORIGIN + "/"
    webhook_url: str = ""           # = PUBLIC_ORIGIN при https, иначе "" (polling)
    webhook_path: str = "/tg/webhook"  # путь, куда Telegram POST'ит апдейты (Caddy → bot:port)
    webhook_secret: SecretStr = SecretStr("")  # секрет-токен заголовка (валидирует aiogram)
    webhook_port: int = 8080        # внутренний порт aiohttp-сервера вебхука (наружу — через Caddy)
    # Аварийный тумблер: заставить polling даже при https PUBLIC_ORIGIN. Нужен, когда
    # входящий webhook от Telegram недоступен (хостер/транзит режут диапазоны Telegram —
    # `Connection timed out`), а исходящий getUpdates работает. Web App остаётся на https.
    force_polling: bool = False

    _ids = field_validator("admin_user_ids", mode="before")(_split_csv_ints)

    @property
    def webhook_full_url(self) -> str:
        """Полный URL вебхука (base + path) для `set_webhook`."""
        return self.webhook_url.rstrip("/") + self.webhook_path


class DatabaseConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DB_", env_file=".env", extra="ignore")

    host: str = "localhost"
    port: int = 5432
    user: str = "qazaqcinema"
    password: SecretStr = SecretStr("qazaqcinema")
    name: str = "qazaqcinema"

    @property
    def dsn(self) -> str:
        """Async-DSN для SQLAlchemy/asyncpg."""
        return (
            f"postgresql+asyncpg://{self.user}:{self.password.get_secret_value()}"
            f"@{self.host}:{self.port}/{self.name}"
        )


class RedisConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="REDIS_", env_file=".env", extra="ignore")

    host: str = "localhost"
    port: int = 6379
    db: int = 0

    @property
    def dsn(self) -> str:
        return f"redis://{self.host}:{self.port}/{self.db}"


class PaymentsConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PAY_", env_file=".env", extra="ignore")

    # Kaspi: способ включается заполненностью (пусто → скрыт на пэйволле). Заданы
    # оба → доступны оба; только номер → только перевод по номеру; только ссылка →
    # только оплата по ссылке. Переключение способов = правка env, без кода.
    kaspi_number: str = ""   # перевод по номеру
    kaspi_name: str = ""     # имя получателя (рядом с номером)
    kaspi_link: str = ""     # оплата по ссылке Kaspi Pay (pay.kaspi.kz/pay/...)


class ApiConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="API_", env_file=".env", extra="ignore")

    host: str = "0.0.0.0"
    port: int = 8000
    # Перекрывается AppConfig._derive_from_public_origin → [PUBLIC_ORIGIN]. Дефолт/CSV
    # оставлены как фолбэк, но единственный источник в норме — PUBLIC_ORIGIN.
    cors_origins: Annotated[list[str], NoDecode] = Field(default_factory=lambda: ["*"])

    _origins = field_validator("cors_origins", mode="before")(_split_csv_str)


class MediaConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MEDIA_", env_file=".env", extra="ignore")

    root: str = "uploads"               # каталог на диске (постеры и прочая статика)
    posters_url_base: str = "/posters"  # публичный префикс URL постера (mount StaticFiles)


class AppConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ── Единый публичный адрес (scheme://host[:port]) — ОДИН источник правды ──────
    # Из PUBLIC_ORIGIN выводятся ВСЕ домен-зависимые значения: CORS, URL Mini App,
    # режим бота (webhook/polling). Та же переменная уходит в Caddy как site address
    # (docker-compose) → и авто-TLS оттуда же. Схема ОБЯЗАТЕЛЬНА и служит флагом среды:
    #   прод:     https://qazaqcinema.rehubpro.kz   (https ⟹ TLS + webhook)
    #   локально: http://localhost                  (http  ⟹ без TLS + polling)
    public_origin: str = "http://localhost"

    bot: BotConfig = Field(default_factory=BotConfig)
    db: DatabaseConfig = Field(default_factory=DatabaseConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)
    payments: PaymentsConfig = Field(default_factory=PaymentsConfig)
    api: ApiConfig = Field(default_factory=ApiConfig)
    media: MediaConfig = Field(default_factory=MediaConfig)

    @model_validator(mode="after")
    def _derive_from_public_origin(self) -> AppConfig:
        """Выводит домен-зависимые значения из единого public_origin.

        Домен пишется в env ОДИН раз (PUBLIC_ORIGIN) — CORS, Mini App и режим бота
        больше не рассинхронятся и не дублируются. Отдельные BOT_WEBAPP_URL/
        BOT_WEBHOOK_URL/API_CORS_ORIGINS не нужны (эти поля — лишь хранилище).
        """
        origin = self.public_origin.rstrip("/")
        secure = origin.startswith("https://")
        # CORS: ровно этот origin (scheme важен для матчинга; не "*").
        self.api.cors_origins = [origin]
        # Mini App: тот же origin. Кнопка в Telegram появится только при https.
        self.bot.webapp_url = origin + "/"
        # Бот: Telegram требует HTTPS для webhook → https ⟹ webhook, http ⟹ polling.
        # force_polling перебивает: webhook_url="" → main.py уходит в polling (обход
        # блокировки входящего webhook), при этом webapp_url/CORS остаются на https.
        self.bot.webhook_url = origin if (secure and not self.bot.force_polling) else ""
        return self


def load_config() -> AppConfig:
    """Единая точка загрузки конфигурации."""
    return AppConfig()
