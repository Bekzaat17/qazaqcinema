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
