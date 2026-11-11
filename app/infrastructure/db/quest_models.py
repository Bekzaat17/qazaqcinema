from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


class QuestPlayerModel(Base):
    __tablename__ = "quest_players"

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.telegram_id"), primary_key=True
    )
    total_xp: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    wood: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    stone: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    completed_quests: Mapped[list[str]] = mapped_column(
        ARRAY(String(32)), server_default=text("'{}'")
    )
    buildings: Mapped[dict[str, int]] = mapped_column(JSONB, server_default=text("'{}'"))

    __table_args__ = (
        Index("ix_quest_players_ranking", text("total_xp DESC"), "user_id"),
        CheckConstraint("wood >= 0 AND stone >= 0 AND total_xp >= 0", name="ck_quest_wallet"),
    )


class QuestRunModel(Base):
    __tablename__ = "quest_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"))
    quest_id: Mapped[str] = mapped_column(String(32))
    day: Mapped[date] = mapped_column(Date)
    question_ids: Mapped[list[str]] = mapped_column(ARRAY(String(32)))
    question_index: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    tried: Mapped[list[str]] = mapped_column(ARRAY(String(64)), server_default=text("'{}'"))
    points: Mapped[int] = mapped_column(Integer, server_default=text("0"))

    __table_args__ = (
        UniqueConstraint("user_id", "quest_id", "day", name="uq_quest_run_daily"),
        Index("ix_quest_runs_user_day", "user_id", "day"),
        CheckConstraint("points BETWEEN 0 AND 100", name="ck_quest_run_points"),
    )


class QuestWeeklyScoreModel(Base):
    __tablename__ = "quest_weekly_scores"

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.telegram_id"), primary_key=True
    )
    week: Mapped[date] = mapped_column(Date, primary_key=True)
    points: Mapped[int] = mapped_column(Integer)
    __table_args__ = (Index("ix_quest_weekly_ranking", "week", text("points DESC"), "user_id"),)


class QuestChannelPostModel(Base):
    __tablename__ = "quest_channel_posts"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    reserved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class BoardRoomModel(Base):
    __tablename__ = "board_rooms"

    code: Mapped[str] = mapped_column(String(10), primary_key=True)
    state: Mapped[dict[str, object]] = mapped_column(JSONB)
    members: Mapped[dict[str, str]] = mapped_column(JSONB)
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BoardAwardModel(Base):
    __tablename__ = "board_awards"

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.telegram_id", ondelete="CASCADE"), primary_key=True
    )
    scenario_id: Mapped[str] = mapped_column(String(48), primary_key=True)


class BoardResultModel(Base):
    __tablename__ = "board_results"

    code: Mapped[str] = mapped_column(String(10), ForeignKey("board_rooms.code"), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.telegram_id", ondelete="CASCADE"), primary_key=True
    )
    name: Mapped[str] = mapped_column(String(24))
    scenario_id: Mapped[str] = mapped_column(String(48))
    board_id: Mapped[str] = mapped_column(String(48))
    rounds: Mapped[int] = mapped_column(Integer)
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    winner_name: Mapped[str] = mapped_column(String(24))
    player_count: Mapped[int] = mapped_column(Integer)
    capital: Mapped[int] = mapped_column(BigInteger)
    won: Mapped[bool] = mapped_column(Boolean)

    __table_args__ = (Index("ix_board_results_history", "user_id", text("finished_at DESC")),)
