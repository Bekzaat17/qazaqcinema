# PLAN.md — дорожная карта QazaqCinema

Рабочий план по фазам. Каждая сессия: открыть этот файл → найти **ТЕКУЩУЮ ПОЗИЦИЮ** →
сделать следующие невыполненные шаги → отметить `[x]` → подвинуть маркер.

**Definition of Done для любой фазы:** `ruff check app tests`, `mypy app`, `pytest` — зелёные;
новое поведение покрыто тестом (где применимо).

---

## 📍 ТЕКУЩАЯ ПОЗИЦИЯ
**Фаза 2 завершена (авторизация).** Дальше → **Фаза 3: Добавление фильмов (бот-визард `/add`)**.

---

## Фаза 0 — Каркас проекта ✅
- [x] venv (Python 3.13), `pyproject.toml` (зависимости + ruff/mypy/pytest)
- [x] Структура пакетов по слоям (bot / api / domain / application / infrastructure / config)
- [x] Конфиг: `pydantic-settings`, секции `BOT_/DB_/REDIS_/PAY_/API_`, `.env.example`
- [x] Домен: `Movie`, `User` (+`has_active_access`), `PaymentRequest`, enums
- [x] Домен: тарифы (`tariffs/catalog.py`), категории (`catalog/categories.py`)
- [x] Домен: `parsing/caption_parser.py` (+ тест), `subscription/expiry.py` (+ тест)
- [x] Порты (Protocol): repositories, payments, telegram, security
- [x] Скелеты сервисов: Auth, Catalog, MovieIngestion, Subscription, Payment
- [x] ORM-модели (`users`, `movies`, `payment_requests`), engine, репозитории-скелеты
- [x] DI-контейнер (dishka) — поднимается; APP + REQUEST scope
- [x] Бот: роутеры (start✓, channel_post, inline_query, moderation), `setup.py`
- [x] API: FastAPI (`/api/auth`, `/api/movies*`, `/api/payments*`), `/tariffs` рабочий
- [x] `infrastructure/telegram/init_data.py` — HMAC-валидатор initData (+ тесты)
- [x] `infrastructure/payments/kaspi.py` — рабочий; `stars.py` — скелет
- [x] Alembic (async `env.py`), Dockerfile, docker-compose
- [x] Фронтенд-каркас: React 19 + Vite 6 + TS + Tailwind v4 (`web/`)
- [x] Зелёные ruff + mypy(strict) + pytest(20)

---

## Фаза 1 — БД и репозитории ✅
**Цель:** живая БД + рабочие репозитории (мапинг ORM↔домен).
- [x] `docker compose up -d --wait postgres` + локальный `.env`
- [x] `alembic revision --autogenerate` → миграция `c2d3c2c343d2_initial` (3 таблицы + индексы)
- [x] `alembic upgrade head` → таблицы `users/movies/payment_requests` созданы
- [x] `PgMovieRepository`: `add`, `get`, `list_all(category)`, `search(query)` + мапперы `_to_domain`
- [x] `PgUserRepository`: `get`, `upsert` (ON CONFLICT по telegram_id), `list_expired(now)`
- [x] `PgPaymentRepository`: `add`, `get`, `set_status`
- [x] Интеграционные тесты репозиториев (фикстура `session`, skip без БД) — 5 шт.

## Фаза 2 — Авторизация Web App (initData) ✅
**Цель:** фронт шлёт initData → бэк валидирует → отдаёт статус/доступ.
- [x] `AuthService.authenticate`: verify(initData) → get/upsert User(NEW) → вернуть
- [x] FastAPI-зависимость `api/deps/auth.py` (`get_current_user`) поверх `AuthService`
- [x] `POST /api/auth` возвращает `AuthOut` (status, expires_at, has_access)
- [x] Защищены каталог + оплата (`Depends(get_current_user)`); `/tariffs` публичный
- [x] Юнит-тесты `AuthService` (фейки): создание NEW / существующий / битый initData
- [ ] (опционально, позже) e2e-тест эндпоинта через TestClient (нужен httpx)

