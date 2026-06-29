# PLAN.md — дорожная карта QazaqCinema

Рабочий план по фазам. Каждая сессия: открыть этот файл → найти **ТЕКУЩУЮ ПОЗИЦИЮ** →
сделать следующие невыполненные шаги → отметить `[x]` → подвинуть маркер.

**Definition of Done для любой фазы:** `ruff check app tests`, `mypy app`, `pytest` — зелёные;
новое поведение покрыто тестом (где применимо).

---

## 📍 ТЕКУЩАЯ ПОЗИЦИЯ
**Фаза 4 — закрыта** (2026-06-29): каталог-сервис + 3 эндпоинта были готовы с Фазы 3, добавлен
тест-страж `tests/test_movie_dto.py` — `telegram_file_id` не утекает в `MovieOut` (нет поля в
схеме + значение не появляется в JSON). **Чора имён миграций — сделана** (`yyyymmdd_<slug>`, см.
ниже). Зелёные ruff + mypy(strict, `app`) + pytest(32). Дальше → **Фаза 5: защищённая inline-выдача**.

Остаётся ручное (хвост Фазы 3, нужен Docker + живой бот): применить `alembic upgrade head` на
рабочей БД и прогнать визард `/add` через @qazaqcinema_bot — код готов, на проде не верифицирован.

> **План пересмотрен 2026-06-28:** подписка вынесена в отдельную **Фазу 6 (Подписка и контроль
> доступа)** ПЕРЕД оплатой (Kaspi → Фаза 7, Stars → Фаза 8); прежняя «Фаза 8 — Крон» влита в Фазу 6.

## 🔧 Чоры (вне фаз)
- [x] **Человекочитаемые имена миграций** (`yyyymmdd_<slug>`). Сделано 2026-06-29: `file_template`
      в `alembic.ini` задан; файлы → `20260625_initial.py` / `20260628_movie_titles_and_search.py`
      (`git mv`, revision id ВНУТРИ файлов не тронут); `alembic history` + offline `upgrade head --sql`
      перепроверены — цепочка `<base> → c2d3c2c343d2 → b7f3a9c2d1e4 (head)` цела. Контекст ниже:
      Сейчас имя файла = `<random_hex>_<slug>.py`:
      Alembic даёт случайный hex как `revision id` — это лишь уникальный ключ для `down_revision`/
      `alembic_version`, порядок задаётся связями, а не датой/именем (для людей — неудобно).
      Сделать: в `alembic.ini` задать
      `file_template = %%(year)d%%(month).2d%%(day).2d_%%(slug)s`
      (при желании точнее — добавить `_%%(hour).2d%%(minute).2d`). `revision id` внутри файла
      можно оставить hex — на работу не влияет. Существующие переименовать (id ВНУТРИ не трогать):
      `c2d3c2c343d2_initial.py` → `20260625_initial.py`;
      `b7f3a9c2d1e4_movie_titles_and_search.py` → `20260628_movie_titles_and_search.py`.
      После — сверить `alembic history` и `alembic upgrade head --sql`.

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

## Фаза 3 — Добавление фильмов: бот-визард `/add` (FSM) ✅ (код; ручная проверка — за тобой)
**Цель:** нетехнический админ добавляет фильм пошагово в личке бота. Видео — копией в канал-архив
(`protect_content`), постер — статикой на VPS, метаданные — в БД.

**Решения 2026-06-28 (детали в CLAUDE.md):** постеры — **файлами на VPS** (не Telegram file_id,
не прокси); основное название — **казахское** `title_kk` (+ `title_ru`, `title_original`); поиск —
**pg_trgm + unaccent** (опечатки/подстрока, работает для казахского). Визард вместо подписи-#ключами;
`caption_parser` остаётся утилитой.

**Схема/инфра:**
- [x] `Movie`/`MovieModel`: `title`→`title_kk`, +`title_ru`/`title_original` (nullable), +`created_at`
- [x] `MovieOut` отдаёт `title_kk/title_ru/title_original` (фронт покажет kk основным)
- [x] Миграция `b7f3a9c2d1e4` (ручная): rename + колонки + `pg_trgm`/`unaccent` + immutable
      `f_unaccent` + GIN-trgm индексы на 3 поля названий (проверена base→head на scratch-БД)
- [x] `MediaConfig` (`MEDIA_ROOT`/`MEDIA_POSTERS_URL_BASE`); порт `PosterStorage` +
      `LocalPosterStorage` (uuid-имя, async-запись); StaticFiles-mount `/posters` в API; DI
- [ ] ⚠️ применить `alembic upgrade head` на рабочей БД (CREATE EXTENSION требует прав superuser)

**Поиск (фундамент Фазы 4):**
- [x] `PgMovieRepository.search`: `f_unaccent` + ILIKE-подстрока по title_kk/ru/original/description
      + ранжирование `similarity()` (тот же `f_unaccent`, что в GIN-индексе)
