"""Разбор квиза: цифры → текст поста-ответа. Чистая функция.

Разбор — НЕ элемент контента (PLAN.md §4): он собирается из квиза и журнала ответов и
уходит ответом на сам пост. Считаем честно: «сколько ответили» и «сколько верно» — по
первому ответу каждого; «алғашқы үшеу» — первые правильные по времени.
"""

from __future__ import annotations

from dataclasses import dataclass
from html import escape

from app.domain.channel.content.item import (
    CHOICE_LETTERS,
    MESSAGE_LIMIT,
    ContentItem,
    QuizChoice,
    QuizOpen,
)
from app.domain.channel.content.render.base import frame

_MEDALS = ("🥇", "🥈", "🥉")


@dataclass(frozen=True, slots=True)
class QuizStats:
    total: int
    correct: int
    first_correct: tuple[str, ...]   # имена первых правильно ответивших, по времени


def correct_answer_text(item: ContentItem) -> str:
    """Правильный ответ словами — для разбора и для всплывашки «қате, жауабы — …»."""
    match item.payload:
        case QuizChoice() as quiz:
            return quiz.options[quiz.answer]
        case QuizOpen() as quiz:
            return quiz.accept[0]
        case _:
            return ""


def question_text(item: ContentItem) -> str:
    match item.payload:
        case QuizChoice() as quiz:
            return quiz.question
        case QuizOpen() as quiz:
            return quiz.question
        case _:
            return item.title_kk


def render_result(item: ContentItem, stats: QuizStats) -> str:
    """Текст разбора: вопрос, ответ, сколько людей, первые трое."""
    lines = [f"<i>{escape(question_text(item))}</i>", ""]
    answer = escape(correct_answer_text(item))
    if isinstance(item.payload, QuizChoice):
        letter = CHOICE_LETTERS[item.payload.answer]
        lines.append(f"✅ Дұрыс жауап: <b>{letter}) {answer}</b>")
    else:
        lines.append(f"✅ Жауабы: <b>{answer}</b>")
    lines.append("")
    if stats.total == 0:
        lines.append("Бүгін жауап берген болмады — келесі жолы сынап көріңіз! 😉")
    else:
        lines.append(f"👥 {stats.total} адам жауап берді, {stats.correct} дұрыс тапты.")
        if stats.first_correct:
            podium = " · ".join(
                f"{medal} {escape(name)}"
                for medal, name in zip(_MEDALS, stats.first_correct, strict=False)
            )
            lines.append(f"{podium} — алғашқылар! 👏")
    return frame(item, "\n".join(lines), MESSAGE_LIMIT)
