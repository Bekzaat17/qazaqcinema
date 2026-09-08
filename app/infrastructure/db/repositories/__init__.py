"""Pg-реализации портов репозиториев (адаптеры). Мапят ORM ↔ домен.

Разложены по агрегатам (`catalog`, `users`, `payments`, `analytics`), но импортируются
из имени пакета: состав модулей — внутреннее дело адаптеров, а DI и тесты знают только
классы.

Запись (add/upsert/set_status) коммитит сессию сама — для текущих сценариев
(один запрос = одна транзакция) этого достаточно; при необходимости перейдём на
явный Unit of Work.
"""

from __future__ import annotations

from app.infrastructure.db.repositories.analytics import (
    PgDailyReportRepository,
    PgMilestoneRepository,
    PgSearchQueryRepository,
    PgUserEventRepository,
)
from app.infrastructure.db.repositories.catalog import (
    PgFavoriteRepository,
    PgMovieRepository,
    PgSeasonRepository,
    PgSeriesRepository,
)
from app.infrastructure.db.repositories.payments import (
    PgPaymentRepository,
    PgVideoDeliveryRepository,
)
from app.infrastructure.db.repositories.users import PgUserRepository

__all__ = [
    "PgDailyReportRepository",
    "PgFavoriteRepository",
    "PgMilestoneRepository",
    "PgMovieRepository",
    "PgPaymentRepository",
    "PgSearchQueryRepository",
    "PgSeasonRepository",
    "PgSeriesRepository",
    "PgUserEventRepository",
    "PgUserRepository",
    "PgVideoDeliveryRepository",
]
