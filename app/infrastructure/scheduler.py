"""Фоновый планировщик (apscheduler). Семь задач — все через REQUEST-scope dishka.

1. `expire_due` (15 мин) — гасит просроченные подписки: ACTIVE → EXPIRED + уведомление +
   чистка выданных видео. Доступ к контенту от этого джоба НЕ зависит (`has_active_access`
   считает `expires_at` в реальном времени на каждом запросе) — джоб лишь приводит статус
   и чат в порядок.
2. `purge_stale_videos` (1 час) — сносит выданные видео старше 40 ч. Главный механизм
   защиты контента: Telegram не даёт боту удалить сообщение старше 48 ч, поэтому выдачи
   надо забирать ЗАРАНЕЕ, не дожидаясь конца подписки (см. `VideoRetentionService`).

3. `daily_report` (раз в сутки, 22:00 по Алматы) — короткая сводка админам в личку:
   сколько всего людей, сколько активных подписок, сколько заходов/просмотров за день.
   Окно отчёта — скользящее (см. `domain/analytics/report.day_window`), поэтому час
   можно двигать свободно: дыр в сутках это не создаёт. Тем же вызовом `AnalyticsService.
   daily_report` пишет снимок в `daily_reports` (upsert по дню) — история накапливается
   сама, отдельного джоба на запись нет.

4. `weekly_report` (раз в неделю, воскресенье 22:10 по Алматы) — дайджест за 7 суток
   с сравнением к предыдущим 7 (в %), нормировкой на размер каталога и вехами роста
   за период (`domain/analytics/weekly_report`). Считает НЕ `user_events` заново, а
   агрегирует уже сохранённые снимки `daily_reports` — 10-минутный сдвиг от
   `daily_report` гарантирует, что сегодняшний снимок к этому моменту уже записан.

5. `daily_channel_post` (раз в сутки, 10:00 по Алматы) — пост про фильм дня в ПУБЛИЧНЫЙ
   канал-витрину. Фильм берётся у того же `DailyMovieService`, что рисует hero главной
   и пускает `PlaybackService`, иначе пост обещал бы одно кино, а приложение открывало
   другое. Канал не настроен (`BOT_PUBLIC_CHANNEL_ID=0`) → публикация no-op, джоб
   остаётся зарегистрированным (отключать его руками не нужно).

6. `content_post` (ежечасно, :00) — контент-план канала (PLAN.md §4): спрашивает у
   сетки `plan.slot_for(now)`, есть ли слот на этот час (қара сөз по воскресеньям, квиз
   по понедельникам/четвергам…), берёт следующий элемент пула по ротации и публикует.
   Один джоб на все рубрики: расписание — данные в `plan.py`, а не набор крон-строк.
   Идемпотентность — `slot_key` UNIQUE в журнале, поэтому misfire-окно широкое (50 мин):
   бот, перезапущенный в 19:20, опубликует воскресный пост, а не пропустит неделю.

7. `quiz_results` (ежечасно, :00) — разбор закрывшихся квизов: снять кнопки с поста,
   опубликовать ответ и статистику ответом на него. Отдельный джоб от `content_post`
   (другая ответственность), но тот же час: квиз закрывается в 21:00, и разбор уходит
   ровно тогда, когда обещано в посте.

Джобы дёргают сервисы через REQUEST-scope контейнер (сессия БД + репозитории живут именно
там). Запуск/остановка — в `main.py`. Планировщик поднимает ТОЛЬКО процесс бота (api и
worker его не заводят) — поэтому отчёт уходит один раз, сколько бы реплик API ни было.
То же и про пост в канал: дубль там увидели бы все подписчики.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from dishka import AsyncContainer

from app.application.ports.telegram import AdminsUnreachableError, TelegramNotifier
from app.application.services.analytics_service import AnalyticsService
from app.application.services.channel_service import ChannelService
from app.application.services.content_posting_service import ContentPostingService
from app.application.services.quiz_service import QuizService
from app.application.services.subscription_service import SubscriptionService
from app.application.services.video_retention_service import VideoRetentionService
from app.domain.analytics.report import render_report
from app.domain.analytics.weekly_report import render_weekly_report

logger = logging.getLogger(__name__)

EXPIRE_INTERVAL_MINUTES = 15
# Раз в час: выдача живёт 40 ч, до потолка Telegram (48 ч) остаётся запас в 8 часов —
# поэтому пропуск даже нескольких прогонов не превращает видео в неудаляемое.
PURGE_VIDEOS_INTERVAL_MINUTES = 60
# Отчёт — данные: когда и по какому времени. Часовой пояс задан ЯВНО (не «время сервера»):
# контейнеры живут в UTC, и без него «22:00» пришло бы в 3 утра по Казахстану.
REPORT_TZ = ZoneInfo("Asia/Almaty")
REPORT_HOUR = 22
REPORT_MINUTE = 0
# 10 минут после дневного отчёта того же дня — сегодняшний снимок `daily_reports`
# к этому моменту уже точно записан (weekly_report только читает историю, не считает
# заново). Воскресенье — просто конец недели, окно самого отчёта скользящее и от
# дня запуска не зависит.
WEEKLY_REPORT_DAY_OF_WEEK = "sun"
WEEKLY_REPORT_HOUR = 22
WEEKLY_REPORT_MINUTE = 10
# Пост про фильм дня в публичный канал — утром по Алматы (данные: крутить здесь).
# 10:00, а не в местную полночь, когда фильм фактически меняется: пост, ушедший в 00:00,
# к подъёму аудитории утонул бы под ночными сообщениями других каналов, а «бүгін тегін»
# должно попасть на глаза, пока день ещё не прошёл. Тот же `REPORT_TZ`: контейнеры в UTC,
# и без явной зоны «10:00» пришло бы в 5 утра по Казахстану.
DAILY_POST_HOUR = 10
DAILY_POST_MINUTE = 0


async def _expire_due_job(container: AsyncContainer) -> None:
    async with container() as request_container:
        service = await request_container.get(SubscriptionService)
        count = await service.expire_due(datetime.now(UTC))
    if count:
        logger.info("Подписка истекла у %d пользователей → EXPIRED", count)


async def _purge_stale_videos_job(container: AsyncContainer) -> None:
    async with container() as request_container:
        service = await request_container.get(VideoRetentionService)
        # Пачками внутри; число разобранных логирует сам сервис.
        await service.purge_stale(datetime.now(UTC))


async def _daily_report_job(container: AsyncContainer) -> None:
    async with container() as request_container:
        analytics = await request_container.get(AnalyticsService)
        notifier: TelegramNotifier = await request_container.get(TelegramNotifier)
        report = await analytics.daily_report(datetime.now(UTC), REPORT_TZ)
        try:
            await notifier.notify_admins(render_report(report))
        except AdminsUnreachableError:
            # Никто из админов не получил сводку (не нажал /start / заблокировал бота).
            # Это не повод ронять джоб — цифры не потеряны, они всегда в БД.
            logger.warning("Ежедневный отчёт не доставлен ни одному админу")


async def _weekly_report_job(container: AsyncContainer) -> None:
    async with container() as request_container:
        analytics = await request_container.get(AnalyticsService)
        notifier: TelegramNotifier = await request_container.get(TelegramNotifier)
        report = await analytics.weekly_report(datetime.now(UTC), REPORT_TZ)
        try:
            await notifier.notify_admins(render_weekly_report(report))
        except AdminsUnreachableError:
            logger.warning("Еженедельный дайджест не доставлен ни одному админу")


async def _content_post_job(container: AsyncContainer) -> None:
    async with container() as request_container:
        posting = await request_container.get(ContentPostingService)
        if await posting.post_slot(datetime.now(UTC)):
            logger.info("Пост контент-плана опубликован в канале")


async def _quiz_results_job(container: AsyncContainer) -> None:
    async with container() as request_container:
        quiz = await request_container.get(QuizService)
        if count := await quiz.publish_due_results(datetime.now(UTC)):
            logger.info("Опубликовано разборов квиза: %d", count)


async def _daily_channel_post_job(container: AsyncContainer) -> None:
    async with container() as request_container:
        channel = await request_container.get(ChannelService)
        # Исключений публикатор не бросает (деградация в адаптере), поэтому своего
        # try/except тут нет: джоб не может упасть из-за недоступного канала.
        if await channel.publish_daily_movie(datetime.now(UTC)):
            logger.info("Фильм дня опубликован в канале")


def build_scheduler(container: AsyncContainer) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        _expire_due_job,
        "interval",
        minutes=EXPIRE_INTERVAL_MINUTES,
        args=[container],
        id="expire_due",
    )
    scheduler.add_job(
        _purge_stale_videos_job,
        "interval",
        minutes=PURGE_VIDEOS_INTERVAL_MINUTES,
        args=[container],
        id="purge_stale_videos",
    )
    scheduler.add_job(
        _daily_report_job,
        CronTrigger(hour=REPORT_HOUR, minute=REPORT_MINUTE, timezone=REPORT_TZ),
        args=[container],
        id="daily_report",
        # Бот перезапустился в 22:05 — отчёт за день всё равно уйдёт (в пределах часа),
        # а не пропадёт до завтра; coalesce не даёт послать его дважды.
        misfire_grace_time=3600,
        coalesce=True,
    )
    scheduler.add_job(
        _weekly_report_job,
        CronTrigger(
            day_of_week=WEEKLY_REPORT_DAY_OF_WEEK,
            hour=WEEKLY_REPORT_HOUR,
            minute=WEEKLY_REPORT_MINUTE,
            timezone=REPORT_TZ,
        ),
        args=[container],
        id="weekly_report",
        misfire_grace_time=3600,
        coalesce=True,
    )
    scheduler.add_job(
        _daily_channel_post_job,
        CronTrigger(hour=DAILY_POST_HOUR, minute=DAILY_POST_MINUTE, timezone=REPORT_TZ),
        args=[container],
        id="daily_channel_post",
        # Бот перезапустился в 10:05 — пост всё равно уйдёт (в пределах часа), а
        # `coalesce` не даст опубликовать его дважды: дубль в публичном канале виден
        # всем подписчикам, в отличие от повторного отчёта в личку админа.
        misfire_grace_time=3600,
        coalesce=True,
    )
    scheduler.add_job(
        _content_post_job,
        CronTrigger(minute=0, timezone=REPORT_TZ),
        args=[container],
        id="content_post",
        # Меньше часа: следующий запуск сам проверит свой слот, а слоты в сетке стоят на
        # разные часы, поэтому 50 минут догоняют пропущенный час, не задевая следующий.
        misfire_grace_time=3000,
        coalesce=True,
    )
    scheduler.add_job(
        _quiz_results_job,
        CronTrigger(minute=0, timezone=REPORT_TZ),
        args=[container],
        id="quiz_results",
        # Разбор идемпотентен по `result_posted_at` — догонять можно смело.
        misfire_grace_time=3000,
        coalesce=True,
    )
    return scheduler
