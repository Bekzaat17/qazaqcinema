"""Недельная сетка постов канала — данные + чистая функция `slot_for`.

Один ежечасный джоб спрашивает: «есть ли слот на этот час?» — и получает слот с ЦЕПОЧКОЙ
источников. Источник — это (форма, тема, ось разнообразия, можно ли повторять). Цепочка —
фолбэк: когда пул первого источника исчерпан (у `repeat=False` — все элементы уже
постились), слот переходит к следующему. Так воскресенье «қара сөз → нақыл сөз» само
переключится на цитаты, когда 45 сөз Абая закончатся, без правок кода.

Часы — по Алматы (тот же `TZ`, что у фильма дня): контейнеры живут в UTC. Не 10:00 —
в этот час уже уходит фильм дня, два поста подряд склеиваются в ленте.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from enum import StrEnum

from app.domain.catalog.daily import TZ
from app.domain.channel.content.kinds import ContentKind


class Vary(StrEnum):
    """Ось разнообразия источника: что именно НЕ должно идти в ленте подряд.

    Пул залит из `content/*.yaml` пачками (сначала девять вопросов про жылқы, потом про
    төрт түлік; сначала двадцать цитат Абая, потом Момышұлы), а ротация берёт «никогда не
    постившийся, тай-брейк по id» — то есть ровно порядок файла. Подписчик видит месяц
    лошадей и квартал Абая, хотя в пуле 12 рубрик и 13 авторов. Ось говорит, по какому
    полю считать «уже было недавно»; сортировать файлы руками бесполезно — следующая
    заливка снова придёт пачкой.
    """

    TOPIC = "topic"    # рубрика: атаулары, атау-сұрақ, мақал — не две лошади подряд
    SOURCE = "source"  # автор: нақыл сөз — не два Абая подряд
    NONE = "none"      # порядок важен сам по себе: қара сөз читаются по номерам


# Сколько «остывает» рубрика (автор) после выпуска. Три недели = три выпуска еженедельного
# слота: ровно та дистанция, на которой повтор рубрики перестаёт читаться как «опять то же
# самое». Правило МЯГКОЕ — ключ сортировки, а не фильтр: когда остывают все (у жұмбақ
# рубрика одна на весь пул), слот всё равно постит, просто по LRU.
VARIETY_COOLDOWN = timedelta(days=21)


@dataclass(frozen=True, slots=True)
class Source:
    kind: ContentKind
    topic: str | None = None   # None — любая тема этой формы
    # False — элемент постится ровно один раз, пул исчерпался → источник «пуст» (қара сөз:
    # 45 штук, второй круг Абая заметен). True — LRU-ротация по кругу (мақал через много
    # месяцев повторить нормально, повторится самое давнее).
    repeat: bool = True
    # По умолчанию разнообразим по рубрике: новая форма получает это даром, а выключается
    # осознанно — там, где порядок и есть смысл (`Vary.NONE`).
    vary: Vary = Vary.TOPIC


@dataclass(frozen=True, slots=True)
class Slot:
    name: str                  # часть `slot_key` — устойчивое имя, не индекс в кортеже
    weekday: int               # 0 = понедельник (как `date.weekday()`)
    hour: int
    sources: tuple[Source, ...]
    # Для квизов: час того же дня, когда ответы закрываются и уходит разбор.
    closes_hour: int | None = None


SLOTS: tuple[Slot, ...] = (
    # Дс — квиз с кнопками (мақал/атау-сұрақ), фолбэк — открытый.
    Slot(
        "quiz-mon", 0, 12,
        (Source(ContentKind.QUIZ_CHOICE), Source(ContentKind.QUIZ_OPEN)),
        closes_hour=21,
    ),
    # Сс — нақыл сөз, разнообразие по АВТОРУ: рубрика одна, а имён в пуле тринадцать.
    Slot("saying", 1, 19, (Source(ContentKind.SAYING, vary=Vary.SOURCE),)),
    # Ср — атаулары.
    Slot("terms", 2, 19, (Source(ContentKind.TERM_LIST),)),
    # Бс — квиз открытый (жұмбақ), фолбэк — с кнопками.
    Slot(
        "quiz-thu", 3, 12,
        (Source(ContentKind.QUIZ_OPEN), Source(ContentKind.QUIZ_CHOICE)),
        closes_hour=21,
    ),
    # Жс — Абайдың қара сөзі, без повторов и ПО ПОРЯДКУ (1-ші, 2-ші, 3-ші…): у қара сөз
    # есть номера, и перемешанная нумерация читается как сбой. Закончатся → нақыл сөз.
    Slot(
        "abai", 6, 19,
        (
            Source(ContentKind.LONGREAD, topic="abai", repeat=False, vary=Vary.NONE),
            Source(ContentKind.SAYING, vary=Vary.SOURCE),
        ),
    ),
)


def slot_for(now: datetime) -> Slot | None:
    """Слот, чей час наступил в МЕСТНЫХ сутках `now`. Джоб вызывает раз в час в :00."""
    local = now.astimezone(TZ)
    for slot in SLOTS:
        if slot.weekday == local.weekday() and slot.hour == local.hour:
            return slot
    return None


def slot_key(slot: Slot, now: datetime) -> str:
    """Ключ идемпотентности публикации: местная дата + имя слота (`2026-09-14:quiz-mon`).

    UNIQUE в `channel_post_log` — рестарт бота, misfire и вторая реплика не дадут дубля
    в канале, где его увидели бы все подписчики.
    """
    return f"{now.astimezone(TZ).date().isoformat()}:{slot.name}"


def closes_at(slot: Slot, now: datetime) -> datetime | None:
    """Когда закрываются ответы квиза этого слота (местное время того же дня). Не квиз → None."""
    if slot.closes_hour is None:
        return None
    local_day = now.astimezone(TZ).date()
    return datetime.combine(local_day, time(hour=slot.closes_hour), tzinfo=TZ)
