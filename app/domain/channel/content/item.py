"""Элемент контента и типизированные payload'ы форм.

В БД payload — JSONB (форма у видов разная, разреженные колонки были бы хуже), но
домен работает с dataclass'ами: рендерер квиза получает `QuizChoice`, а не словарь,
и опечатка в ключе ловится на границе (в репозитории при маппинге), а не в тексте
поста. Тот же принцип, что ORM ↔ domain у фильмов.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

from app.domain.channel.content.kinds import ContentKind

# Лимиты Telegram: обычное сообщение и подпись к фото. Держатся здесь, потому что от
# них зависит ДОМЕННОЕ решение — резать ли текст и что пойдёт подписью к карточке.
MESSAGE_LIMIT = 4096
CAPTION_LIMIT = 1024

# Буквы вариантов квиза — казахский алфавит, чтобы кнопки читались «своими».
CHOICE_LETTERS = ("А", "Ә", "Б", "В", "Г")


@dataclass(frozen=True, slots=True)
class QuizChoice:
    """Вопрос с вариантами; `answer` — индекс правильного в `options`."""

    question: str
    options: tuple[str, ...]
    answer: int

    def __post_init__(self) -> None:
        if not 2 <= len(self.options) <= len(CHOICE_LETTERS):
            raise ValueError(f"вариантов должно быть 2–{len(CHOICE_LETTERS)}")
        if not 0 <= self.answer < len(self.options):
            raise ValueError("answer указывает за пределы options")


@dataclass(frozen=True, slots=True)
class QuizOpen:
    """Вопрос с открытым ответом; `accept` — допустимые написания (первое — каноническое,
    его печатает разбор). Сравнение — после нормализации, см. `answers/normalize`."""

    question: str
    accept: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.accept:
            raise ValueError("нужен хотя бы один допустимый ответ")


@dataclass(frozen=True, slots=True)
class Term:
    term: str
    meaning: str


@dataclass(frozen=True, slots=True)
class TermList:
    items: tuple[Term, ...]
    # Необязательное пояснение после списка («…так до шести лет, дальше — просто ат»).
    note: str = ""

    def __post_init__(self) -> None:
        if not self.items:
            raise ValueError("список терминов пуст")


Payload = QuizChoice | QuizOpen | TermList | None


@dataclass(slots=True)
class ContentItem:
    slug: str            # натуральный ключ сидера: тот же slug в YAML → тот же элемент (upsert)
    kind: ContentKind
    topic: str           # slug из `topics.TOPICS`
    title_kk: str
    body_kk: str         # основной текст (у квизов может быть пустым — вопрос в payload)
    source: str = ""     # атрибуция: «Абай Құнанбайұлы, 17-ші қара сөз»
    image_path: str | None = None    # относительно MEDIA_ROOT: `channel/<slug>.jpg`
    image_credit: str = ""           # автор/лицензия картинки (CC-BY-SA требует упоминания)
    payload: Payload = None
    scheduled_for: date | None = None  # редакторский пин на дату; побеждает ротацию
    last_posted_at: datetime | None = None
    post_count: int = 0
    is_active: bool = True
    id: int | None = None
    created_at: datetime | None = field(default=None, compare=False)
