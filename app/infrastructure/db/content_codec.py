"""JSONB ↔ типизированный payload элемента контента (граница хранения).

Домен работает с dataclass'ами (`QuizChoice` и т. д.), БД хранит словарь. Разбор
здесь — чтобы битый payload (сидер залил не то) падал на маппинге с понятным
сообщением, а не в рендерере посреди публикации.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, cast

from app.domain.channel.content.item import Payload, QuizChoice, QuizOpen, Term, TermList
from app.domain.channel.content.kinds import ContentKind


def payload_to_json(payload: Payload) -> dict[str, Any] | None:
    if payload is None:
        return None
    return asdict(payload)


def payload_from_json(kind: ContentKind, data: dict[str, Any] | None) -> Payload:
    if data is None:
        return None
    match kind:
        case ContentKind.QUIZ_CHOICE:
            return QuizChoice(
                question=str(data["question"]),
                options=tuple(str(o) for o in data["options"]),
                answer=int(data["answer"]),
            )
        case ContentKind.QUIZ_OPEN:
            return QuizOpen(
                question=str(data["question"]),
                accept=tuple(str(a) for a in data["accept"]),
            )
        case ContentKind.TERM_LIST:
            items = cast(list[dict[str, Any]], data["items"])
            return TermList(
                items=tuple(Term(str(t["term"]), str(t["meaning"])) for t in items),
                note=str(data.get("note", "")),
            )
        case _:
            # У longread/saying payload'а нет; непустой словарь — ошибка сидера, но
            # ронять публикацию из-за лишнего поля незачем.
            return None
