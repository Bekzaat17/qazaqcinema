"""Игровая сводка и предложение для вовлечения аудитории."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from html import escape

from app.domain.catalog.daily import TZ


@dataclass(frozen=True, slots=True)
class GameWinner:
    name: str
    wins: int


@dataclass(frozen=True, slots=True)
class GameReport:
    since: datetime
    until: datetime
    active_players: int = 0
    rooms_created: int = 0
    games_started: int = 0
    games_finished: int = 0
    finished_players: int = 0
    quest_players: int = 0
    quests_started: int = 0
    quests_finished: int = 0
    players_total: int = 0
    winners: tuple[GameWinner, ...] = ()


def engagement_suggestion(report: GameReport) -> str:
    # Завершения могут относиться к вчерашним стартам: это не когортная конверсия.
    if report.games_started > report.games_finished and report.games_started >= 3:
        return (
            "💡 <b>Идея для канала: узнать, что мешает доиграть</b>\n"
            "Дайын сауалнама: «Ойынды соңына дейін ойнауға не кедергі?»\n"
            "• Уақыт жетпейді\n• Ережесін түсінбедім\n"
            "• Бірге ойнайтын адам жоқ\n• Техникалық мәселе бар\n"
            "Талқылауда нақты қай жерде қиын болғанын сұрауға болады."
        )
    if report.games_finished:
        return (
            "💡 <b>Идея для канала: собрать отзывы</b>\n"
            "Дайын мәтін: «QazaqPlay ойнап көрдіңіз бе? 🎲 "
            "Ойынға 1–5 баға беріңіз. Не ұнады, нені өзгерткіміз келеді? "
            "Пікіріңізді осы жазбаның астына қалдырыңыз 👇»"
        )
    return (
        "💡 <b>Идея для канала: пригласить попробовать игру</b>\n"
        "Дайын сауалнама: «QazaqPlay ойнап көрдіңіз бе? 🎲»\n"
        "• Иә, ойнадым\n• Қалай бастау керегін білмеймін\n"
        "• Бірге ойнауға адам іздеймін\n• Әзірге ойнамадым\n"
        "Келесі жазбада жауаптарға қарай қысқа нұсқаулық не ойынға шақыру беруге болады."
    )


def render_game_report(report: GameReport) -> str:
    start = report.since.astimezone(TZ)
    end = report.until.astimezone(TZ)
    lines = [
        "🎮 <b>QazaqPlay · күнделікті есеп</b>",
        f"{start:%d.%m %H:%M} – {end:%d.%m.%Y %H:%M} (Алматы)",
        "",
        "🎲 <b>Үстел ойыны · соңғы 24 сағат</b>",
        f"👥 Белсенді ойыншы: {report.active_players}",
        f"🚪 Құрылған бөлме: {report.rooms_created}",
        f"▶️ Басталған партия: {report.games_started}",
        f"🏁 Аяқталған партия: {report.games_finished}",
        f"🙋 Аяқталған партияларға қатысқан: {report.finished_players}",
        "",
        f"🧩 <b>Квесттер · {end:%d.%m}, 00:00–{end:%H:%M}</b>",
        f"👥 Қатысушы: {report.quest_players}",
        f"▶️ Басталған: {report.quests_started} · ✅ Аяқталған: {report.quests_finished}",
        f"🌱 Ауыл/квест ойыншылары, барлығы: {report.players_total}",
    ]
    if report.winners:
        lines += ["", "🏆 <b>Тәуліктің жеңімпаздары</b>"]
        lines += [
            f"{i}. {escape(w.name[:24])} — {w.wins} жеңіс"
            for i, w in enumerate(report.winners, 1)
        ]
    lines += [
        "",
        "ℹ️ Админдердің әрекеттері есептелмейді. Боттар ойыншы санына кірмейді.",
        "Белсенділік пен старт есебі жаңарту орнатылған сәттен жиналады.",
        "Басталған және аяқталған партиялар әртүрлі болуы мүмкін; бұл конверсия емес.",
        "",
        engagement_suggestion(report),
    ]
    return "\n".join(lines)
