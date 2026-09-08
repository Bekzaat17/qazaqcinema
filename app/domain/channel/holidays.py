"""Праздники Казахстана — данные + чистая функция «какой праздник сегодня».

Праздник это НЕ элемент недельной сетки (`content/plan.py`) и не элемент пула: сетка
задана днём недели и часом, пул крутится LRU-ротацией, а праздник привязан к ДАТЕ.
Поэтому у него свой справочник и свои джобы, а текст и картинка лежат в пуле обычным
элементом формы `greeting` (slug = slug праздника).

Правило даты — отдельный класс на каждый вид (`Fixed`, `NthWeekday`, `Lunar`), а не
`if` по типу праздника: новое правило (скажем, «пятница перед датой») = новый класс,
существующие не трогаются. `date_in(year)` возвращает `None`, если для года даты нет —
так ведут себя лунные праздники за пределами заполненной таблицы.

Многодневные праздники (Жаңа жыл 1–2 қаңтар, Наурыз 21–23 наурыз) поздравляются ОДИН
раз, в первый день: три поста подряд с одним смыслом обесценивают рубрику. Поэтому в
таблице у праздника ровно одна дата.

Скорбные даты (31 мамыр — репрессия және ашаршылық құрбандарын еске алу күні) здесь
СОЗНАТЕЛЬНО отсутствуют: канал поздравляет, а поминальный пост требует другого тона и
другого решения, чем «мереке құтты болсын».
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol

from app.domain.catalog.daily import TZ


class HolidayDate(Protocol):
    def date_in(self, year: int) -> date | None:
        """Дата праздника в этом году. `None` — в этом году даты нет (см. `Lunar`)."""
        ...

    def review(self, year: int) -> str | None:
        """Что не так с датой этого года: нет её вовсе, не подтверждена. `None` — всё в порядке.

        Метод правила, а не `if` по типу праздника: вычисляемым правилам сверять нечего,
        а лунному есть что — и ровно оно попадает в ежегодное напоминание админам.
        """
        ...


@dataclass(frozen=True, slots=True)
class Fixed:
    """Фиксированное число: 8 наурыз, 25 қазан."""

    month: int
    day: int

    def date_in(self, year: int) -> date | None:
        return date(year, self.month, self.day)

    def review(self, year: int) -> str | None:
        return None


@dataclass(frozen=True, slots=True)
class NthWeekday:
    """N-е воскресенье месяца: Ана күні — 3-е, Отбасы күні — 2-е (`nth=-1` — последнее).

    Считаем, а не держим таблицу по годам: правило детерминированное, и таблица тут
    была бы лишней работой, которую однажды забудут пополнить.
    """

    month: int
    weekday: int   # 0 = понедельник, как `date.weekday()`
    nth: int       # 1..5 либо -1 (последнее в месяце)

    def date_in(self, year: int) -> date | None:
        days_in_month = calendar.monthrange(year, self.month)[1]
        matching = [
            day
            for day in range(1, days_in_month + 1)
            if date(year, self.month, day).weekday() == self.weekday
        ]
        index = self.nth - 1 if self.nth > 0 else self.nth
        try:
            return date(year, self.month, matching[index])
        except IndexError:  # 5-го такого дня в этом месяце не бывает
            return None

    def review(self, year: int) -> str | None:
        return None


@dataclass(frozen=True, slots=True)
class Lunar:
    """Лунный календарь — таблица дат по годам, заполненная вручную.

    Вычислять нельзя: Ораза айт и Құрбан айт объявляет ДУМК (muftyat.kz), и объявленная
    дата отличается от астрономической на день в обе стороны. Года нет в таблице →
    `None` → поста не будет (сервис пишет об этом в лог). Это честнее, чем поздравить
    не в тот день: пост уходит всем подписчикам сразу.
    """

    dates: tuple[tuple[int, int, int], ...]   # (год, месяц, день)
    # Год, до которого даты ОБЪЯВЛЕНЫ ДУМК. Всё, что после, — астрономический прогноз:
    # он и попадает в ежегодное напоминание админам, а не остаётся комментарием в коде.
    announced_through: int = 0

    def date_in(self, year: int) -> date | None:
        for table_year, month, day in self.dates:
            if table_year == year:
                return date(year, month, day)
        return None

    def review(self, year: int) -> str | None:
        if self.date_in(year) is None:
            return f"{year} жылға дата жоқ — поздравления не будет"
        if year > self.announced_through:
            return f"{year} жылғы дата — прогноз, сверить с muftyat.kz"
        return None


@dataclass(frozen=True, slots=True)
class Holiday:
    """Праздник: когда поздравлять и каким элементом пула.

    `slug` — он же slug элемента в `content/holidays.yaml` (форма `greeting`): текст и
    картинка редактируются без правок кода. `hour` — МЕСТНЫЙ час поздравления (Алматы),
    `minute` нужен Новому году: в 00:01 лента пустая и поздравление видно первым.
    """

    slug: str
    title_kk: str          # для логов и предпросмотра; в посте — заголовок элемента
    when: HolidayDate
    hour: int = 9
    minute: int = 0


# Государственные и национальные праздники + всенародно отмечаемые даты. Порядок — по
# календарю; дополнять здесь (новая дата = одна строка).
#
# ⚠️ Список сверять по официальному календарю раз в год: закон о праздниках меняется
# (День Первого Президента отменён в 2022, Әке күні появился в 2023).
#
# Две даты на одни сутки — редкость, но бывает (в 2028-м Ұстаз күні выпадает ровно на
# Қарттар күні): тогда поздравления идут ОБА, каждое в свой час. Поэтому у таких дат
# часы РАЗНЫЕ — совпадение часа означало бы, что второе поздравление молча пропало.
HOLIDAYS: tuple[Holiday, ...] = (
    Holiday("zhana-zhyl", "Жаңа жыл", Fixed(1, 1), hour=0, minute=1),
    Holiday("rozhdestvo", "Рождество", Fixed(1, 7)),
    Holiday("aigys-aitu", "Алғыс айту күні", Fixed(3, 1)),
    Holiday("halyqaralyq-aiel", "Халықаралық әйелдер күні", Fixed(3, 8)),
    Holiday("konstitutsiya", "Конституция күні", Fixed(3, 15)),
    Holiday("nauryz", "Наурыз мейрамы", Fixed(3, 21)),
    Holiday("birlik", "Қазақстан халқының бірлігі күні", Fixed(5, 1)),
    Holiday("otan-qorgaushy", "Отан қорғаушы күні", Fixed(5, 7)),
    Holiday("zhenis", "Жеңіс күні", Fixed(5, 9)),
    Holiday("balalar", "Балаларды қорғау күні", Fixed(6, 1)),
    Holiday("ramizder", "Мемлекеттік рәміздер күні", Fixed(6, 4)),
    # Әке күні — 3-е воскресенье июня (официально с 2023).
    Holiday("ake-kuni", "Әке күні", NthWeekday(6, calendar.SUNDAY, 3)),
    Holiday("astana", "Астана күні", Fixed(7, 6)),
    Holiday("abai", "Абай күні", Fixed(8, 10)),
    Holiday("zhastar", "Жастар күні", Fixed(8, 12)),
    Holiday("bilim", "Білім күні", Fixed(9, 1)),
    Holiday("til", "Қазақстан халқы тілдері күні", Fixed(9, 5)),
    # Отбасы күні — 2-е воскресенье сентября, Ана күні — 3-е.
    Holiday("otbasy", "Отбасы күні", NthWeekday(9, calendar.SUNDAY, 2)),
    Holiday("ana-kuni", "Ана күні", NthWeekday(9, calendar.SUNDAY, 3)),
    Holiday("qarttar", "Қарттар күні", Fixed(10, 1)),
    # Ұстаз күні — 1-е воскресенье октября, а значит раз в несколько лет это ровно
    # 1 қазан (Қарттар күні). Час другой — тогда в такой день выходят оба поздравления.
    Holiday("ustaz", "Ұстаз күні", NthWeekday(10, calendar.SUNDAY, 1), hour=12),
    Holiday("respublika", "Республика күні", Fixed(10, 25)),
    Holiday("tauelsizdik", "Тәуелсіздік күні", Fixed(12, 16)),
    # ⚠️ Лунные праздники: даты объявляет ДУМК, `announced_through` отделяет объявленные
    # от прогноза. Года нет в таблице → поздравления не будет (пропуск лучше поздравления
    # не в тот день). Раз в год об этом напоминает джоб `holiday_calendar_review`.
    Holiday(
        "oraza-ait",
        "Ораза айт",
        Lunar(
            dates=(
                (2026, 3, 20), (2027, 3, 9),
                (2028, 2, 26), (2029, 2, 14), (2030, 2, 4),
            ),
            announced_through=2027,
        ),
    ),
    Holiday(
        "qurban-ait",
        "Құрбан айт",
        Lunar(
            dates=(
                (2026, 5, 27), (2027, 5, 16),
                (2028, 5, 5), (2029, 4, 24), (2030, 4, 13),
            ),
            announced_through=2027,
        ),
    ),
)

# Различные времена поздравлений из данных — по одному cron-джобу на каждое (см.
# `infrastructure/scheduler.py`). Ежечасный `content_post` не годится: он стреляет в
# :00 и 00:01 не поймает.
POST_TIMES: tuple[tuple[int, int], ...] = tuple(
    sorted({(holiday.hour, holiday.minute) for holiday in HOLIDAYS})
)


def holidays_on(now: datetime) -> tuple[Holiday, ...]:
    """Все праздники ЭТИХ местных суток — обычно один, но бывает и два."""
    today = now.astimezone(TZ).date()
    return tuple(h for h in HOLIDAYS if h.when.date_in(today.year) == today)


def holiday_today(now: datetime) -> Holiday | None:
    """Первый праздник этих суток — по нему сетка понимает, что сегодня молчит."""
    found = holidays_on(now)
    return found[0] if found else None


def holiday_for(now: datetime) -> Holiday | None:
    """Праздник, чей ЧАС поздравления наступил. Джоб вызывает в своё время.

    Сверяем час, а не минуту: misfire-окно джоба (рестарт бота) должно догнать
    поздравление внутри того же часа, а не потерять его до следующего года. Перебираем
    ВСЕ праздники дня: у совпавших дат часы разные, и каждое поздравление обязано
    дождаться своего.
    """
    hour = now.astimezone(TZ).hour
    for holiday in holidays_on(now):
        if holiday.hour == hour:
            return holiday
    return None


def holiday_slot_key(holiday: Holiday, now: datetime) -> str:
    """Ключ идемпотентности: `2027-03-21:holiday-nauryz`.

    Тот же UNIQUE `channel_post_log.slot_key`, что у слотов сетки: рестарт, misfire и
    повторный запуск не дадут второго поздравления в канале.
    """
    return f"{now.astimezone(TZ).date().isoformat()}:holiday-{holiday.slug}"


def review_notes(now: datetime) -> tuple[str, ...]:
    """Замечания по календарю на СЛЕДУЮЩИЙ год — текст ежегодного напоминания админам.

    Проверяем то, что проверяется машиной: есть ли у каждого праздника дата и подтверждена
    ли она. Сверка списка с законом — работа человека (закон меняется: Конституция күні
    переехал с 30 тамыз на 15 наурыз), поэтому напоминание уходит и при пустом списке
    замечаний.
    """
    year = now.astimezone(TZ).year + 1
    notes: list[str] = []
    for holiday in HOLIDAYS:
        note = holiday.when.review(year)
        if note is not None:
            notes.append(f"{holiday.title_kk}: {note}")
    return tuple(notes)
