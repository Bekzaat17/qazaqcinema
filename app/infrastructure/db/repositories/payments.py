"""Pg-адаптеры заявок на оплату и очереди доставки видео."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.delivery import VideoDelivery
from app.domain.entities.enums import PaymentMethod, PaymentStatus
from app.domain.entities.subscription import PaymentRequest
from app.infrastructure.db.models import PaymentRequestModel, VideoDeliveryModel


def _payment_to_domain(model: PaymentRequestModel) -> PaymentRequest:
    return PaymentRequest(
        id=model.id,
        user_id=model.user_id,
        tariff=model.tariff,
        method=PaymentMethod(model.method),
        status=PaymentStatus(model.status),
        proof_file_id=model.proof_file_id,
        external_charge_id=model.external_charge_id,
        created_at=model.created_at,
        reviewed_at=model.reviewed_at,
    )


def _delivery_to_domain(model: VideoDeliveryModel) -> VideoDelivery:
    return VideoDelivery(
        chat_id=model.chat_id,
        message_id=model.message_id,
        id=model.id,
        attempts=model.attempts,
    )


class PgPaymentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, request: PaymentRequest) -> PaymentRequest:
        model = PaymentRequestModel(
            user_id=request.user_id,
            tariff=request.tariff,
            method=request.method.value,
            status=request.status.value,
            proof_file_id=request.proof_file_id,
            external_charge_id=request.external_charge_id,
        )
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)
        return _payment_to_domain(model)

    async def get(self, request_id: int) -> PaymentRequest | None:
        model = await self._session.get(PaymentRequestModel, request_id)
        return _payment_to_domain(model) if model else None

    async def set_status(
        self, request_id: int, status: PaymentStatus, reviewed_at: datetime
    ) -> PaymentRequest | None:
        model = await self._session.get(PaymentRequestModel, request_id)
        if model is None:
            return None
        model.status = status.value
        model.reviewed_at = reviewed_at
        await self._session.commit()
        await self._session.refresh(model)
        return _payment_to_domain(model)


class PgVideoDeliveryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, user_id: int, chat_id: int, message_id: int) -> None:
        self._session.add(
            VideoDeliveryModel(user_id=user_id, chat_id=chat_id, message_id=message_id)
        )
        await self._session.commit()

    async def list_for_user(self, user_id: int) -> list[VideoDelivery]:
        stmt = select(VideoDeliveryModel).where(VideoDeliveryModel.user_id == user_id)
        result = await self._session.scalars(stmt)
        return [_delivery_to_domain(m) for m in result]

    async def list_due(
        self, older_than: datetime, now: datetime, limit: int
    ) -> list[VideoDelivery]:
        # next_attempt_at IS NULL — строку ещё не пробовали (обычный случай).
        # ORDER BY id — стабильный порядок; разобранная строка либо удаляется, либо
        # получает срок в будущем, поэтому следующий запрос отдаёт другие строки.
        stmt = (
            select(VideoDeliveryModel)
            .where(
                VideoDeliveryModel.created_at < older_than,
                or_(
                    VideoDeliveryModel.next_attempt_at.is_(None),
                    VideoDeliveryModel.next_attempt_at <= now,
                ),
            )
            .order_by(VideoDeliveryModel.id)
            .limit(limit)
        )
        result = await self._session.scalars(stmt)
        return [_delivery_to_domain(m) for m in result]

    async def delete_many(self, ids: list[int]) -> None:
        if not ids:
            return
        await self._session.execute(
            delete(VideoDeliveryModel).where(VideoDeliveryModel.id.in_(ids))
        )
        await self._session.commit()

    async def reschedule(self, ids: list[int], next_attempt_at: datetime) -> None:
        if not ids:
            return
        await self._session.execute(
            update(VideoDeliveryModel)
            .where(VideoDeliveryModel.id.in_(ids))
            .values(
                attempts=VideoDeliveryModel.attempts + 1,
                next_attempt_at=next_attempt_at,
            )
        )
        await self._session.commit()
