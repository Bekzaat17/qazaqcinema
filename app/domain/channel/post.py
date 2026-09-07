"""Тексты постов публичного канала. Чистые функции: ни Telegram, ни БД.

Тот же приём, что у `analytics/report.render_report`: ЧТО написано в посте — домен и
проверяется юнит-тестом, а куда и чем отправлять — забота адаптера и планировщика.

Канал публичный и живёт по своим правилам, поэтому текст здесь не совпадает с текстом
рассылки в личку (`BroadcastService`): в личке человек уже наш и ему достаточно
«жаңа фильм», а в канале пост читают и те, кто про кинотеатр ничего не знает — им нужны
и «қазақша дубляж» как повод, и хэштеги как навигация.

HTML: подставляемые данные (название, описание) экранируем ЗДЕСЬ, потому что здесь
собирается строка — иначе `<` в названии фильма сломал бы парсинг, и Telegram отказал
бы в отправке всего поста.
"""

from __future__ import annotations

from html import escape

from app.domain.catalog.categories import get_category
from app.domain.entities.movie import Movie

# Лимит подписи к фото в Telegram — 1024 символа. Держим запас: HTML-теги тоже считаются,
# а описание у фильма бывает длинным (визард его не ограничивает).
CAPTION_LIMIT = 900
# Сколько хэштегов ставим. Фильм бывает в 5-6 категориях, но простыня тегов читается как
# спам — а канал продаёт язык и продукт, не ключевые слова (то же правило, что в SEO:
# видимый блок курируется, «без переспама»).
MAX_HASHTAGS = 3

_DUB_NOTE = "🇰🇿 Қазақша дубляж"


def _hashtag(label: str) -> str:
    """Казахская подпись категории → хэштег.

    Пробелы и дефисы Telegram считает КОНЦОМ тега, поэтому «Қиял-ғажайып» без чистки
    дал бы кликабельным только «#Қиял». Убираем всё, что не буква и не цифра, склеивая
    слова: «Шытырман оқиға» → `#ШытырманОқиға`.
    """
    parts = [word for word in label.replace("-", " ").split() if word]
    return "#" + "".join(word[:1].upper() + word[1:] for word in parts)


def hashtags(categories: list[str]) -> str:
    """Строка хэштегов по категориям фильма (не больше `MAX_HASHTAGS`).

    Порядок — как у фильма (визард даёт его от общего к частному); незнакомые slug'и
    пропускаем: справочник — источник правды подписей, а тег из сырого slug был бы
    англоязычным огрызком в казахской ленте.
    """
    labels = [
        category.title_kk
        for slug in categories
        if (category := get_category(slug)) is not None
    ]
    return " ".join(_hashtag(label) for label in labels[:MAX_HASHTAGS])


def clip(text: str, limit: int = CAPTION_LIMIT) -> str:
    text = text.strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _title_line(movie: Movie) -> str:
    """Название + год жирным. Год — в той же строке: отдельной он занимал бы место зря."""
    title = f"<b>{escape(movie.title_kk)}</b>"
    return f"{title} ({movie.year})" if movie.year is not None else title


def _meta_line(movie: Movie) -> str:
    """«Қазақша дубляж» + рейтинг. Дубляж — ГЛАВНОЕ, что отличает нас, поэтому всегда.

    Рейтинг только если он есть: «⭐️ —» выглядело бы как отсутствие качества, тогда как
    на самом деле это просто незаполненное поле визарда.
    """
    if movie.rating is None:
        return _DUB_NOTE
    return f"{_DUB_NOTE} · ⭐️ {movie.rating:g}"


def _body(movie: Movie, header: str, footer: str = "") -> str:
    """Общий каркас поста: шапка → название → мета → описание → подвал → хэштеги.

    Обрезается ЦЕЛИКОМ по `CAPTION_LIMIT`, а не только описание: подпись к фото Telegram
    режет по своему лимиту молча, и без общей обрезки первым терялся бы хвост — то есть
    хэштеги и подвал, самое полезное для навигации по каналу.
    """
    blocks = [header, f"{_title_line(movie)}\n{_meta_line(movie)}"]
    if movie.description.strip():
        blocks.append(escape(movie.description.strip()))
    if footer:
        blocks.append(footer)
    if tags := hashtags(movie.categories):
        blocks.append(tags)
    return clip("\n\n".join(blocks))


def render_new_movie(movie: Movie) -> str:
    """Пост о новинке: «залили — смотрите»."""
    return _body(movie, "🎬 <b>Жаңа фильм қосылды!</b>")


def render_daily_movie(movie: Movie) -> str:
    """Пост про фильм дня: главное здесь — что смотреть можно БЕСПЛАТНО и только сегодня.

    Срок в подвале словами («тек бүгін»), а не временем: граница — местная полночь, и
    точный час в тексте лишь путал бы тех, кто читает пост вечером. Ограниченность —
    это и есть причина открыть приложение сейчас, а не «когда-нибудь».
    """
    return _body(
        movie,
        "📅 <b>Күн фильмі — бүгін тегін!</b>",
        footer="⏳ Тек бүгін — жазылымсыз, тегін көріңіз.",
    )
