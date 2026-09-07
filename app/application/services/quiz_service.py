"""Квиз: приём ответов (кнопки и комментарии), привязка ветки комментариев, разбор.

Две формы — два входа, один журнал ответов:
- `answer_choice` — нажатие кнопки под постом (callback). Ответ = индекс варианта.
- `answer_comment` — сообщение в ветке обсуждения поста `quiz_open`. Ответ = текст;
  после записи хендлер удаляет комментарий и подтверждает приём — спойлеров в ветке нет.

Проверка — `AnswerChecker` по форме (Strategy, `domain/.../answers/checkers`). Первый ответ
человека — единственный (UNIQUE в БД). Админы не участвуют в статистике, как и в
аналитике (`AdminBlindEventRepository`): их ответы принимаются, но не записываются.

`publish_due_results` — раз в час: у квизов с истёкшим `quiz_closes_at` снимаем кнопки и
публикуем разбор ответом на пост.
"""

from __future__ import annotations

import logging
from collections.abc import Collection
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.application.ports.channel import ChannelPost, ChannelPublisher
from app.application.ports.content import (
    ContentRepository,
    PostLogEntry,
    PostLogRepository,
    QuizAnswerRepository,
)
from app.domain.channel.content.answers.checkers import (
    AnswerChecker,
    ChoiceChecker,
    OpenChecker,
)
from app.domain.channel.content.answers.result import (
    QuizStats,
    correct_answer_text,
    render_result,
)
from app.domain.channel.content.item import ContentItem, QuizChoice, QuizOpen
from app.domain.channel.content.kinds import ContentKind

logger = logging.getLogger(__name__)

PODIUM_SIZE = 3


class Verdict(StrEnum):
    CORRECT = "correct"
    WRONG = "wrong"
    ALREADY_ANSWERED = "already"   # второй ответ того же человека — не считаем
    CLOSED = "closed"              # время вышло
    NOT_A_QUIZ = "not_a_quiz"      # кнопка/ветка не от квиза (или пост не в журнале)


@dataclass(frozen=True, slots=True)
class Outcome:
    verdict: Verdict
    correct_answer: str = ""   # для всплывашки «қате, жауабы — …» и подтверждения


@dataclass(frozen=True, slots=True)
class Answerer:
    user_id: int
    first_name: str


def _checker(item: ContentItem) -> AnswerChecker | None:
    match item.payload:
        case QuizChoice() as quiz:
            return ChoiceChecker(quiz)
        case QuizOpen() as quiz:
            return OpenChecker(quiz)
        case _:
            return None


class QuizService:
    def __init__(
        self,
        items: ContentRepository,
        log: PostLogRepository,
        answers: QuizAnswerRepository,
        publisher: ChannelPublisher,
        admin_ids: Collection[int],
    ) -> None:
        self._items = items
        self._log = log
        self._answers = answers
        self._publisher = publisher
        self._admin_ids = set(admin_ids)

    async def answer_choice(
        self, channel_message_id: int, item_id: int, index: int, who: Answerer, now: datetime
    ) -> Outcome:
        """Нажатие кнопки под постом в канале."""
        post = await self._log.get_by_channel_message(channel_message_id)
        if post is None or post.item_id != item_id or post.kind is not ContentKind.QUIZ_CHOICE:
            return Outcome(Verdict.NOT_A_QUIZ)
        return await self._record(post, who, str(index), now)

    async def answer_comment(
        self, thread_message_id: int, who: Answerer, text: str, now: datetime
    ) -> Outcome:
        """Сообщение в ветке комментариев. `NOT_A_QUIZ` — обычный комментарий, трогать нельзя."""
        post = await self._log.get_by_group_message(thread_message_id)
        if post is None or post.kind is not ContentKind.QUIZ_OPEN:
            return Outcome(Verdict.NOT_A_QUIZ)
        return await self._record(post, who, text, now)

    async def _record(
        self, post: PostLogEntry, who: Answerer, answer: str, now: datetime
    ) -> Outcome:
        item = await self._items.get(post.item_id)
        checker = _checker(item) if item else None
        if item is None or checker is None:
            return Outcome(Verdict.NOT_A_QUIZ)
        expected = correct_answer_text(item)
        if post.quiz_closes_at is not None and now >= post.quiz_closes_at:
            return Outcome(Verdict.CLOSED, expected)
        correct = checker.is_correct(answer)
        if who.user_id in self._admin_ids:
            # Админ проверяет квиз — ответ показываем, в статистику не пишем.
            return Outcome(Verdict.CORRECT if correct else Verdict.WRONG, expected)
        assert post.id is not None
        recorded = await self._answers.add_first(
            post.id, who.user_id, who.first_name[:128], answer[:255], correct, now
        )
        if not recorded:
            return Outcome(Verdict.ALREADY_ANSWERED, expected)
        return Outcome(Verdict.CORRECT if correct else Verdict.WRONG, expected)

    async def bind_forward(self, channel_message_id: int, group_message_id: int) -> bool:
        """Авто-форвард поста в группу: запомнить id, по нему узнаются комментарии."""
        return await self._log.bind_group_message(channel_message_id, group_message_id)

    async def publish_due_results(self, now: datetime) -> int:
        """Опубликовать разборы всех закрывшихся квизов. Вернуть сколько ушло."""
        published = 0
        for post in await self._log.list_due_results(now):
            item = await self._items.get(post.item_id)
            if item is None or post.id is None:
                continue
            row = await self._answers.stats(post.id, PODIUM_SIZE)
            stats = QuizStats(row.total, row.correct, row.first_correct)
            await self._publisher.remove_buttons(post.channel_message_id)
            sent = await self._publisher.publish(
                ChannelPost(
                    text=render_result(item, stats),
                    reply_to_message_id=post.channel_message_id,
                )
            )
            if sent is None:
                # Канал недоступен — попробуем следующим часом: запись не помечаем.
                logger.warning("Разбор квиза %s не опубликован", post.slot_key)
                continue
            await self._log.mark_result_posted(post.id, now)
            published += 1
        return published
