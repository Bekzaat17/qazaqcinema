"""Границы Telegram: старые кнопки используют сегодня, личка не запускает игру."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta
from importlib.util import find_spec
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

_NOW = datetime(2026, 11, 13, 9, tzinfo=UTC)
_TELEGRAM_AVAILABLE = find_spec("aiogram") is not None and find_spec("dishka") is not None


def _config() -> SimpleNamespace:
    return SimpleNamespace(bot=SimpleNamespace(
        public_channel_id=-100123, discussion_group_id=-100456,
    ))


def _dependencies(config: object, riddles: object, group: object = None) -> SimpleNamespace:
    from app.application.ports.discussion import DiscussionGroup
    from app.application.services.daily_riddle_service import DailyRiddleService
    from app.config.settings import AppConfig

    values = {AppConfig: config, DailyRiddleService: riddles, DiscussionGroup: group}

    async def get(dependency: type[object], component: str = "") -> object:
        return values[dependency]

    return SimpleNamespace(get=get)


@unittest.skipUnless(_TELEGRAM_AVAILABLE, "Нужны зависимости aiogram и dishka")
class RiddleHandlerTests(unittest.IsolatedAsyncioTestCase):
    async def test_old_and_new_buttons_call_current_day_and_remain_callbacks(self) -> None:
        from aiogram.types import Chat, InlineKeyboardButton, InlineKeyboardMarkup, Message
        from app.application.services.daily_riddle_service import RiddleReply
        from app.bot.handlers.riddles import riddle_button
        from app.domain.channel.content.daily_riddle import DAILY_RIDDLE_CALLBACK

        service = SimpleNamespace(request=AsyncMock(return_value=RiddleReply("Бүгінгі сұрақ", 555)))
        for age in (0, 100):
            markup = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="Жұмбақ", callback_data=DAILY_RIDDLE_CALLBACK),
            ]])
            message = Message(
                message_id=age + 1, date=_NOW - timedelta(days=age),
                chat=Chat(id=-100123, type="channel"), text="Фильм", reply_markup=markup,
            )
            callback = SimpleNamespace(message=message, answer=AsyncMock())
            with patch("app.bot.handlers.riddles.datetime") as clock:
                clock.now.return_value = _NOW
                await riddle_button(callback, dishka_container=_dependencies(_config(), service))
            self.assertEqual(service.request.await_args.args, (_NOW,))
            self.assertEqual(message.reply_markup, markup)
            callback.answer.assert_awaited_once()

    async def test_commands_and_callbacks_in_private_chat_do_not_start_game(self) -> None:
        from aiogram.types import Chat, Message
        from app.bot.handlers.riddles import answer_command, riddle_button, riddle_command

        message = Message(message_id=1, date=_NOW, chat=Chat(id=42, type="private"))
        service, group = AsyncMock(), AsyncMock()
        await riddle_command(message, dishka_container=_dependencies(_config(), service))
        await answer_command(
            message, SimpleNamespace(args="Кірпі"),
            dishka_container=_dependencies(_config(), service, group),
        )
        await riddle_button(
            SimpleNamespace(message=message, answer=AsyncMock()),
            dishka_container=_dependencies(_config(), service),
        )
        service.request.assert_not_awaited()
        service.answer.assert_not_awaited()
        service.result.assert_not_awaited()
        group.delete_message.assert_not_awaited()

    async def test_movie_keyboard_keeps_watch_link_and_dynamic_riddle_button(self) -> None:
        from app.application.ports.channel import ChannelPost
        from app.domain.channel.content.daily_riddle import DAILY_RIDDLE_CALLBACK
        from app.domain.channel.content.render.base import CallbackButton
        from app.infrastructure.telegram.channel import _keyboard

        markup = _keyboard(ChannelPost(
            text="Фильм", button_text="Тегін көру", button_url="https://t.me/example?start=m_1",
            choices=(CallbackButton("Күннің жұмбағы", DAILY_RIDDLE_CALLBACK),),
        ))
        assert markup is not None
        self.assertEqual(len(markup.inline_keyboard), 2)
        self.assertEqual(markup.inline_keyboard[0][0].url, "https://t.me/example?start=m_1")
        self.assertEqual(markup.inline_keyboard[1][0].callback_data, DAILY_RIDDLE_CALLBACK)
        self.assertIsNone(markup.inline_keyboard[1][0].url)
