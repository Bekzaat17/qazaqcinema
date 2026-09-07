"""Рендереры квизов.

`quiz_choice`: вопрос + варианты списком в тексте (А) … Ә) …) и те же буквы кнопками под
постом. callback_data — `qz:<item_id>:<index>`: по сообщению бот найдёт пост в журнале,
по индексу — вариант; id элемента — сверка, что кнопка от этого квиза.

`quiz_open`: вопрос + приглашение ответить в комментариях. Бот удалит ответ и подтвердит
приём — об этом честно написано в посте, иначе исчезающий комментарий выглядит как сбой.
"""

from __future__ import annotations

from html import escape

from app.domain.channel.content.item import (
    CAPTION_LIMIT,
    CHOICE_LETTERS,
    MESSAGE_LIMIT,
    ContentItem,
    QuizChoice,
    QuizOpen,
)
from app.domain.channel.content.kinds import ContentKind
from app.domain.channel.content.render.base import (
    RENDERERS,
    CallbackButton,
    RenderedPost,
    frame,
)

CALLBACK_PREFIX = "qz"
_CLOSES_NOTE = "⏳ Жауаптар 21:00-ге дейін қабылданады, содан кейін — талдау."


def callback_data(item_id: int, index: int) -> str:
    return f"{CALLBACK_PREFIX}:{item_id}:{index}"


def parse_callback(data: str) -> tuple[int, int] | None:
    """`qz:<item_id>:<index>` → (item_id, index); чужой/битый формат → None."""
    parts = data.split(":")
    if len(parts) != 3 or parts[0] != CALLBACK_PREFIX:
        return None
    if not (parts[1].isdigit() and parts[2].isdigit()):
        return None
    return int(parts[1]), int(parts[2])


def _limit(item: ContentItem) -> int:
    return CAPTION_LIMIT if item.image_path else MESSAGE_LIMIT


@RENDERERS.register(ContentKind.QUIZ_CHOICE.value)
class QuizChoiceRenderer:
    def render(self, item: ContentItem) -> RenderedPost:
        quiz = item.payload
        if not isinstance(quiz, QuizChoice):
            raise ValueError(f"{item.slug}: quiz_choice без QuizChoice payload")
        lines = [f"❓ <b>{escape(quiz.question)}</b>", ""]
        lines += [
            f"{CHOICE_LETTERS[i]}) {escape(option)}" for i, option in enumerate(quiz.options)
        ]
        lines += ["", "Жауабыңызды төмендегі батырмамен таңдаңыз 👇", _CLOSES_NOTE]
        buttons = tuple(
            CallbackButton(CHOICE_LETTERS[i], callback_data(item.id or 0, i))
            for i in range(len(quiz.options))
        )
        return RenderedPost(head=frame(item, "\n".join(lines), _limit(item)), buttons=buttons)


@RENDERERS.register(ContentKind.QUIZ_OPEN.value)
class QuizOpenRenderer:
    def render(self, item: ContentItem) -> RenderedPost:
        quiz = item.payload
        if not isinstance(quiz, QuizOpen):
            raise ValueError(f"{item.slug}: quiz_open без QuizOpen payload")
        lines = [
            f"❓ <b>{escape(quiz.question)}</b>",
            "",
            "Жауабыңызды комментарийге жазыңыз 💬",
            "Бот жауапты қабылдап, басқалар көрмес үшін жасырып қояды.",
            _CLOSES_NOTE,
        ]
        return RenderedPost(head=frame(item, "\n".join(lines), _limit(item)))
