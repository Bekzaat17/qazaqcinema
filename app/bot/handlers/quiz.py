"""Квиз в публичном канале: кнопки под постом и комментарии в группе обсуждений.

Тонкая презентация: разобрать апдейт → `QuizService` → показать результат. Тексты
всплывашек и подтверждений — здесь (это UI), правила игры — в сервисе.

Комментарии: Telegram авто-форвардит пост канала в привязанную группу
(`is_automatic_forward`, `forward_origin.message_id` = id в канале) — по этому сообщению
запоминаем связку. Любое сообщение в группе с `message_thread_id` — комментарий к посту
с таким id форварда. Для `quiz_open` бот записывает ответ, удаляет комментарий (чтобы не
спойлерить) и отвечает в ветку. Комментарии к остальным постам не трогает.

Тот же авто-форвард Telegram ещё и ЗАКРЕПЛЯЕТ в группе (поведение связки «канал ↔
обсуждение»), поэтому здесь же уборка: открепить пост и убрать служебную строку о
закреплении. Обработчик один на событие — второй с тем же фильтром до апдейта бы просто
не дошёл (aiogram останавливается на первом подошедшем).
"""

from __future__ import annotations

from datetime import UTC, datetime
from html import escape

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message, MessageOriginChannel
from dishka import FromDishka
from dishka.integrations.aiogram import inject

from app.application.ports.discussion import DiscussionGroup
from app.application.services.quiz_service import Answerer, Outcome, QuizService, Verdict
from app.config.settings import AppConfig
from app.domain.channel.content.render.quiz import CALLBACK_PREFIX, parse_callback

router = Router(name="quiz")

_TOASTS: dict[Verdict, str] = {
    Verdict.CORRECT: "✅ Дұрыс! Жарайсыз!",
    Verdict.WRONG: "❌ Қате. Дұрыс жауабы: {answer}",
    Verdict.ALREADY_ANSWERED: "Сіз жауап беріп қойдыңыз 🙂 Бірінші жауап есептеледі.",
    Verdict.CLOSED: "⏳ Уақыт бітті. Дұрыс жауабы: {answer}",
    Verdict.NOT_A_QUIZ: "Бұл сауалнама аяқталған.",
}


def _toast(outcome: Outcome) -> str:
    return _TOASTS[outcome.verdict].format(answer=outcome.correct_answer)


@router.callback_query(F.data.startswith(f"{CALLBACK_PREFIX}:"))
@inject
async def quiz_button(callback: CallbackQuery, quiz: FromDishka[QuizService]) -> None:
    parsed = parse_callback(callback.data or "")
    message = callback.message
    if parsed is None or message is None:
        await callback.answer()
        return
    item_id, index = parsed
    who = Answerer(callback.from_user.id, callback.from_user.first_name)
    outcome = await quiz.answer_choice(
        message.message_id, item_id, index, who, datetime.now(UTC)
    )
    # Всплывашка видна только нажавшему — спойлеров для остальных нет.
    await callback.answer(_toast(outcome), show_alert=outcome.verdict is Verdict.WRONG)


def _in_discussion_group(message: Message, config: AppConfig) -> bool:
    group_id = config.bot.discussion_group_id
    return bool(group_id) and message.chat.id == group_id


@router.message(F.is_automatic_forward.is_(True))
@inject
async def channel_forward(
    message: Message,
    config: FromDishka[AppConfig],
    quiz: FromDishka[QuizService],
    group: FromDishka[DiscussionGroup],
) -> None:
    """Пост канала приехал в группу: связать с веткой комментариев и открепить.

    Закрепление тут не наше — его делает сам Telegram для каждого авто-форварда. Смысла
    в нём нет: посты идут ежедневно, каждый следующий сменяет предыдущий, и «закреплённое»
    в группе значит всего лишь «последнее». А цену человек платит настоящую — шапка чата
    занята и в ленте копятся служебные строки.
    """
    if not _in_discussion_group(message, config):
        return
    origin = message.forward_origin
    if isinstance(origin, MessageOriginChannel):
        await quiz.bind_forward(origin.message_id, message.message_id)
    await group.unpin_message(message.message_id)


@router.message(F.pinned_message)
@inject
async def pin_notice(
    message: Message, config: FromDishka[AppConfig], group: FromDishka[DiscussionGroup]
) -> None:
    """Убрать служебную строку «закрепил сообщение» — но только про авто-форвард.

    Открепление саму строку из ленты не убирает, она остаётся висеть под постом. Чужие
    закрепления (админ закрепил что-то руками) не трогаем: убираем шум, который создали
    не люди.
    """
    pinned = message.pinned_message
    if not _in_discussion_group(message, config) or not isinstance(pinned, Message):
        return
    if pinned.is_automatic_forward:
        await group.delete_message(message.message_id)


@router.message(F.message_thread_id.is_not(None), F.from_user, F.text)
@inject
async def comment(
    message: Message,
    config: FromDishka[AppConfig],
    quiz: FromDishka[QuizService],
    group: FromDishka[DiscussionGroup],
) -> None:
    if not _in_discussion_group(message, config) or message.from_user is None:
        return
    assert message.message_thread_id is not None and message.text is not None
    who = Answerer(message.from_user.id, message.from_user.first_name)
    outcome = await quiz.answer_comment(
        message.message_thread_id, who, message.text, datetime.now(UTC)
    )
    if outcome.verdict is Verdict.NOT_A_QUIZ:
        return  # обычный комментарий под обычным постом — не наше дело
    name = escape(message.from_user.first_name)
    if outcome.verdict is Verdict.CLOSED:
        answer = escape(outcome.correct_answer)
        reply = f"⏳ {name}, жауаптар қабылдау аяқталды. Жауабы: <b>{answer}</b>"
    elif outcome.verdict is Verdict.ALREADY_ANSWERED:
        reply = f"{name}, сіз жауап беріп қойдыңыз 🙂 Бірінші жауап есептеледі."
    else:
        reply = f"✅ {name}, жауабыңыз қабылданды! Талдау — 21:00-де."
    # Сначала убираем ответ (спойлер), потом подтверждаем — чтобы ветка не показывала
    # чужой ответ ни секунды дольше нужного.
    await group.delete_message(message.message_id)
    await group.reply_in_thread(message.message_thread_id, reply)
