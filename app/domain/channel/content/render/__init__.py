"""Рендереры форм контента: `ContentItem` → `RenderedPost` (текст сообщений + кнопки).

Strategy по `kind` через `Registry` (`domain/registry.py`): каждый модуль формы
регистрирует свой класс декоратором, `RENDERERS.get(kind)` — фабрика. Discovery —
импорты ниже: без них реестр пуст (см. докстринг `Registry`).
"""

from app.domain.channel.content.render.base import (
    RENDERERS,
    CallbackButton,
    ContentRenderer,
    RenderedPost,
    frame,
)

__all__ = ["RENDERERS", "CallbackButton", "ContentRenderer", "RenderedPost", "frame"]