- [x] `CatalogService.list_movies/search_movies/get_movie`
- [x] conftest: `pg_trgm`/`unaccent`/`f_unaccent` + drop/create (тесты идут через `create_all`)

**Визард (aiogram FSM, только `BOT_ADMIN_USER_IDS`):**
- [x] `/add`: видео → постер → категория (кнопки из `CATEGORIES`) → `title_kk` → `title_ru`(/skip)
      → `title_original`(/skip) → год(/skip) → рейтинг(/skip) → описание → подтверждение
- [x] По подтверждению: видео копией в канал-архив (`protect_content`) → file_id; постер
      скачивается 1 раз; `MovieIngestionService.ingest(...)` → запись + DM админам
- [x] `/cancel` сбрасывает визард; ретраи при неверном вводе (не фото/видео и т.п.)
- [x] Юнит-тест `MovieIngestionService` (фейки storage/repo/notifier)
- [ ] Ручная проверка через @qazaqcinema_bot: фильм в БД, видео в канале, постер открывается

## Фаза 4 — Каталог (сервис + API) ✅
**Цель:** Web App получает список/поиск/детали фильмов (без `telegram_file_id`).
- [x] `CatalogService.list_movies / search_movies / get_movie` (готов с Фазы 3)
- [x] `GET /api/movies?category=`, `/api/movies/search?q=`, `/api/movies/{id}` → `MovieOut`
- [x] Тест: ответ НЕ содержит `telegram_file_id` (`tests/test_movie_dto.py` — страж на уровне DTO,
      без БД/HTTP: нет поля в схеме + значение не просачивается в JSON)

## Фаза 5 — Бот: защищённая inline-выдача
**Цель:** тап по превью → видео с `protect_content=True` только подписчику.
- [ ] `inline_query.py`: распарсить `movie_<id>`
- [ ] Проверить `User.has_active_access(now)`; нет доступа → подсказка открыть Web App
- [ ] `InlineQueryResultCachedVideo(video_file_id=movie.telegram_file_id, protect_content=True)`
- [ ] Ручная проверка: подписчик видит видео, не-подписчик — нет; запрет скачивания работает

## Фаза 6 — Подписка и контроль доступа
**Цель:** единый «движок доступа» ДО оплаты — потом любой способ оплаты просто дёргает его.
Грант/ревок подписки и проверка `has_active_access` живут здесь, а не размазаны по способам оплаты.
- [ ] `SubscriptionService.activate(user, tariff, now)`: `compute_expiry` → User ACTIVE +
      `expires_at` + DM пользователю. Ядро гранта — вызывается из любого способа оплаты.
- [ ] `SubscriptionService.expire_due(now)`: ACTIVE с истёкшим `expires_at` → EXPIRED.
- [ ] `infrastructure/scheduler.py`: apscheduler-джоб каждые N минут → `expire_due`
      (REQUEST-scope контейнер); запуск планировщика в `main.py`.
- [ ] Контроль доступа: `has_active_access` (уже есть в `User`) — единый гейт. API-зависимость
      `require_active_access` (поверх `get_current_user`) для «только подписчикам»; в inline-выдаче
      (Фаза 5) — тот же чек. Каталог-просмотр свободный, видео — по подписке.
- [ ] Тесты `SubscriptionService` на фейках: activate (срок по тарифу), expire_due (только
      просроченные), has_active_access (граничные даты).

## Фаза 7 — Оплата: Kaspi (ручной чек)
**Цель:** выбор тарифа → реквизиты → загрузка чека → модерация → активация (через Фазу 6).
- [ ] `PaymentService.initiate` (Kaspi) → реквизиты (номер/имя) на фронт
- [ ] `POST /api/payments/proof` (multipart): залить файл боту → `file_id`;
      PaymentRequest(PENDING) + User→PENDING_REVIEW
- [ ] `notifier.send_payment_proof_to_admins`: фото чека в чат модерации + кнопки ✅/❌
- [ ] `moderation.py`: callback `pay:approve|reject:<id>` → approve вызывает
      `SubscriptionService.activate`, reject → PaymentRequest=REJECTED (грант — в Фазе 6, не дублируем)
- [ ] Тест: одобрение чека → подписка активна; отклонение → доступа нет

## Фаза 8 — Оплата: Telegram Stars (авто-подписка)
**Цель:** нативная оплата цифрового контента + помесячная авто-подписка.
- [ ] Сверить актуальную доку Telegram Payments (Stars/XTR, subscription_period)
- [ ] `TelegramStarsProvider.initiate`: `create_invoice_link(currency="XTR", …)`
- [ ] Хендлеры `pre_checkout_query` + `successful_payment` → `SubscriptionService.activate`
- [ ] Зарегистрировать Stars в `payment_providers` (DI) — без правок сервисов
- [ ] Обработка авто-продления (recurring) для тарифа `1_month`

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
