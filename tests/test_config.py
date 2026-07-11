from __future__ import annotations

import pytest
from app.config.settings import load_config


def test_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOT_ADMIN_USER_IDS", "1, 2 ,3")
    monkeypatch.setenv("DB_NAME", "testdb")

    config = load_config()

    assert config.bot.admin_user_ids == [1, 2, 3]
    assert config.db.name == "testdb"
    assert "testdb" in config.db.dsn
    assert config.db.dsn.startswith("postgresql+asyncpg://")


def test_public_origin_drives_cors_webapp_and_webhook(monkeypatch: pytest.MonkeyPatch) -> None:
    """Единый PUBLIC_ORIGIN (https) → CORS, URL Mini App и webhook берутся из него."""
    monkeypatch.setenv("PUBLIC_ORIGIN", "https://qazaqcinema.rehubpro.kz")

    config = load_config()

    assert config.api.cors_origins == ["https://qazaqcinema.rehubpro.kz"]
    assert config.bot.webapp_url == "https://qazaqcinema.rehubpro.kz/"
    assert config.bot.webhook_url == "https://qazaqcinema.rehubpro.kz"
    assert config.bot.webhook_full_url == "https://qazaqcinema.rehubpro.kz/tg/webhook"


def test_public_origin_trailing_slash_is_normalized(monkeypatch: pytest.MonkeyPatch) -> None:
    """Хвостовой / в PUBLIC_ORIGIN не ломает вывод webhook_full_url."""
    monkeypatch.setenv("PUBLIC_ORIGIN", "https://cinema.example/")

    config = load_config()

    assert config.bot.webhook_full_url == "https://cinema.example/tg/webhook"


def test_http_origin_means_polling(monkeypatch: pytest.MonkeyPatch) -> None:
    """http-origin (локаль) → бот в polling (webhook_url пуст), CORS на localhost."""
    monkeypatch.setenv("PUBLIC_ORIGIN", "http://localhost")

    config = load_config()

    assert config.bot.webhook_url == ""
    assert config.api.cors_origins == ["http://localhost"]
