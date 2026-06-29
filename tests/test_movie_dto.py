"""Страж безопасности Фазы 4: telegram_file_id НЕ должен утекать в DTO каталога.

telegram_file_id — внутренний id видео в канале-архиве, его видит только бот. MovieOut
(DTO для Web App) обязан его исключать — это ядро безопасности продукта. Тест ловит
регрессию на уровне DTO (без БД и HTTP): именно здесь проходит граница «наружу».
"""

from __future__ import annotations

from app.api.schemas.movie import MovieOut
from app.domain.entities.movie import Movie

_SECRET_FILE_ID = "BAACAgIAAxkBAAEC-secret-archive-file-id"


def _movie() -> Movie:
    return Movie(
        id=1,
        title_kk="Арыстан Патша",
        title_ru="Король Лев",
        title_original="The Lion King",
        description="сипаттама",
        category="disney",
        poster_url="/posters/abc.jpg",
        telegram_file_id=_SECRET_FILE_ID,
        year=1994,
        rating=8.5,
    )


def test_movieout_schema_has_no_telegram_file_id_field() -> None:
    # Структурная гарантия: поля нет в схеме → FastAPI физически не сможет его отдать.
    assert "telegram_file_id" not in MovieOut.model_fields


def test_from_domain_drops_telegram_file_id() -> None:
    dumped = MovieOut.from_domain(_movie()).model_dump()
    assert "telegram_file_id" not in dumped


def test_serialized_json_never_contains_secret_file_id() -> None:
    # Даже само значение не должно просочиться ни под каким ключом.
    payload = MovieOut.from_domain(_movie()).model_dump_json()
    assert _SECRET_FILE_ID not in payload
