"""Ссылка-хэндл для админских карточек: кликабельна всегда, разметка не ломается."""

from __future__ import annotations

from app.domain.mention import mention_html


def test_username_becomes_public_link() -> None:
    assert mention_html(42, "beka") == '<a href="https://t.me/beka">@beka</a>'


def test_leading_at_is_not_doubled() -> None:
    """В БД хэндл лежит без «@», но если прилетел с ним — ссылка всё равно верная."""
    assert mention_html(42, "@beka") == '<a href="https://t.me/beka">@beka</a>'


def test_without_username_falls_back_to_id_link() -> None:
    """Без хэндла остаётся id — но тоже ссылкой, чтобы админ писал в один тап."""
    assert mention_html(42, None) == '<a href="tg://user?id=42">id 42</a>'


def test_odd_username_is_escaped() -> None:
    """HTML-разметка не должна ломаться от мусора в хэндле (иначе сообщение не дойдёт)."""
    assert "<b>" not in mention_html(42, "a<b>c")
