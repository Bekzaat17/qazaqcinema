from __future__ import annotations

import pytest
from app.config.settings import load_config


def test_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOT_WEBAPP_URL", "https://app.example.com")
    monkeypatch.setenv("BOT_ADMIN_USER_IDS", "1, 2 ,3")
    monkeypatch.setenv("DB_NAME", "testdb")

    config = load_config()

    assert config.bot.webapp_url == "https://app.example.com"
    assert config.bot.admin_user_ids == [1, 2, 3]
    assert config.db.name == "testdb"
    assert "testdb" in config.db.dsn
    assert config.db.dsn.startswith("postgresql+asyncpg://")


def test_webhook_defaults_to_polling() -> None:
    """Без BOT_WEBHOOK_URL бот работает в polling (webhook_url пуст) — локаль не трогаем."""
    config = load_config()
    assert config.bot.webhook_url == ""


def test_webhook_full_url_joins_base_and_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOT_WEBHOOK_URL", "https://cinema.example/")  # хвостовой / срезаем
    monkeypatch.setenv("BOT_WEBHOOK_PATH", "/tg/webhook")

    config = load_config()

    assert config.bot.webhook_full_url == "https://cinema.example/tg/webhook"
