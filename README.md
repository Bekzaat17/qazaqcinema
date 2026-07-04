# QazaqCinema 🎬

Онлайн-кинотеатр (Netflix-style) внутри **Telegram Web App** — редкие мультфильмы и аниме
с казахской озвучкой. Видео хранится в приватном канале-архиве Telegram (экономия на хостинге),
контент защищён от скачивания (`protect_content=True`), оплата — Kaspi-чеки + Telegram Stars.

> 📖 **Перед работой над кодом** прочитай [CLAUDE.md](CLAUDE.md) (архитектура и принятые решения)
> и [PLAN.md](PLAN.md) (пошаговая дорожная карта — где остановились и что дальше).

## Возможности
- **Наполнение каталога**: админ добавляет фильм через бот-визард `/add` (видео → постер →
  на главную?/баннер → категория → названия → метаданные). Видео уходит в канал-архив; постер
  нормализуется (Pillow → 2:3) и кладётся статикой на VPS.
- **Защищённый просмотр**: видео шлёт бот в личку с `protect_content=True` (нельзя скачать,
  переслать, записать экран). `telegram_file_id` никогда не уходит на фронтенд; триггер — `POST /play`.
- **Подписка**: 2 тарифа (1 күн / 1 ай). Kaspi-чеки с ручной модерацией (MVP) + Telegram Stars
  как нативная авто-подписка.
- **Web App**: тёмный интерфейс — hero-баннер (курируется бэком), полки по категориям, поиск,
  карточка фильма, пэйволл (Kaspi/Stars).

## Стек
- **Backend**: Python 3.13, **aiogram 3** (бот), **FastAPI** (API), **SQLAlchemy 2.0 async** +
  **asyncpg** + **Alembic** (PostgreSQL), **dishka** (DI), **apscheduler** (крон), **Pillow**
  (нормализация постеров/hero-баннеров).
- **Frontend**: React 19 + Vite 6 + TypeScript + Tailwind CSS v4.
- **Инфраструктура**: Docker Compose (postgres, redis, bot, api).

## Структура
```
app/
  bot/            # aiogram: handlers (start, add_movie, inline_query, moderation, stars), keyboards, security
  api/            # FastAPI: routers (auth, catalog, payments), schemas (DTO), deps
  domain/         # ядро без внешних зависимостей: entities, tariffs, parsing, catalog, subscription
  application/    # ports (Protocol-интерфейсы) + services (use-cases)
  infrastructure/ # адаптеры: db (модели/репозитории), telegram, payments, di, scheduler
  config/         # pydantic-settings
  main.py         # запуск бота (polling)
web/              # Web App (React + Vite + TS + Tailwind)
migrations/       # Alembic
tests/            # тесты домена (без БД)
```

## Быстрый старт

### Backend
```bash
# venv уже создан; зависимости установлены (pip install -e ".[dev]")
cp .env.example .env            # заполни BOT_TOKEN, BOT_ADMIN_*, BOT_ARCHIVE_CHANNEL_ID, …

docker compose up -d postgres redis      # поднять БД и кеш
.venv/bin/alembic upgrade head           # применить миграции (после генерации 0001_initial)

.venv/bin/python -m app.main             # бот (polling)
.venv/bin/uvicorn app.api.app:app --reload   # API на http://localhost:8000 (/docs — Swagger)
```

### Frontend
```bash
cd web
cp .env.example .env.local      # VITE_API_URL=http://localhost:8000
npm install
npm run dev                     # http://localhost:5173
```

### Всё через Docker
```bash
docker compose up --build       # postgres + redis + bot + api
```

## Команды
```bash
.venv/bin/pytest                       # тесты домена (без БД)
.venv/bin/ruff check app tests         # линт
.venv/bin/mypy app                     # типы (strict)

.venv/bin/alembic revision --autogenerate -m "msg"   # новая миграция по diff моделей
.venv/bin/alembic upgrade head                       # применить
.venv/bin/alembic upgrade head --sql                 # offline DDL без подключения к БД
```

## Безопасность (ядро продукта)
- `telegram_file_id` отдаётся **только боту**, в API-схемах (`MovieOut`) его нет.
- Видео шлёт бот в личку с `protect_content=True` (inline-результаты `protect_content` не умеют).
- Каждый запрос Web App к API авторизуется по Telegram `initData` (валидация HMAC + TTL по
  `auth_date` против реплея, см. `app/infrastructure/telegram/init_data.py`).
- Модерация оплат (`pay:approve/reject`) — под явным админ-гейтом (`app/bot/security.is_admin`).
