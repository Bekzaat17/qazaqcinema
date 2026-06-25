from __future__ import annotations

import pytest
from app.domain.parsing.caption_parser import CaptionParseError, parse_caption

CAPTION = """#title Арыстан Патша / Король Лев
#category disney
#year 1994
#rating 8.5
#poster [https://link/lion.jpg](https://link/lion.jpg)
#desc Симба есімді арыстанның тақ үшін күресі туралы аңыз."""


def test_parse_full_caption() -> None:
    movie = parse_caption(CAPTION)
    assert movie.title == "Арыстан Патша / Король Лев"
    assert movie.category == "disney"
    assert movie.year == 1994
    assert movie.rating == 8.5
    assert movie.poster_url == "https://link/lion.jpg"  # markdown-ссылка очищена
    assert "Симба" in movie.description


def test_order_independent_and_plain_url() -> None:
    movie = parse_caption("#desc описание #poster https://x/y.jpg #category anime #title Тест")
    assert movie.title == "Тест"
    assert movie.category == "anime"
    assert movie.poster_url == "https://x/y.jpg"
    assert movie.year is None


def test_missing_required_raises() -> None:
    with pytest.raises(CaptionParseError):
        parse_caption("#title Только название")


def test_empty_caption_raises() -> None:
    with pytest.raises(CaptionParseError):
        parse_caption("")


def test_no_keys_raises() -> None:
    with pytest.raises(CaptionParseError):
        parse_caption("обычный текст без ключей")
