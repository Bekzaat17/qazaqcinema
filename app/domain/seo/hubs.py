"""Хабы каталога: что за страница живёт по `/catalog/<slug>` и что на ней показывать.

Хаб — это страница-список со своим заголовком, своим текстом и своим правилом отбора.
Их три вида, и все они здесь сводятся к одному типу `Hub`:

  * **раздел** — `/catalog/kids`, отбор по категории (тексты — `landing.py`);
  * **подборка** — `/catalog/new`, `/catalog/popular`: тот же каталог, но в другом
    порядке; страница существует ради широкого запроса («новинки мультфильмов
    на казахском») и ради внутренних ссылок;
  * **год** — `/catalog/2024`, отбор по году выпуска.

Единый тип нужен, чтобы страница, шаблон и sitemap не знали про эти различия: новая
подборка — строка в `COLLECTIONS`, и она сразу получает страницу, пагинацию, строку в
карте сайта и врезку в перелинковке. Разбор `if/elif` по видам страниц существует ровно
в одном месте — `resolve_hub`.

⚠️ Слаги подборок делят пространство имён с категориями (`/catalog/<что-то>`), поэтому
`COLLECTIONS` и `CATEGORIES` не должны пересекаться — это закреплено тестом. Пространство
одно намеренно: `/catalog/new` — это раздел каталога, а не отдельная сущность, и лишний
путь верхнего уровня пришлось бы отдельно проксировать в Caddy.

Порядок отбора описан своим перечислением (`HubOrder`), а не именем колонки: домен не
знает про SQL и про `SortField` — сопоставление делает сервис.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from app.domain.catalog.categories import CATEGORIES, Category
from app.domain.seo.landing import landing_for


class HubKind(StrEnum):
    """Вид хаба. Нужен только представлению: подписи крошек и приоритет в sitemap."""

    CATEGORY = "category"
    COLLECTION = "collection"
    YEAR = "year"


class HubOrder(StrEnum):
    """Порядок карточек на хабе. Сервис переводит его в сортировку репозитория."""

    NEWEST = "newest"
    POPULAR = "popular"


@dataclass(frozen=True, slots=True)
class Hub:
    """Готовое описание страницы-списка: чем она озаглавлена, что отбирает, как сортирует."""

    slug: str
    kind: HubKind
    heading_kk: str
    heading_ru: str
    intro: str
    order: HubOrder = HubOrder.NEWEST
    # Фильтры. Оба пустые — хаб по всему каталогу (таковы подборки).
    category: str | None = None
    year: int | None = None
    tags: tuple[str, ...] = field(default_factory=tuple)

    @property
    def path(self) -> str:
        return f"/catalog/{self.slug}"


@dataclass(frozen=True, slots=True)
class Collection:
    """Подборка — данные: слаг, тексты и порядок. Новая подборка = строка в `COLLECTIONS`."""

    slug: str
    heading_kk: str
    heading_ru: str
    intro: str
    order: HubOrder
    # Короткая подпись для врезки на других страницах («Жаңа түскен»).
    shelf_kk: str
    tags: tuple[str, ...] = field(default_factory=tuple)


COLLECTIONS: dict[str, Collection] = {
    "new": Collection(
        slug="new",
        heading_kk="Жаңа түскен қазақша мультфильмдер",
        heading_ru="Новинки мультфильмов на казахском языке",
        intro=(
            "Каталогқа соңғы қосылған қазақша мультфильмдер мен фильмдер — жаңасы жоғарыда. "
            "Новинки с казахской озвучкой: что добавили последним, то и наверху."
        ),
        order=HubOrder.NEWEST,
        shelf_kk="Жаңа түскен",
        tags=(
            "жаңа қазақша мультфильмдер",
            "новинки на казахском",
            "жаңа мультфильмдер қазақша",
            "новые мультики на казахском языке",
            "жаңа фильмдер қазақша",
        ),
    ),
    "popular": Collection(
        slug="popular",
        heading_kk="Танымал қазақша мультфильмдер",
        heading_ru="Популярные мультфильмы на казахском языке",
        intro=(
            "Ең көп қаралған және таңдаулыға жиі қосылған қазақша мультфильмдер. "
            "Популярное на казахском: то, что смотрят и добавляют в избранное чаще всего."
        ),
        order=HubOrder.POPULAR,
        shelf_kk="Танымал",
        tags=(
            "танымал қазақша мультфильмдер",
            "популярные мультики на казахском",
            "ең жақсы қазақша мультфильмдер",
            "лучшие мультфильмы на казахском языке",
            "топ мультфильмдер қазақша",
        ),
    ),
}

# Границы правдоподобного года выпуска. Ниже — заведомо опечатка в визарде, и страницы
# такому «году» не положено: она была бы тонкой и висела бы в индексе мусором.
_YEAR_MIN = 1900
_YEAR_MAX = 2100
# Сколько фильмов должно быть в году, чтобы у него появилась страница. Один-два фильма —
# это не «мультфильмы 2024 года», а карточка фильма, у которой своя страница уже есть.
YEAR_MIN_MOVIES = 4


def category_hub(category: Category) -> Hub:
    """Хаб раздела: тексты берём из посадочных данных (`landing.py`)."""
    landing = landing_for(category)
    return Hub(
        slug=category.slug,
        kind=HubKind.CATEGORY,
        heading_kk=landing.heading_kk,
        heading_ru=landing.heading_ru,
        intro=landing.intro,
        category=category.slug,
    )


def collection_hub(collection: Collection) -> Hub:
    return Hub(
        slug=collection.slug,
        kind=HubKind.COLLECTION,
        heading_kk=collection.heading_kk,
        heading_ru=collection.heading_ru,
        intro=collection.intro,
        order=collection.order,
        tags=collection.tags,
    )


def year_hub(year: int) -> Hub:
    """Хаб года. Тексты собираются из числа — таблицы на каждый год не бывает."""
    return Hub(
        slug=str(year),
        kind=HubKind.YEAR,
        heading_kk=f"{year} жылғы қазақша мультфильмдер",
        heading_ru=f"Мультфильмы {year} года на казахском языке",
        intro=(
            f"{year} жылы шыққан мультфильмдер мен фильмдердің қазақ тіліндегі дубляжы. "
            f"Мультфильмы и фильмы {year} года с казахской озвучкой — смотрите онлайн."
        ),
        year=year,
        tags=(
            f"{year} қазақша мультфильмдер",
            f"мультфильмы {year} на казахском",
            f"{year} жылғы мультфильмдер",
            f"новинки {year} на казахском языке",
        ),
    )


def parse_year(slug: str) -> int | None:
    """Год из слага или None. Только четыре цифры: `/catalog/24` годом не считается."""
    if len(slug) != 4 or not slug.isdigit():
        return None
    year = int(slug)
    return year if _YEAR_MIN <= year <= _YEAR_MAX else None


def resolve_hub(slug: str, *, year_counts: dict[int, int]) -> Hub | None:
    """Какая страница живёт по `/catalog/<slug>`. None → 404.

    ЕДИНСТВЕННОЕ место, где виды хабов разбираются по слагу. Порядок проверок важен:
    подборки идут первыми, потому что их слаги — обычные слова и однажды могут совпасть
    с новой категорией; тест на непересечение ловит это на месте.

    Год получает страницу только при `YEAR_MIN_MOVIES` фильмах и больше: тонкая страница
    ни по какому запросу не ранжируется, зато тратит бюджет обхода.
    """
    collection = COLLECTIONS.get(slug)
    if collection is not None:
        return collection_hub(collection)

    year = parse_year(slug)
    if year is not None:
        return year_hub(year) if year_counts.get(year, 0) >= YEAR_MIN_MOVIES else None

    category = CATEGORIES.get(slug)
    return category_hub(category) if category is not None else None


def indexable_years(year_counts: dict[int, int]) -> list[int]:
    """Годы, у которых есть своя страница, от свежих к старым (навигация и sitemap)."""
    return sorted(
        (year for year, count in year_counts.items() if count >= YEAR_MIN_MOVIES),
        reverse=True,
    )
