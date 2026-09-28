"""Метка источника в deep-link: разбор payload и совместимость со старыми ссылками."""

from __future__ import annotations

import pytest
from app.domain.analytics.source import (
    CHANNEL,
    SEO,
    UNTAGGED,
    link_movie_id,
    link_source,
    movie_link_payload,
)


def test_payload_round_trips_source_and_movie() -> None:
    payload = movie_link_payload(SEO, 42)

    assert payload == "seo-m_42"
    assert (link_source(payload), link_movie_id(payload)) == (SEO, 42)


@pytest.mark.parametrize(
    ("payload", "source", "movie_id"),
    [
        ("ch-m_7", CHANNEL, 7),
        ("seo", SEO, None),  # подвал сайта: источник без фильма
        ("web", "web", None),
        # Ссылки, разосланные до меток, обязаны открывать фильм и дальше.
        ("m_42", UNTAGGED, 42),
        ("m42", UNTAGGED, 42),
        ("мусор", UNTAGGED, None),
    ],
)
def test_parses_known_payloads(payload: str, source: str, movie_id: int | None) -> None:
    assert link_source(payload) == source
    assert link_movie_id(payload) == movie_id


def test_no_payload_means_no_source() -> None:
    """Заход из чата бота — возврат, а не приход: источника нет."""
    assert link_source(None) is None
    assert link_source("") is None