## Фаза 3 — Добавление фильмов: бот-визард `/add` (FSM)
**Цель:** нетехнический админ добавляет фильм пошагово в личке бота. Видео уходит в
канал-хранилище (`qazaqcinema`), метаданные — в БД. (Решение 2026-06: визард вместо
подписи-#ключами; `caption_parser` пока остаётся как утилита, не основной путь.)

**Изменения модели/инфры (в начале фазы):**
- [ ] `Movie`/`MovieModel`: `poster_url` → `poster_file_id` (Telegram photo file_id) + миграция
- [ ] Порт `TelegramFiles` (get_file/download) + адаптер поверх aiogram Bot
- [ ] `GET /api/posters/{movie_id}`: бот качает фото по file_id, отдаёт картинку (кэш на диск `/uploads`)
- [ ] `MovieOut.poster_url` = `/api/posters/{id}` (контракт фронта не меняется)

**Визард (aiogram FSM, только для `BOT_ADMIN_USER_IDS`):**
- [ ] `/add` → видео → постер (фото) → категория (inline-кнопки из `CATEGORIES`) → название
      → год (/skip) → рейтинг (/skip) → описание → экран подтверждения
- [ ] По подтверждению: бот отправляет видео в канал-хранилище → берёт `file_id` для inline-выдачи
- [ ] `MovieIngestionService.ingest(...)` → запись в БД → DM админу «Фильм «{title}» добавлен. ID: {id}»
- [ ] `/cancel` сбрасывает визард; валидация шагов (не фото вместо видео и т.п.)
- [ ] Ручная проверка через @qazaqcinema_bot: фильм в БД, видео — в канале

## Фаза 4 — Каталог (сервис + API)
**Цель:** Web App получает список/поиск/детали фильмов (без `telegram_file_id`).
- [ ] `CatalogService.list_movies / search_movies / get_movie`
- [ ] `GET /api/movies?category=`, `/api/movies/search?q=`, `/api/movies/{id}` → `MovieOut`
- [ ] Тест: ответ НЕ содержит `telegram_file_id`

## Фаза 5 — Бот: защищённая inline-выдача
**Цель:** тап по превью → видео с `protect_content=True` только подписчику.
- [ ] `inline_query.py`: распарсить `movie_<id>`
- [ ] Проверить `User.has_active_access(now)`; нет доступа → подсказка открыть Web App
- [ ] `InlineQueryResultCachedVideo(video_file_id=movie.telegram_file_id, protect_content=True)`
- [ ] Ручная проверка: подписчик видит видео, не-подписчик — нет; запрет скачивания работает

## Фаза 6 — Оплата: Kaspi (ручной чек)
**Цель:** выбор тарифа → реквизиты → загрузка чека → модерация → активация.
- [ ] `PaymentService.initiate` (Kaspi) → реквизиты (номер/имя) на фронт
- [ ] `POST /api/payments/proof` (multipart): залить файл боту → `file_id`
- [ ] `SubscriptionService.submit_proof`: PaymentRequest(PENDING) + User→PENDING_REVIEW
- [ ] `notifier.send_payment_proof_to_admins`: фото чека в чат модерации + кнопки ✅/❌
- [ ] `moderation.py`: callback `pay:approve|reject:<id>`
- [ ] `SubscriptionService.approve` (compute_expiry → User ACTIVE, DM юзеру) / `reject`
- [ ] Тест жизненного цикла подписки (с фейковыми портами)

## Фаза 7 — Оплата: Telegram Stars (авто-подписка)
**Цель:** нативная оплата цифрового контента + помесячная авто-подписка.
- [ ] Сверить актуальную доку Telegram Payments (Stars/XTR, subscription_period)
- [ ] `TelegramStarsProvider.initiate`: `create_invoice_link(currency="XTR", …)`
- [ ] Хендлеры `pre_checkout_query` + `successful_payment` → авто-approve подписки
- [ ] Зарегистрировать Stars в `payment_providers` (DI) — без правок сервисов
- [ ] Обработка авто-продления (recurring) для тарифа `1_month`

## Фаза 8 — Крон: сброс просроченных
- [ ] `SubscriptionService.expire_due(now)`: ACTIVE с истёкшим `expires_at` → EXPIRED
- [ ] `infrastructure/scheduler.py`: job каждые N минут через REQUEST-scope контейнера
- [ ] Запуск планировщика в `main.py`
- [ ] Тест `expire_due` на фейковом репозитории

## Фаза 9 — Фронтенд: Web App
**Цель:** тёмный Netflix-style интерфейс.
- [ ] Авторизация при старте (`api.auth`), ветвление по `has_access`
- [ ] Экран пэйволла: 3 тарифа (`/tariffs`), выбор → реквизиты Kaspi → загрузка чека
- [ ] Каталог: карусели по категориям (`/movies?category=`), постеры по `poster_url`
- [ ] Поиск (`/movies/search`)
- [ ] Модалка фильма + кнопка «Көру / Смотреть» → `switchInlineQuery(movie_<id>)`
- [ ] Состояния pending_review / expired
- [ ] Сборка `npm run build`, отдача статики (Nginx или FastAPI StaticFiles)

## Фаза 10 — Прод
- [ ] aiogram webhook вместо polling; FastAPI-роут вебхука
- [ ] Nginx reverse-proxy (TLS, домен Web App, статика)
- [ ] Прод-конфиг compose, секреты, бэкапы БД
- [ ] CORS под реальный домен Web App

---

## Идеи на будущее (не в MVP)
- Кеш каталога в Redis (cache-aside), rate-limit на API.
- Лидерборды/реферальная программа.
- Mini App админки (чекбоксы категорий из справочника).
- Множественные каналы-архивы.
