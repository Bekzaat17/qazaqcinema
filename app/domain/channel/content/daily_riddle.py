"""Правила жұмбақ дня: местные сутки, три попытки и ответ после 21:00."""

from __future__ import annotations

from datetime import datetime, time
from html import escape

from app.domain.catalog.daily import TZ
from app.domain.channel.content.answers.normalize import fold, levenshtein
from app.domain.channel.content.item import ContentItem, QuizOpen
from app.domain.channel.content.render.base import frame

DAILY_RIDDLE_CALLBACK = "jumbak:today"
MAX_ATTEMPTS = 3
CLOSE_HOUR = 21
_SLOT_SUFFIX = ":jumbak"


def daily_riddle_key(now: datetime) -> str:
    return f"{now.astimezone(TZ).date().isoformat()}{_SLOT_SUFFIX}"


def is_daily_riddle(key: str) -> bool:
    return key.endswith(_SLOT_SUFFIX)


def daily_riddle_closes(now: datetime) -> datetime:
    return datetime.combine(now.astimezone(TZ).date(), time(CLOSE_HOUR), tzinfo=TZ)


def check_riddle_answer(quiz: QuizOpen, text: str) -> bool:
    """Один ответ целиком: список из десятков догадок не считается одной попыткой."""
    given = fold(text)
    if not given:
        return False
    for answer in quiz.accept:
        accepted = fold(answer)
        tolerance = min(2, sum(len(word) >= 5 for word in accepted.split()))
        if given == accepted or (tolerance and levenshtein(given, accepted) <= tolerance):
            return True
    return False


def render_daily_riddle(item: ContentItem) -> str:
    assert isinstance(item.payload, QuizOpen)
    body = "\n".join((
        f"❓ <b>{escape(item.payload.question)}</b>", "",
        "Жауабыңызды осы посттың комментарийіне жазыңыз 💬",
        "Немесе талқылау тобында: /answer жауабыңыз", "",
        "Әр адамға 3 мүмкіндік: дұрыс жауапқа 3 / 2 / 1 ұпай.",
        "Бот жауаптарды басқалар көрмес үшін жасырады.",
        "⏳ Жауаптар 21:00-ге дейін (Алматы уақыты).", "",
        "21:00-ден кейін /answer — жауабы мен қорытындысы.",
        "/rating — апталық рейтинг. Қорытынды тек сұраған кезде жарияланады.",
    ))
    return frame(item, body, 4096, head="🧩 <b>Күннің жұмбағы</b>")
