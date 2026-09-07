"""Разрез длинного текста под лимит Telegram — по абзацам, никогда посреди предложения.

Қара сөз длиннее 4096 символов уходит несколькими сообщениями ПОДРЯД (не по дням).
Граница — пустая строка между абзацами; абзац, который сам не влезает, режется по
концу предложения. Только предложение длиннее лимита (в живых текстах не встречается)
режется по пробелу — это страховка, а не режим работы.
"""

from __future__ import annotations

import re

_SENTENCE_END = re.compile(r"(?<=[.!?…»])\s+")


def split_text(text: str, limit: int) -> list[str]:
    """Куски ≤ `limit`, каждый — целые абзацы/предложения. Пустой текст → []."""
    text = text.strip()
    if not text:
        return []
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    current = ""
    for paragraph in re.split(r"\n\s*\n", text):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        for piece in _fit_paragraph(paragraph, limit):
            candidate = f"{current}\n\n{piece}" if current else piece
            if len(candidate) <= limit:
                current = candidate
            else:
                if current:
                    chunks.append(current)
                current = piece
    if current:
        chunks.append(current)
    return chunks


def _fit_paragraph(paragraph: str, limit: int) -> list[str]:
    """Абзац целиком, либо его предложения, склеенные до лимита."""
    if len(paragraph) <= limit:
        return [paragraph]
    pieces: list[str] = []
    current = ""
    for sentence in _SENTENCE_END.split(paragraph):
        for part in _fit_sentence(sentence, limit):
            candidate = f"{current} {part}" if current else part
            if len(candidate) <= limit:
                current = candidate
            else:
                if current:
                    pieces.append(current)
                current = part
    if current:
        pieces.append(current)
    return pieces


def _fit_sentence(sentence: str, limit: int) -> list[str]:
    """Страховка: предложение длиннее лимита — режем по последнему пробелу перед лимитом."""
    parts: list[str] = []
    while len(sentence) > limit:
        cut = sentence.rfind(" ", 0, limit)
        if cut <= 0:
            cut = limit
        parts.append(sentence[:cut].rstrip())
        sentence = sentence[cut:].lstrip()
    if sentence:
        parts.append(sentence)
    return parts
