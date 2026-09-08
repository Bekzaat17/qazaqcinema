"""SEO-ядро: slug'и, формулировки поискового спроса и тексты посадочных страниц.

Без внешних зависимостей и без I/O — только преобразование данных фильма в строки,
которые presentation (SSR-роутер) кладёт в HTML. Логика «как выглядит SEO» живёт здесь,
а не размазана по шаблонам, поэтому её можно тестировать и переиспользовать (страница + sitemap).
"""

from __future__ import annotations

from app.domain.seo.slug import movie_slug, slugify, transliterate

__all__ = ["movie_slug", "slugify", "transliterate"]
