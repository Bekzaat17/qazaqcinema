"""Конфигурация приложения (pydantic-settings).

Каждая секция — отдельный `BaseSettings` со своим `env_prefix` и `env_file=".env"`.
Важно: вложенные `BaseSettings`, собранные через `default_factory`, НЕ наследуют
`env_file` родителя — поэтому каждая секция объявляет его сама (иначе `.env` не
читается при локальном запуске). Урок перенесён из проекта bekabot.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import Field, SecretStr, field_validator
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
    admin_chat_id: int = 0          # чат модерации (куда падают чеки)
    # NoDecode: не даём pydantic-settings JSON-декодить env-строку — её разберёт валидатор
    admin_user_ids: Annotated[list[int], NoDecode] = Field(default_factory=list)
    archive_channel_id: int = 0     # секретный канал-архив с видео
    webapp_url: str = ""            # URL Web App (кнопка 🍿)

    # Вебхук (прод). Пусто → polling (локально/дев). Заполнено → бот слушает webhook.
    webhook_url: str = ""           # публичный HTTPS base, напр. https://cinema.example (без пути)
    webhook_path: str = "/tg/webhook"  # путь, куда Telegram POST'ит апдейты (Nginx → bot:port)
    webhook_secret: SecretStr = SecretStr("")  # секрет-токен заголовка (валидирует aiogram)
    webhook_port: int = 8080        # внутренний порт aiohttp-сервера вебхука (наружу — через Nginx)

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

    kaspi_number: str = ""
    kaspi_name: str = ""
    # ссылка Kaspi Pay (pay.kaspi.kz/pay/...) — если задана, фронт ведёт по ней
    kaspi_link: str = ""


class ApiConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="API_", env_file=".env", extra="ignore")

    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: Annotated[list[str], NoDecode] = Field(default_factory=lambda: ["*"])

    _origins = field_validator("cors_origins", mode="before")(_split_csv_str)


class MediaConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MEDIA_", env_file=".env", extra="ignore")

    root: str = "uploads"               # каталог на диске (постеры и прочая статика)
    posters_url_base: str = "/posters"  # публичный префикс URL постера (mount StaticFiles)


class AppConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    bot: BotConfig = Field(default_factory=BotConfig)
    db: DatabaseConfig = Field(default_factory=DatabaseConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)
    payments: PaymentsConfig = Field(default_factory=PaymentsConfig)
    api: ApiConfig = Field(default_factory=ApiConfig)
    media: MediaConfig = Field(default_factory=MediaConfig)


def load_config() -> AppConfig:
    """Единая точка загрузки конфигурации."""
    return AppConfig()
