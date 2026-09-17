"""Ответ на личное сообщение, которое некому обработать — чаще всего это чек мимо Mini App.

Чек, присланный в чат с ботом, заявкой на оплату НЕ становится: `payment_requests` заводит
только Mini App, и в модерации админ такой чек не увидит. Человек при этом уверен, что
оплатил, и ждёт — а бот до сих пор молчал в ответ буквально: хендлера под фото в личке не
было вовсе. Поэтому ответ шаблонный, но с обеими дорогами: куда нести чек и как написать
админу (обе — внутри Mini App, снаружи их просто нет).

Роутер подключается ПОСЛЕДНИМ (`bot/setup.py`) и отвечает только там, где больше некому:
личка (в группе обсуждений свои хендлеры — см. `handlers/quiz`) и никакого активного FSM
(`StateFilter(None)`) — иначе он перехватывал бы шаги визарда `/add` и рассылки.

Подписи в тексте — РОВНО те, что человек видит в Mini App («Жазылу», «Чекті жүктеу»,
«Қолдау қызметіне жазу»): инструкция «нажми то, чего на экране нет» хуже молчания.
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.filters import StateFilter
from aiogram.types import Message
from dishka import FromDishka
from dishka.integrations.aiogram import inject

from app.bot.keyboards.common import webapp_keyboard
from app.config.settings import AppConfig

router = Router(name="fallback")
router.message.filter(F.chat.type == ChatType.PRIVATE, StateFilter(None))

# Чек прислали в чат: главное — сказать, что он не потерялся, а просто не туда, и что
# делать дальше. Без «қате»/«болмайды» в первой строке: человек уже заплатил.
_RECEIPT = (
    "Сәлем! 😊\n\n"
    "Чекті осы чатқа жібердіңіз — бот оны қабылдай алмайды. "
    "Чек қосымша арқылы жүктелгенде ғана тексеруге түседі."
)

# Любое другое сообщение (вопрос, «сәлем», неизвестная команда): человек ждёт ответа
# от живого админа и не знает, что в этом чате его никто не прочитает.
_MESSAGE = (
    "Сәлем! 😊\n\n"
    "Бұл чатта бот тек хабарландыру жібереді — мұнда жазғаныңызды әкімшілер көрмейді."
)

_HOW_TO = (
    "🧾 Чекті жүктеу: қосымшаны ашыңыз → «Жазылу» → «Kaspi арқылы төлеу» → "
    "«Чекті жүктеу» (сурет не PDF). Төлеміңізді 10–15 минут ішінде тексереміз.\n\n"
    "📝 Әкімшіге жазу: қосымшаны ашыңыз → жоғарыдан 👤 профиль → "
    "«Қолдау қызметіне жазу». Әкімшілер сол жерден жауап береді.\n\n"
    "Қосымшаны төмендегі батырмамен ашасыз 👇"
)


def hint_text(*, has_attachment: bool) -> str:
    """Шаблон ответа: вложение считаем чеком, остальное — сообщением админу."""
    return f"{_RECEIPT if has_attachment else _MESSAGE}\n\n{_HOW_TO}"


@router.message()
@inject
async def handle_unrouted(message: Message, config: FromDishka[AppConfig]) -> None:
    url = config.bot.webapp_url
    await message.answer(
        hint_text(has_attachment=bool(message.photo or message.document)),
        # Кнопка ведёт ровно туда, куда зовёт текст. Web App без URL Telegram не примет —
        # при незаданном PUBLIC_ORIGIN отвечаем текстом, а не роняем каждый апдейт.
        reply_markup=webapp_keyboard(url) if url else None,
    )
