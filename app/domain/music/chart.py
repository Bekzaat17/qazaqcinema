"""Еженедельный пост в канал: хиты недели и треки, которые слушатели ищут."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from html import escape

CHART_SIZE = 10
WANTED_SIZE = 5
_MEDALS = ("🥇", "🥈", "🥉")


@dataclass(frozen=True, slots=True)
class ChartEntry:
    title: str
    performer: str
    plays: int


@dataclass(frozen=True, slots=True)
class WeeklyChart:
    week: date
    top: tuple[ChartEntry, ...]
    new_tracks: int
    wanted: tuple[str, ...]


def has_content(chart: WeeklyChart) -> bool:
    """Пустой хит-парад в канал не уходит: «топ из нуля песен» выглядит как поломка."""
    return bool(chart.top)


def render_chart(chart: WeeklyChart) -> str:
    lines = ["🎧 <b>Аптаның хиттері · QazaqMusic</b>", ""]
    for index, entry in enumerate(chart.top[:CHART_SIZE], start=1):
        marker = _MEDALS[index - 1] if index <= len(_MEDALS) else f"{index}."
        lines.append(
            f"{marker} {escape(entry.performer)} — <b>{escape(entry.title)}</b>"
        )
    if chart.new_tracks:
        lines += ["", f"🆕 Осы аптада тыңдаушылар {chart.new_tracks} жаңа ән қосты."]
    if chart.wanted:
        lines += ["", "🔎 <b>Іздеп жүр, бірақ әлі жоқ:</b>"]
        lines += [f"• {escape(query)}" for query in chart.wanted[:WANTED_SIZE]]
        lines.append("Сізде бар ма? Әнді ботқа жіберіңіз — бәрі тыңдай алады 🙌")
    lines += ["", "Тыңдау, плейлист жинау және досқа бөлісу — төмендегі батырма 👇"]
    return "\n".join(lines)
