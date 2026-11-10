from __future__ import annotations

from datetime import date, timedelta
from html import escape

from app.domain.quest.game import RankEntry


def render_ranking(entries: tuple[RankEntry, ...], week: date, *, final: bool) -> str:
    title = "Апта жеңімпаздары" if final else "Апталық рейтинг"
    end = week + timedelta(days=6)
    lines = [f"🏆 <b>QazaqQuest · {title}</b>", f"{week:%d.%m} — {end:%d.%m.%Y}", ""]
    for entry in entries:
        medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(entry.rank, f"{entry.rank}.")
        lines.append(f"{medal} {escape(entry.name)} — <b>{entry.points}</b> ұпай")
    lines.extend(
        [
            "",
            "Ауылыңды дамыт. Қазақша үйрен. Рухтарды оят!",
            "Ұпай тең болса, тұрақты ойыншы реті қолданылады.",
        ]
    )
    if not final:
        lines.append("Рейтинг сағат сайын жаңарады. Жаңа апта: дүйсенбі, 00:00 (Алматы).")
    return "\n".join(lines)
