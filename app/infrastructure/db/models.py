"""ORM-модели. Намеренно отделены от доменных сущностей (мапятся в репозиториях).

Статус/способ/категория хранятся как VARCHAR (а не PG-ENUM): добавить новое
значение можно без миграции типа. telegram_id и user_id — BIGINT без автоинкремента
(это Telegram ID, не суррогатный ключ).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.entities.enums import PaymentStatus, UserStatus
from app.infrastructure.db.base import Base


class UserModel(Base):
    __tablename__ = "users"

    telegram_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default=UserStatus.NEW.value)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    selected_tariff: Mapped[str | None] = mapped_column(String(20), nullable=True)


class MovieModel(Base):
    __tablename__ = "movies"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(32), index=True)
    poster_url: Mapped[str] = mapped_column(Text)
    telegram_file_id: Mapped[str] = mapped_column(Text)
    year: Mapped[int | None] = mapped_column(nullable=True)
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)


class PaymentRequestModel(Base):
    __tablename__ = "payment_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.telegram_id"), index=True
    )
    tariff: Mapped[str] = mapped_column(String(20))
    method: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default=PaymentStatus.PENDING.value, index=True)
    proof_file_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    external_charge_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
