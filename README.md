# QazaqCinema 🎬

Онлайн-кинотеатр внутри **Telegram Mini App**: мультфильмы и аниме с казахской озвучкой.
Видео хранится в приватном канале-архиве Telegram и выдаётся ботом в личку с
`protect_content=True`; оплата — Kaspi-чеки и Telegram Stars. Публичный канал ведётся
автоматически: фильм дня, новинки, контент про казахский язык и квизы.

> Перед работой над кодом — [CLAUDE.md](CLAUDE.md) (архитектура, инварианты), затем
> [PLAN.md](PLAN.md) (что осталось). Прод — [DEPLOY.md](DEPLOY.md).

## Возможности
- **Каталог** наполняет админ визардом `/add` в боте (видео → постер → категории → названия →
  метаданные → рассылать ли новинку). Поддерживаются сериалы с сезонами. Постер нормализуется
  (Pillow, 2:3) и лежит статикой на VPS.
- **Защищённый просмотр**: `telegram_file_id` не покидает бэкенд; «Көру» шлёт видео в чат с ботом.
  Выданные видео удаляются через 40 часов (подписчик получает их снова по нажатию).
- **Фильм дня** — бесплатный для всех, меняется каждые сутки по Алматы; это же hero главной.
- **Подписка**: тарифы 1 күн / 1 ай. Kaspi (перевод по номеру или Kaspi Pay, чек модерируют
  админы) и Telegram Stars (авто-продление).
- **Mini App**: тёмная тема, казахский UI, три таба — Басты (hero + полки), Каталог (категории,
  сортировка, подгрузка), Таңдаулы (избранное); поиск, профиль, поддержка одним сообщением.
- **SEO**: серверные страницы `/m/<id>-<slug>`, `/catalog`, `/sitemap.xml` для Google;
  deep-link `t.me/<bot>?startapp=m_<id>` открывает карточку в Mini App.
- **Рассылки**: по выбору админа о новинке + ручная `/broadcast`; Redis-очередь и отдельный worker
  с соблюдением лимитов Telegram; тумблер отписки у пользователя.
- **Аналитика**: журнал значимых событий, ежевечерний отчёт админам, недельный дайджест, вехи роста
  (`/milestone`), лог поисковых запросов как очередь на озвучку.
- **Публичный канал**: пост фильма дня и новинок, контент-план из `content/*.yaml` (қара сөз,
  нақыл сөз, атаулары, квизы с разбором), комментарии через группу обсуждений.

## Стек
- **Backend**: Python 3.13, aiogram 3, FastAPI (+ Jinja2 для SSR), SQLAlchemy 2.0 async + asyncpg +
  Alembic (PostgreSQL 16), dishka, apscheduler, redis.asyncio, Pillow, PyYAML.
- **Frontend**: React 19 + Vite 6 + TypeScript + Tailwind v4.
- **Инфраструктура**: Docker Compose, одна топология для dev/prod/test (postgres, redis, migrate,
  api, bot, worker, web=Caddy с авто-TLS). Отличие сред — только env-файл. Redis — сессии, кэш,
  rate-limit, локи, очередь рассылок; все адаптеры fail-open.

## Структура
```
app/
  bot/            # aiogram: handlers (start, add_movie, broadcast, daily, milestone, inline_query, moderation, quiz, stars)
  api/            # FastAPI: routers (auth, catalog, favorites, me, payments, events, support, public_seo, health)
  domain/         # ядро без зависимостей: entities, catalog, tariffs, subscription, analytics, seo, channel
  application/    # ports (Protocol) + services (use-cases)
  infrastructure/ # адаптеры: db, cache (Redis), telegram, payments, images, storage, content, analytics, di, scheduler
  config/         # pydantic-settings
  main.py         # бот (polling/webhook по PUBLIC_ORIGIN)
  worker.py       # воркер рассылок
  tools/          # seed_content (контент канала → БД), preview_post
web/              # Mini App (React + Vite + TS + Tailwind) + Caddyfile
content/          # пул контента канала: YAML + картинки + шрифты
migrations/       # Alembic
tests/            # юнит (домен, сервисы) + интеграционные (репозитории, БД *_test)
```

## Быстрый старт
```bash
./start.sh                  # dev (env = .env; создаётся из .env.example)
./start.sh prod             # те же контейнеры, env = .env.prod
./start.sh test             # ruff + mypy + pytest в контейнере (env = .env.test, БД qazaqcinema_test)
./start.sh seed             # контент канала (content/*.yaml) → БД + картинки
./start.sh logs [сервис] | ps | migrate | backup | down [--clean]
```
После старта: Web → http://localhost/, API-доки → http://localhost:8000/docs,
health → `GET /api/health` → `{"redis":"ok","db":"ok","status":"ok"}`.

Прод-режим включается одной переменной `PUBLIC_ORIGIN=https://домен`: Caddy сам выпускает
сертификат, бот переходит на webhook, CORS выводится оттуда же.

<details><summary>Hot-reload (host-venv поверх Docker-инфры)</summary>

```bash
docker compose --env-file .env up -d postgres redis
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app.api.app:app --reload      # API → :8000
.venv/bin/python -m app.main                    # бот (polling)
cd web && npm run dev                           # Vite HMR → :5173, прокси /api на :8000
```
</details>

## Безопасность (ядро продукта)
- `telegram_file_id` отдаётся только боту, в API-схемах его нет.
- Видео — только `send_video(protect_content=True)` в личку; inline-режим видео не отдаёт.
- Web App авторизуется по initData (HMAC + TTL) с серверной сессией в Redis и initData-фолбэком.
- Админские действия — под явным гейтом `app/bot/security.is_admin`.
