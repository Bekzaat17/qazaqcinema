"""Поисковый ключ музыки: одна форма для казахской, русской кириллицы и латиницы.

Казахскую музыку ищут как попало: «Қайрат Нұртас», «Кайрат Нуртас», «Kairat Nurtas»,
«Qairat». `unaccent` здесь не помогает — Қ, Ұ, Ә для него отдельные буквы, а не буквы с
диакритикой. Поэтому и название трека, и запрос сводятся к одной латинской форме: Қ→k,
Ұ/Ү→u, Ә→a, Ө→o, І/И/Й/Ы→i, Ж→j, Х/Һ→h, латинские kh/zh/q/y/c — туда же; двойные
буквы схлопываются. Ключ хранится у трека и пересчитывается при каждом переименовании.

Правило намеренно грубое: точность добирает ранжирование (совпадение всех слов выше
нечёткого), а потерять находку из-за «қ» вместо «к» хуже, чем показать лишнюю строку.
"""

from __future__ import annotations

import re
import unicodedata

_CYRILLIC = {
    "а": "a", "ә": "a", "б": "b", "в": "v", "г": "g", "ғ": "g", "д": "d", "е": "e",
    "ё": "e", "ж": "zh", "з": "z", "и": "i", "й": "i", "і": "i", "к": "k", "қ": "k",
    "л": "l", "м": "m", "н": "n", "ң": "n", "о": "o", "ө": "o", "п": "p", "р": "r",
    "с": "s", "т": "t", "у": "u", "ұ": "u", "ү": "u", "ф": "f", "х": "h", "һ": "h",
    "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sh", "ъ": "", "ы": "i", "ь": "", "э": "e",
    "ю": "iu", "я": "ia",
}
# Казахская латиница (обе редакции алфавита) — до снятия диакритики, иначе ş стала бы s.
_LATIN_SPECIAL = {
    "ş": "sh", "ç": "ch", "ğ": "g", "ñ": "n", "ı": "i", "ä": "a", "ö": "o", "ü": "u",
    "ú": "u", "ý": "i", "á": "a", "ó": "o", "ń": "n", "ǵ": "g",
}
_DIGRAPHS = (("kh", "h"), ("zh", "j"), ("dj", "j"), ("yu", "iu"), ("ya", "ia"), ("ts", "c"))
_SINGLE = str.maketrans({"q": "k", "y": "i", "w": "u"})


def fold(text: str) -> str:
    """Свести строку к поисковому ключу (регистр, алфавит, пунктуация не важны)."""
    lowered = unicodedata.normalize("NFKC", text).casefold()
    chars = [_CYRILLIC.get(ch, _LATIN_SPECIAL.get(ch, ch)) for ch in lowered]
    stripped = unicodedata.normalize("NFKD", "".join(chars))
    latin = "".join(ch for ch in stripped if not unicodedata.combining(ch))
    for source, target in _DIGRAPHS:
        latin = latin.replace(source, target)
    latin = latin.translate(_SINGLE)
    latin = re.sub(r"c(?!h)", "k", latin)       # Scriptonite = Скриптонит
    latin = re.sub(r"([a-z])\1+", r"\1", latin)  # Kairatt, Нұртасс
    return " ".join(re.sub(r"[^a-z0-9]+", " ", latin).split())


def words(key: str, min_len: int = 2) -> list[str]:
    """Слова ключа, достаточно длинные, чтобы искать их по отдельности (любой порядок)."""
    return [word for word in key.split() if len(word) >= min_len]
