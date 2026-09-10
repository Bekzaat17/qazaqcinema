"""Пагинация страниц-хабов: сколько страниц, куда ведут ссылки, что писать в canonical.

Чистые правила без I/O и без Jinja: шаблон получает готовые строки и только подставляет их.
Отдельный модуль, потому что от этих правил зависит индексация, а не только вид страницы.

Что здесь решено раз и навсегда:

⚠️ **Каждая страница пагинации канонична сама себе.** Соблазн поставить `canonical` второй
страницы на первую велик — и он выбрасывает из индекса все фильмы, которые видны только со
второй: Google считает такую страницу дублем и её ссылки не учитывает. Поэтому
`canonical_suffix` возвращает `?page=N` для N>1, а не пустую строку.

⚠️ **Первая страница живёт по чистому URL.** `?page=1` — тот же документ по второму адресу,
то есть дубль; роутер отдаёт на него 301, а ссылки «назад» на первую страницу строятся
без параметра.

`rel=prev/next` Google не использует с 2019 года, но Bing и Яндекс — да, и стоит он ноль.
Настоящая навигация для краулера — обычные `<a href>` с номерами плюс все страницы в sitemap.
"""

from __future__ import annotations

from dataclasses import dataclass

# Сколько номеров показываем без сокращения. Дальше середина сворачивается в «…»:
# на каталоге в тысячу фильмов это 21 страница, и подвал из 21 ссылки — уже не навигация.
_NUMBERS_FULL = 9
# Сколько соседей вокруг текущей страницы остаётся при сокращении (с каждой стороны).
_NUMBERS_AROUND = 2


@dataclass(frozen=True, slots=True)
class Pagination:
    """Где мы в списке и как выглядят ссылки. `path` — базовый путь без query-параметра."""

    path: str
    page: int
    pages: int

    def url(self, page: int) -> str:
        """URL страницы. Первая — без параметра (иначе получаем дубль чистого адреса)."""
        return self.path if page <= 1 else f"{self.path}?page={page}"

    @property
    def has_pages(self) -> bool:
        """Показывать ли навигацию вообще (одна страница — нечего листать)."""
        return self.pages > 1

    @property
    def prev_url(self) -> str | None:
        return self.url(self.page - 1) if self.page > 1 else None

    @property
    def next_url(self) -> str | None:
        return self.url(self.page + 1) if self.page < self.pages else None

    @property
    def canonical_suffix(self) -> str:
        """Хвост к canonical/og:url: страница ссылается на СЕБЯ, а не на первую."""
        return "" if self.page <= 1 else f"?page={self.page}"

    @property
    def title_suffix(self) -> str:
        """Хвост к <title> и H1-подписи: без него у всех страниц был бы один заголовок."""
        return "" if self.page <= 1 else f" — {self.page}-бет"

    @property
    def numbers(self) -> list[int | None]:
        """Номера для подвала; `None` — место разрыва («…»).

        Крайние страницы остаются видимыми всегда: с них начинается обход и на них
        заканчивается, а «…» между ними экономит место, не отрезая путь.
        """
        if self.pages <= _NUMBERS_FULL:
            return list(range(1, self.pages + 1))

        window = range(
            max(2, self.page - _NUMBERS_AROUND),
            min(self.pages - 1, self.page + _NUMBERS_AROUND) + 1,
        )
        shown = {1, self.pages, *window}
        out: list[int | None] = []
        previous = 0
        for number in sorted(shown):
            if number - previous > 1:
                out.append(None)
            out.append(number)
            previous = number
        return out


def page_count(total: int, size: int) -> int:
    """Сколько страниц у списка. Пустой список — всё равно одна (её и отдаём с 200)."""
    if size < 1:
        raise ValueError("размер страницы должен быть положительным")
    return max(1, -(-total // size))  # округление вверх без float


def paginate(*, path: str, page: int, total: int, size: int) -> Pagination:
    """Собрать пагинацию для готового среза. `page` уже проверен роутером на диапазон."""
    return Pagination(path=path, page=page, pages=page_count(total, size))
