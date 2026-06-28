# CLAUDE.md — гайд для будущих сессий

Этот файл — память проекта. Прочитай его первым, потом загляни в [PLAN.md](PLAN.md): там отмечено,
**где остановились и что делать дальше**.

## Что это
**QazaqCinema** — онлайн-кинотеатр (Netflix-style) внутри Telegram Web App: редкие мультфильмы
и аниме с казахской озвучкой. Видео лежит в приватном **канале-архиве** Telegram (бэкенд не
стримит тяжёлое видео), защита через `protect_content=True`, монетизация — подписка (Kaspi-чеки +
Telegram Stars). Контент наполняется автоматически: админ постит видео с подписью-ключами в канал,
бот парсит и пишет фильм в БД.

## Стек (зафиксирован)
- **Python 3.13**
- **aiogram 3.x** — бот (polling сейчас; webhook+Nginx — на этапе прода)
- **FastAPI** — API для Web App
- **SQLAlchemy 2.0 async + asyncpg + Alembic** — PostgreSQL
- **dishka** — DI-контейнер (composition root)
- **apscheduler** — фоновые задачи (сброс просроченных подписок)
- **React 19 + Vite 6 + TypeScript + Tailwind v4** — Web App (`web/`)
- **Docker Compose** — postgres, redis, bot, api

## Архитектура: Clean / Hexagonal + DDD-lite
Принцип: **домен не знает про aiogram/FastAPI/Postgres**. Зависимости направлены внутрь (DIP).
Bot и API — два «presentation»-входа, оба тонкие: достать данные → делегировать сервису → отдать ответ.

```
app/
  bot/            # Presentation #1. ТОЛЬКО здесь импортируется aiogram
    handlers/     # start, channel_post (автонаполнение), inline_query (выдача), moderation (✅/❌)
    keyboards/    # webapp-кнопка, клавиатура модерации
  api/            # Presentation #2. FastAPI
    routers/      # auth (initData), catalog (фильмы), payments (тарифы/чек)
    schemas/      # pydantic DTO — БЕЗ telegram_file_id наружу
    deps/         # (TODO) FastAPI-зависимость авторизации
  domain/         # Ядро. Без внешних зависимостей. POPO + dataclass
    entities/     # Movie, User (+ has_active_access), PaymentRequest, enums
    tariffs/      # Tariff (VO) + catalog.py (тарифная сетка как данные)
    parsing/      # caption_parser (чистая функция #title… → ParsedMovie)
    catalog/      # справочник категорий (данные, не enum)
    subscription/ # expiry.compute_expiry (чистый расчёт срока)
    registry.py   # generic Registry[T] (PEP 695) — задел для slug-плагинов
  application/    # Use-cases
    ports/        # Protocol-интерфейсы: repositories, payments, telegram, security  ← границы DIP/ISP
    services/     # Auth, Catalog, MovieIngestion, Subscription, Payment — зависят ТОЛЬКО от портов
  infrastructure/ # Адаптеры (реализации портов)
    db/           # models (ORM) + engine + repositories (мапят ORM↔domain)
    telegram/     # init_data (HMAC-валидатор) + notifier (поверх aiogram Bot)
    payments/     # kaspi (ручная), stars (Telegram Stars) — реализации PaymentProvider
    di/           # providers.py — composition root (dishka)
    scheduler.py  # apscheduler
  config/         # pydantic-settings, load_config()
  main.py         # сборка контейнера, polling
```

## Модель гибкости (понять до правок)
Две оси, разными механизмами:
- **ДАННЫЕ** (меняются правкой одной строки, без миграции): тарифы (`tariffs/catalog.py`),
  категории (`catalog/categories.py`). В БД категория/статус/способ — **VARCHAR**, не PG-ENUM,
  поэтому новое значение не требует миграции типа.
- **КОД** (что вообще существует как поведение): способы оплаты (`PaymentProvider` —
  Strategy-адаптеры), ключи парсера (`KNOWN_KEYS`), будущие slug-плагины через `registry.py`.
  Добавить = новый класс/запись, без правок существующих (OCP).

## Паттерны (где искать)
| Паттерн | Файл |
|---|---|
| Repository + DIP | `application/ports/repositories.py` ↔ `infrastructure/db/repositories.py` |
| Strategy (оплата) | `application/ports/payments.py` ↔ `infrastructure/payments/{kaspi,stars}.py` |
| Strategy/данные (тарифы) | `domain/tariffs/catalog.py` |
| Чистая функция-парсер | `domain/parsing/caption_parser.py` |
| Чистый расчёт срока | `domain/subscription/expiry.py` |
| DTO + защита данных | `api/schemas/*` (нет `telegram_file_id`) |
| Валидатор initData (HMAC) | `infrastructure/telegram/init_data.py` |
| Generic Registry (PEP 695) | `domain/registry.py` |
| DI / composition root | `infrastructure/di/providers.py`, `main.py`, `api/app.py` |
| Миграции БД (async) | `alembic.ini`, `migrations/env.py` |

## SOLID-чеклист при добавлении кода
- **S**: хендлер/роутер не содержит бизнес-логику; сервис не лезет в aiogram/FastAPI.
- **O**: новый способ оплаты/категория/тариф = новый класс/запись, без правок существующего.
- **L**: все `PaymentProvider`/репозитории взаимозаменяемы через свой Protocol.
- **I**: порты мелкие и раздельные (MovieRepository ≠ UserRepository ≠ PaymentRepository).
- **D**: сервисы импортируют `application.ports.*`, НЕ `infrastructure.*`.

