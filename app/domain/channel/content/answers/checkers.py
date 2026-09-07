"""Чекеры ответов — Strategy по форме квиза.

`quiz_choice`: ответ приходит НОМЕРОМ варианта (нажатая кнопка) — сравнение тривиально,
но живёт здесь же, чтобы у сервиса был один интерфейс на обе формы.

`quiz_open`: свободный текст из комментария. Правильно, если после `fold` он совпал с одним
из `accept` целиком, либо совпал с допуском опечатки, либо ответ содержится в тексте как
целые слова («менің ойымша, түйе» → «түйе»). Допуск — 1 опечатка на каждое слово ответа
длиной ≥ 5 букв, не больше 2: «кулын» и «кулин» — одно и то же, а «қой» и «той» — нет.
"""

from __future__ import annotations

from typing import Protocol

from app.domain.channel.content.answers.normalize import fold, levenshtein
from app.domain.channel.content.item import QuizChoice, QuizOpen

_TYPO_WORD_MIN_LEN = 5
_TYPO_MAX = 2


class AnswerChecker(Protocol):
    def is_correct(self, answer: str) -> bool: ...


class ChoiceChecker:
    def __init__(self, payload: QuizChoice) -> None:
        self._payload = payload

    def is_correct(self, answer: str) -> bool:
        """`answer` — индекс варианта строкой (из callback_data). Не число → неверно."""
        return answer.strip().isdigit() and int(answer) == self._payload.answer


class OpenChecker:
    def __init__(self, payload: QuizOpen) -> None:
        self._accept = [fold(a) for a in payload.accept if fold(a)]

    def is_correct(self, answer: str) -> bool:
        given = fold(answer)
        if not given:
            return False
        if given in self._accept:
            return True
        words = given.split()
        for accepted in self._accept:
            tolerance = min(
                _TYPO_MAX,
                sum(1 for w in accepted.split() if len(w) >= _TYPO_WORD_MIN_LEN),
            )
            if tolerance and levenshtein(given, accepted) <= tolerance:
                return True
            # Ответ внутри фразы: окно из стольких же слов, сколько в допустимом варианте.
            size = len(accepted.split())
            for start in range(len(words) - size + 1):
                window = " ".join(words[start : start + size])
                if window == accepted or (tolerance and levenshtein(window, accepted) <= tolerance):
                    return True
        return False
