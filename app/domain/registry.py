"""Дженерик-реестр `slug → класс` с саморегистрацией через декоратор.

Реализует Open/Closed: добавить новую реализацию = новый класс + `@registry.register("slug")`,
без правок существующего кода и без центрального enum. Discovery — через импорты в
`__init__.py` пакета (иначе реестр останется пустым). Синтаксис дженериков — PEP 695.
"""

from __future__ import annotations

from collections.abc import Callable


class Registry[T]:
    def __init__(self, kind: str) -> None:
        self._kind = kind
        self._items: dict[str, type[T]] = {}

    def register(self, slug: str) -> Callable[[type[T]], type[T]]:
        def decorator(cls: type[T]) -> type[T]:
            if slug in self._items:
                raise ValueError(f"{self._kind}: slug '{slug}' уже зарегистрирован")
            self._items[slug] = cls
            return cls

        return decorator

    def get(self, slug: str) -> type[T]:
        try:
            return self._items[slug]
        except KeyError:
            raise KeyError(f"{self._kind}: неизвестный slug '{slug}'") from None

    def slugs(self) -> list[str]:
        return list(self._items)

    def __contains__(self, slug: object) -> bool:
        return slug in self._items