## Команды
```bash
.venv/bin/pytest                 # тесты домена (без БД)
.venv/bin/ruff check app tests   # линт
.venv/bin/mypy app               # типы (strict)
.venv/bin/python -m app.main     # бот (polling) — нужен .env
.venv/bin/uvicorn app.api.app:app --reload   # API + /docs

.venv/bin/alembic revision --autogenerate -m "msg"  # миграция по diff моделей (нужен postgres)
.venv/bin/alembic upgrade head                       # применить
.venv/bin/alembic upgrade head --sql                 # offline DDL

docker compose up --build        # postgres + redis + bot + api
cd web && npm install && npm run dev   # фронтенд
```

## Состояние / что дальше
> Детальная дорожная карта со всеми шагами и чекбоксами — в **[PLAN.md](PLAN.md)**.
> При расхождении PLAN.md приоритетнее.

**Сделано (Фаза 0 — каркас):** структура по SOLID, конфиг (pydantic-settings, секции с
`env_prefix`), доменное ядро (entities, тарифы, парсер подписи, расчёт срока — с тестами),
порты (Protocol), скелеты сервисов, ORM-модели, репозитории-скелеты, DI-контейнер (dishka,
поднимается), бот (4 роутера, `/start` рабочий), API (7 эндпоинтов, `/tariffs` рабочий),
HMAC-валидатор initData (реализован + тесты), Kaspi-провайдер, Alembic (async env), Docker,
фронтенд-каркас (React+Vite+TS+Tailwind).

**Сделано (Фаза 1 — БД):** миграция `c2d3c2c343d2_initial` применена; репозитории
`PgMovie/PgUser/PgPayment` реализованы (мапперы ORM↔домен, `upsert` ON CONFLICT) +
интеграционные тесты (фикстура `session`, skip без БД); логотип в `web/public/logo.png`.

**Сделано (Фаза 2 — авторизация):** `AuthService.authenticate` (verify initData →
get/upsert User NEW); FastAPI-зависимость `get_current_user` (request-scope контейнер dishka
из `request.state.dishka_container`); каталог и оплата защищены, `/tariffs` публичный; оплата
берёт `user_id` из initData; юнит-тесты `AuthService` (фейки). Зелёное: ruff + mypy + pytest(28).

**Не сделано — по приоритету (детали в PLAN.md):**
1. Сервисы (тела): `CatalogService`, `SubscriptionService`, `MovieIngestionService`.
2. **Добавление фильмов — бот-визард `/add`** (FSM, Фаза 3): смена `poster_url`→`poster_file_id`,
   эндпоинт `GET /api/posters/{id}` (бот качает фото), видео в канал-хранилище.
3. Бот: защищённая inline-выдача (`protect_content`), модерация чеков (✅/❌).
4. Оплата: приём чека (multipart), Telegram Stars (инвойс + авто-подписка), крон `expired`.
5. Фронтенд: каталог/карусели, поиск, модалки, пэйволл с загрузкой чека.
6. Прод: webhook + Nginx.

## Решения, которые уже приняты (не пересматривать без причины)
- **Python 3.13**. Backend — **FastAPI** (не Django/PHP): ложится на async-стек.
- **БД — PostgreSQL** (asyncpg + Alembic). ORM-модели отделены от доменных сущностей намеренно.
- `telegram_file_id` — **только боту**, в API-DTO отсутствует. Inline-видео — всегда
  `protect_content=True`. Это ядро безопасности продукта.
- Категория/статус/способ оплаты в БД — **VARCHAR**, не PG-ENUM (добавить значение без миграции).
- `users.telegram_id` и `payment_requests.user_id` — **BIGINT** без автоинкремента (Telegram ID).
- **Оплата — Strategy-порт** `PaymentProvider`: Kaspi (MVP, ручной чек) + Telegram Stars
  (авто-подписка, **только помесячная** по ограничению Telegram). 1 день/3 месяца — разовые покупки.
  Цифровой контент по политике Telegram продаётся через Stars (сверяться с актуальной докой!).
- **Заявки на оплату** — единая таблица `payment_requests` (аудит), универсальная по способу:
  `proof_file_id` для Kaspi, `external_charge_id` для Stars/фиата.
- **Авторизация Web App** — валидация `initData` (HMAC) на каждый запрос, без JWT (stateless).
- **Тарифы/категории — данные** (словарь), не классы; способы оплаты/ключи парсера — код (OCP).
- **DI — dishka**, composition root в `infrastructure/di/providers.py`. APP-scope: config, движок,
  Bot, провайдеры оплаты; REQUEST-scope: сессия БД, репозитории, сервисы.
- Каждая секция конфига объявляет свой `env_file=".env"` и `env_prefix` (вложенные BaseSettings
  через `default_factory` НЕ наследуют env_file родителя). Списки из env — через `NoDecode` +
  валидатор (иначе pydantic-settings пытается JSON-декодить).
- Alembic берёт DSN из `DatabaseConfig` (для миграций BOT_TOKEN не нужен); переопределение
  `alembic -x dsn=...`.
