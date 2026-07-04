# PLAN.md — дорожная карта QazaqCinema

Рабочий план по фазам. Каждая сессия: открыть этот файл → найти **ТЕКУЩУЮ ПОЗИЦИЮ** →
сделать следующие невыполненные шаги → отметить `[x]` → подвинуть маркер.

**Definition of Done для любой фазы:** `ruff check app tests`, `mypy app`, `pytest` — зелёные;
новое поведение покрыто тестом (где применимо).

---

## 📍 ТЕКУЩАЯ ПОЗИЦИЯ
**Фаза 9 — код готов** (2026-07-04): фронтенд Mini App (тёмный кино-UI, React 19 + Tailwind v4).
**UI-кит зафиксирован:** иконки — **`lucide-react`** (эмодзи-заглушки заменены на векторные),
шрифт — **Inter** (казахская кириллица), компоненты — свои на Tailwind-токенах (`@theme` в
`web/src/index.css`), анимации/полки — нативный CSS (scroll-snap, CSS-шторки). Собрано: topbar+поиск,
hero + полки (`buildShelves`, порог ряда ≥3), карточка-шторка, пэйволл (2 тарифа, **Kaspi первым** →
реквизиты/копирование/чек, Stars вторым → `openInvoice`), профиль (статус подписки), хэндофф-модалка
«видео ботқа жіберілді» → `WebApp.close()`. Полный API-клиент с типизированной `ApiError`
(403→пэйволл, 404→тост), SDK-обёртка (expand/haptics/BackButton/openInvoice), Vite-прокси (без CORS),
DEV-мок бэка (вырезан из прода). Проверено в браузере на mobile-viewport (все экраны/потоки). Зелёное:
`tsc -b`(strict) + `vite build` (71 КБ gzip). Осталась живая e2e в Telegram (реальные initData/оплата)
→ разблокирует e2e фаз 5–8. Дальше → **Фаза 10: прод** (webhook + Nginx + отдача статики `web/dist`).

**Фаза 8 — код готов** (2026-07-02): оплата Telegram Stars (XTR) + авто-подписка.
`TelegramStarsProvider.initiate` → `create_invoice_link(currency="XTR", provider_token="",
subscription_period=2592000 для recurring)`; помесячный тариф = подписка, разовый = разовый инвойс.
Бот-хендлеры `pre_checkout_query` (быстрая валидация payload, без БД) + `successful_payment` →
`StarsPaymentService.confirm` (запись `PaymentRequest(STARS, APPROVED, external_charge_id)` + грант
через `SubscriptionService.activate`; авто-продление recurring идёт тем же путём — продлевает).
Тариф получил `price_xtr` (данные: 1_day=50, 1_month=250 — бизнес может подкрутить); `TariffOut`
отдаёт его на фронт. DI: Stars в `payment_providers` (с Bot) + `StarsPaymentService` (REQUEST).
Константы Stars сверены с докой Telegram (payments-stars). Юнит-тесты (8): StarsPaymentService (6) +
провайдер на фейковом Bot (2, проверяют XTR/provider_token/subscription_period/amount). Зелёные ruff
+ mypy(strict, `app`, 80) + pytest(57). Осталась ручная e2e. **Оба способа оплаты готовы.**
Дальше → **Фаза 9: фронтенд** (Mini App — разблокирует живую e2e всех фаз).

**Фаза 7 — код готов** (2026-07-02): оплата Kaspi (ручной чек). `PaymentService.initiate`
(валидирует тариф/способ → инструкция провайдера) + `submit_proof` (подтверждает приём чека
юзеру и тем же send берёт telegram `file_id` → PaymentRequest(PENDING) → уведомляет админов →
юзер в PENDING_REVIEW). Новый `PaymentModerationService.approve/reject` (approve дёргает
`SubscriptionService.activate` из Фазы 6; идемпотентен — только PENDING, повтор не грантит дважды;
reject → REJECTED + юзер EXPIRED + DM). Тонкий бот-хендлер `moderation.py` (кнопки ✅/❌ →
сервис). API: `POST /api/payments/{initiate,proof}` (proof — multipart, image-гейт + лимит 10 МБ).
Порт `TelegramNotifier.acknowledge_payment_proof` + реализация `send_payment_proof_to_admins`
(фото+клавиатура в админ-чат). DI: `PaymentService` переехал в REQUEST-scope (нужны репозитории),
добавлен `moderation`. Юнит-тесты (9): PaymentService (5) + PaymentModerationService (4). Зелёные
ruff + mypy(strict, `app`, 78) + pytest(49). Осталась ручная e2e. Дальше → **Фаза 8: Stars** или
**Фаза 9: фронтенд** (по решению пользователя).

**Фаза 6 — код готов** (2026-06-29): движок доступа. `SubscriptionService.activate(user, tariff,
now)` (compute_expiry → ACTIVE + expires_at + DM юзеру) и `expire_due(now)` (просроченные ACTIVE →
EXPIRED, возвращает кол-во). apscheduler-джоб `expire_due` каждые 15 мин через REQUEST-scope
контейнер, старт/стоп в `main.py`. API-зависимость `require_active_access` (поверх
`get_current_user`) для «только подписчикам». Решение пользователя: **тарифа теперь два** — `1_day`
(тестовый доступ) и `1_month` (`3_months` убран). Юнит-тесты `SubscriptionService` (5). Зелёные
ruff + mypy(strict, `app`, 77) + pytest(40). Осталась ручная e2e. Дальше → **Фаза 7: Kaspi**.

**Фаза 5 — код готов** (2026-06-29): защищённая выдача видео переосмыслена — inline не умеет
`protect_content`, поэтому видео шлёт бот в личку (`send_video(protect_content=True)`), триггер —
`POST /api/movies/{id}/play` (initData-гейт + `has_active_access`); inline стал подсказкой-кнопкой.
Новый `PlaybackService` + порт `send_protected_video` + юнит-тесты (3). Осталась ручная e2e (за Web App).

Хвост Фазы 3 — **закрыт** (2026-06-29): миграция применена на рабочей БД (`b7f3a9c2d1e4`, полная
схема), визард `/add` прогнан через @qazaqcinema_bot вживую — фильм id=1 в БД, видео ушло в
канал-архив (`protect_content`), постер сохранён в `uploads/posters/`. Грабли: id канала должен быть
`-100…` (без `-` → «chat not found»), бот — админ канала. **Фазы 0–4 готовы и проверены вживую.**

> **План пересмотрен 2026-06-28:** подписка вынесена в отдельную **Фазу 6 (Подписка и контроль
> доступа)** ПЕРЕД оплатой (Kaspi → Фаза 7, Stars → Фаза 8); прежняя «Фаза 8 — Крон» влита в Фазу 6.
>
> **План дополнен 2026-07-02:** добавлены **Фаза 11 (Redis: сессии, кэш, rate-limit, локи)** и
> **Фаза 12 (рассылки + уведомления о новинках, opt-out по умолчанию ВКЛ)**. Redis-компаньоны
> (сессии/кэш) можно тянуть вместе с Фазой 9; порядок фаз 9–12 гибкий (см. «Когда» в фазах).

## 🔧 Чоры (вне фаз)
- [ ] **Изоляция БД тестов от рабочей** (footgun, проявился 2026-06-29). `tests/conftest.py` делает
      `drop_all`+`create_all` по ТОЙ ЖЕ `DatabaseConfig().dsn`, что и приложение → прогон `pytest`
      перешивает рабочую `movies` через `create_all` (колонки = head по моделям, но БЕЗ миграционных
      GIN-trgm индексов), а `alembic_version` не трогается → дрейф, из-за которого `upgrade head` падал
      на `ALTER … RENAME title`. Фикс: отдельная тест-БД (напр. `DB_NAME=qazaqcinema_test`-override в
      conftest) или транзакция-rollback на тест; рабочую БД тесты трогать не должны.
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

## Фаза 3 — Добавление фильмов: бот-визард `/add` (FSM) ✅ (код + ручная проверка вживую 2026-06-29)
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
- [x] ✅ `alembic upgrade head` на рабочей БД (2026-06-29). Драма дрейфа: БД стояла на `c2d3c2c343d2`,
      но `movies` уже имела схему head (наследие `create_all` из conftest на ТОЙ ЖЕ БД) → `upgrade`
      падал на `ALTER … RENAME title`. Таблицы пустые → чистая пересборка (DROP всех таблиц +
      `alembic_version`, затем upgrade с нуля). Итог: head, 3 GIN-trgm индекса + extensions +
      `f_unaccent`, smoke ок. Корень проблемы → чора «изоляция БД тестов» выше.

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
- [x] Ручная проверка через @qazaqcinema_bot (2026-06-29): фильм id=1 в БД, видео в канале-архиве,
      постер в `uploads/posters/` (грабли: id канала `-100…`, бот — админ канала)

## Фаза 4 — Каталог (сервис + API) ✅
**Цель:** Web App получает список/поиск/детали фильмов (без `telegram_file_id`).
- [x] `CatalogService.list_movies / search_movies / get_movie` (готов с Фазы 3)
- [x] `GET /api/movies?category=`, `/api/movies/search?q=`, `/api/movies/{id}` → `MovieOut`
- [x] Тест: ответ НЕ содержит `telegram_file_id` (`tests/test_movie_dto.py` — страж на уровне DTO,
      без БД/HTTP: нет поля в схеме + значение не просачивается в JSON)

## Фаза 5 — Защищённая выдача видео ✅ (код; ручная e2e — за Web App/Фазой 9)
**Цель:** видео с `protect_content=True` только подписчику.
**Правка дизайна 2026-06-29:** inline-выдача НЕВОЗМОЖНА — `InlineQueryResult*` не поддерживают
`protect_content` (проверено на aiogram 3.29). Видео шлёт бот напрямую в личку через
`send_video(protect_content=True)`; триггер — API `/play` (initData-гейт). Inline оставлен как
подсказка-кнопка (открыть Web App), видео не отдаёт.
- [x] `PlaybackService.deliver(user, movie_id, now)`: гейт `has_active_access` → `NO_ACCESS`;
      фильма нет → `NOT_FOUND`; иначе `notifier.send_protected_video`. Юнит-тест (3 кейса).
- [x] Порт `TelegramNotifier.send_protected_video` + `AiogramNotifier` (`send_video`,
      `protect_content=True`); DI-провайдер `playback`.
- [x] `POST /api/movies/{id}/play` (гейт `get_current_user`) → 200 `{status:"sent"}` /
      403 `no_access` / 404. `telegram_file_id` наружу не отдаётся.
- [x] `inline_query.py`: пустая выдача + `InlineQueryResultsButton` (web_app/deep-link),
      `cache_time=0`, `is_personal`.
- [ ] Ручная e2e: подписчик получает видео в личке (protect_content), не-подписчик → 403.
      Полноценно — через Web App (Фаза 9) или crafted initData + ACTIVE-юзер.

## Фаза 6 — Подписка и контроль доступа ✅ (код; ручная e2e — за Web App/Фазой 9)
**Цель:** единый «движок доступа» ДО оплаты — потом любой способ оплаты просто дёргает его.
Грант/ревок подписки и проверка `has_active_access` живут здесь, а не размазаны по способам оплаты.
- [x] `SubscriptionService.activate(user, tariff, now)`: `compute_expiry` → User ACTIVE +
      `expires_at` + `selected_tariff` + DM пользователю (kk). Ядро гранта — вызывается из любого
      способа оплаты. Зависит только от `UserRepository` + `TelegramNotifier` (PaymentRepository не
      нужен: заведение PaymentRequest/модерация — Фаза 7, её approve дёргает этот `activate`).
- [x] `SubscriptionService.expire_due(now)`: ACTIVE с истёкшим `expires_at` → EXPIRED (через
      `users.list_expired`), возвращает кол-во.
- [x] `infrastructure/scheduler.py`: apscheduler-джоб `expire_due` каждые 15 мин (REQUEST-scope
      контейнер `async with container()`); запуск/останов планировщика в `main.py`.
- [x] Контроль доступа: API-зависимость `require_active_access` (поверх `get_current_user`) →
      403 `no_access` для «только подписчикам». `/play` уже гейтит через PlaybackService. Каталог-
      просмотр свободный, видео — по подписке.
- [x] Тарифов теперь два (решение 2026-06-29): `1_day` (тестовый) + `1_month`; `3_months` убран.
- [x] Тесты `SubscriptionService` на фейках (5): activate (новый/продление/после истечения + DM),
      expire_due (только просроченные + счёт). Граничные `has_active_access` — в `test_user.py`.

## Фаза 7 — Оплата: Kaspi (ручной чек) ✅ (код; ручная e2e — за Web App/Фазой 9)
**Цель:** выбор тарифа → реквизиты → загрузка чека → модерация → активация (через Фазу 6).
- [x] `PaymentService.initiate` (Kaspi) → реквизиты (номер/имя) на фронт; валидирует
      тариф (`UnknownTariffError`) и способ (`UnsupportedMethodError`) → 400 в роутере
- [x] `POST /api/payments/proof` (multipart): подтверждаем приём чека юзеру (тем же send берём
      telegram `file_id`) → `PaymentRequest(PENDING)` → уведомляем админов → User→PENDING_REVIEW.
      Гейт: `image/*` + лимит 10 МБ. `PaymentService` переехал в REQUEST-scope (нужны репозитории)
- [x] `notifier.acknowledge_payment_proof` (чек юзеру + возврат file_id) +
      `send_payment_proof_to_admins` (фото + `moderation_keyboard` в админ-чат)
- [x] `PaymentModerationService.approve/reject` + тонкий `moderation.py`: callback
      `pay:approve|reject:<id>` → approve дёргает `SubscriptionService.activate` (грант — Фаза 6,
      не дублируем; идемпотентно — только PENDING), reject → REJECTED + User→EXPIRED + DM
- [x] Тест: одобрение чека → подписка активна (реальный `SubscriptionService` на фейках);
      отклонение → доступа нет; повторный клик не грантит дважды (`test_moderation_service.py`,
      `test_payment_service.py`)
- [ ] Ручная e2e: чек через Web App → модерация в админ-чате → подписка активна. Полноценно —
      через Web App (Фаза 9) или crafted initData + multipart к `/proof`.

## Фаза 8 — Оплата: Telegram Stars (авто-подписка) ✅ (код; ручная e2e — за Web App/Фазой 9)
**Цель:** нативная оплата цифрового контента + помесячная авто-подписка.
- [x] Сверено с докой Telegram (payments-stars): валюта `XTR`, `provider_token` пустой,
      `subscription_period` = 2592000 c (30 дней, единственное значение), amount XTR = звёзды без ×100
- [x] `TelegramStarsProvider.initiate`: `create_invoice_link(currency="XTR", provider_token="",
      subscription_period=... )`; recurring-тариф → подписка, разовый → обычный инвойс. `price_xtr`
      как данные тарифа (1_day=50, 1_month=250 — подкрутить в `domain/tariffs/catalog.py`)
- [x] Бот-хендлеры `bot/handlers/stars.py`: `pre_checkout_query` (валидация payload) +
      `successful_payment` → `StarsPaymentService.confirm` → `SubscriptionService.activate`
- [x] Stars в `payment_providers` (DI, с Bot) — без правок `PaymentService` (OCP);
      `StarsPaymentService` в REQUEST-scope
- [x] Авто-продление (recurring) для `1_month`: прилетает тем же `successful_payment`, `confirm`
      → `activate` продлевает от текущего срока (одна ветка для первого платежа и продления)
- [x] Тесты (8): `StarsPaymentService.confirm/resolve/parse` (6) + провайдер на фейковом Bot (2 —
      сверка XTR/provider_token/subscription_period/amount). `TariffOut` отдаёт `price_xtr` фронту
- [ ] Ручная e2e: реальная оплата Stars в Telegram → активация; авто-списание через 30 дней →
      продление. Полноценно — через Web App (Фаза 9, `WebApp.openInvoice`).

## Фаза 9 — Фронтенд: Web App (Telegram Mini App) ✅ (код + браузерная проверка 2026-07-04;
живая e2e внутри Telegram — за реальными initData/оплатой)
**Цель:** тёмный Netflix-style интерфейс. Каталог листают ВСЕ; подписка проверяется только
в момент «Көру». Дизайн обсуждён и зафиксирован 2026-06-30 (решения ниже).

### Зафиксированные решения (UX/UI)
- **UI-кит (решение 2026-07-04):** иконки — **`lucide-react`** (открытый ISC-набор; ставим его, а
  не эмодзи/дефолтные глифы). Шрифт — **Inter** (казахская кириллица). Компоненты — свои на Tailwind
  v4 дизайн-токенах (`@theme` в `web/src/index.css`), философия shadcn/ui (владеем кодом, без тяжёлой
  UI-библиотеки → лёгкий бандл). Анимации/полки — нативный CSS (scroll-snap, CSS-шторки,
  `prefers-reduced-motion`). Акцент/палитра меняются правкой токенов в одном месте.
- **Доступ:** каталог/поиск/карточка — свободны (только initData-авторизация, без `has_access`).
  Гейт подписки — ТОЛЬКО на «Көру»: фронт по `has_access` рисует на кнопке замок 🔒, но источник
  правды — сервер (`POST /play` → `403 no_access`).
- **Хэндофф видео (ключевое):** видео не играется в Mini App — `protect_content` шлёт его в чат
  с ботом (Фаза 5). Поэтому «Көру» → `POST /play` → при успехе показываем **модалку
  «🎬 Видео ботқа жіберілді — чаттан қараңыз» + кнопка «Жабу»** (кнопка вызывает `WebApp.close()`,
  юзер попадает в чат с ботом, где уже лежит видео). НЕ авто-закрытие — явное подтверждение.
- **Тема:** фиксированная тёмная брендовая (кинотеатр), НЕ подстройка под тему Telegram.
- **Язык UI:** казахский. Тайтлы — `title_kk` основным (+ `title_original` мелким).
- **Оплата:** в пэйволле первым/акцентным — **Kaspi** (ручной чек); Telegram Stars — вторым.
- **Постеры:** карусели — портрет 2:3 (полка), hero — ландшафт 16:9. Соотношение фиксируем на `/add`.

### Главный экран
- [x] Sticky topbar: логотип слева, профиль справа (Lucide `CircleUserRound` + статус-точка) —
      `components/TopBar.tsx`.
- [x] Поиск ОТДЕЛЬНОЙ строкой во всю ширину (дебаунс → `/movies/search?q=`) — `components/SearchBar.tsx`.
- [x] Hero-баннер сверху (одна новинка) — `components/Hero.tsx`. Пока портретный постер с кино-
      градиентом (ландшафт 16:9 появится, когда `/add` начнёт хранить landscape-арт).
- [x] Полки: hero + «Жаңа түскен» + ряды по категориям — `lib/catalog.ts:buildShelves`.
      «Танымал» (топ по рейтингу) отложен: на малом каталоге дублирует другие ряды (старт = Hero +
      «Жаңа» + категории; вернуть при росте каталога).
- [x] ⚠️ Маленький каталог: категорийный ряд рендерим только при ≥ N (=3) тайтлах — иначе дубли.
      Реализовано в `buildShelves` (проверено вживую: с 4 disney + 3 anime ряд «Аниме» появился).

### Карточка фильма + просмотр
- [x] Карточка (bottom sheet): постер, `title_kk` (+ `title_original`), год, рейтинг (Lucide `Star`),
      описание, категория; крупная «Көру» (замок `Lock`, если нет доступа) — `components/MovieSheet.tsx`.
- [x] «Көру» → `api.play(id)` (`POST /api/movies/{id}/play`): 200 → хэндофф-модалка + «Чатқа өту»
      (`WebApp.close()`); 403 → пэйволл-шторка; 404 → тост. Ветвление по `ApiError.status` в `App.tsx`.
      Оптимизация: при `!has_access` пэйволл открываем сразу, не тратя заведомо-403 запрос.
- [x] Заглушка `telegram.ts:watchMovie` (`switchInlineQuery`) убрана; путь просмотра — `api.play` в
      `App.handleWatch` + `components/HandoffModal.tsx`.

### Пэйволл (bottom sheet, 2 тарифа) — `components/Paywall.tsx`
- [x] Контекстная шторка снизу поверх карточки: заголовок ««X» көру үшін».
- [x] 2 тарифа из `/api/payments/tariffs`: `1_day` (349 ₸) и `1_month` (1899 ₸, бейдж «ЕҢ ТИІМДІ» +
      дробная цена ₸/күн через `lib/format.ts:perDay`). По умолчанию выбран `1_month` (recurring).
- [x] Способы оплаты: **Kaspi первым/акцентным** (`initiate` → реквизиты + копирование номера →
      `proof` (чек) → «10–15 мин ішінде тексереміз»), Telegram Stars вторым (`initiate` →
      `WebApp.openInvoice` → статус `paid`).
- [x] ~~Нативная `MainButton`~~ → вместо неё брендовые кнопки Kaspi/Stars в шторке: выбор из двух
      способов двумя явными кнопками понятнее, чем одна нативная (сознательное отступление от плана).

### Состояния пользователя
- [x] new / expired → листает всё, «Көру» открывает пэйволл (`has_access=false`).
- [x] pending_review → баннер сверху «Чек тексерілуде» (`components/StatusBanner.tsx`), «Көру» заблокирован.
- [x] active → профиль (Lucide `CircleUserRound`) со счётчиком «N күн қалды» + дата `expires_at`
      (`components/ProfileSheet.tsx`). Дата — вручную по казахским месяцам (`format.ts`, Intl kk-KZ
      в webview не отдаёт длинные месяцы — давал «M07»).

### Нативный Telegram + сборка
- [x] `expand()` + брендовые цвета шапки/фона при старте (`lib/telegram.ts:initWebApp`), единая
      `BackButton` на весь стек оверлеев (`hooks/useTelegramBackButton.ts`), `HapticFeedback` на тапах.
- [x] Скелетоны загрузки (`components/HomeSkeleton.tsx`, `ui/Skeleton.tsx`); пустые/ошибочные состояния
      (`components/States.tsx` — каталог пуст / поиск пуст / ошибка сети + «Қайталау»).
- [x] Доавторизация: `api.auth()` при старте (в `Promise.all` с каталогом/тарифами; сбой auth не
      роняет экран).
- [x] API-клиент `web/src/lib/api.ts`: `auth/movies/searchMovies/getMovie/play/tariffs/
      initiatePayment/submitProof` + типизированная `ApiError` (status+code).
- [x] Сборка `npm run build` зелёная (`tsc -b` strict + `vite build`, 71 КБ gzip). Отдача статики
      `web/dist` — за Фазой 10 (Nginx/StaticFiles); в dev — Vite-прокси `/api`+`/posters`.

## Фаза 10 — Прод
- [ ] aiogram webhook вместо polling; FastAPI-роут вебхука
- [ ] Nginx reverse-proxy (TLS, домен Web App, статика)
- [ ] Прод-конфиг compose, секреты, бэкапы БД
- [ ] CORS под реальный домен Web App

## Фаза 11 — Redis: скорость и устойчивость (сессии, кэш, rate-limit, локи)
**Цель:** снять нагрузку с БД и защитить API. Redis уже в стеке (`redis>=5.2`, `redis.asyncio`;
сервис в compose; `RedisConfig.dsn`), но код его пока НЕ использует — всё greenfield. Каждый концерн —
через свой порт (`application/ports/`) + Redis-адаптер (`infrastructure/cache/`); сервисы про Redis
не знают (DIP). Ключи — с префиксами (`session:`, `catalog:`, `ratelimit:`, `lock:`).

**Когда:** 11.1 (сессии) и 11.2 (кэш) — компаньоны Фазы 9 (фронт), тянутся параллельно с ней;
11.3 (rate-limit) и 11.4 (локи) — hardening, удобно с Фазой 10 (прод).

### 11.0 — Redis-фундамент
- [ ] `redis.asyncio`-клиент: APP-scoped DI-провайдер из `RedisConfig.dsn` (пул) + graceful close
      (по аналогии с движком БД); health-ping при старте API/бота.
- [ ] Пакет `infrastructure/cache/` (адаптеры) + порты `SessionStore`/`CatalogCache`/`RateLimiter`/
      `Lock` (мелкие, раздельные — ISP).
- [ ] Политика деградации при недоступном Redis (решить и задокументировать): сессии → фолбэк на
      initData; кэш → прямой запрос в БД; rate-limit/локи → fail-open. Не ронять запрос в 500.

### 11.1 — Сессионные токены (auth)
> ⚠️ Меняет решение «stateless initData, без JWT»: initData остаётся **bootstrap-ом** (HMAC 1 раз),
> далее — серверная сессия в Redis. Плюс: не верифицируем initData каждый клик, свой TTL. Минус:
> состояние на сервере (Redis нужен для auth). Сам по себе initData дёшев (одна HMAC-SHA256) — это
> про свой TTL/ревок сессии, а не про «дорого». initData не выкидываем: он — источник правды для входа.
- [ ] `POST /api/auth`: валидирует initData → `session_token = uuid4()` → Redis
      `session:<uuid> → {user_id, username}` c TTL 24 ч → вернуть токен фронту.
- [ ] `get_current_user` принимает `Authorization: <session_token>`: смотрит Redis (≈1 мс); промах/
      просрочка → 401 `session_expired` (фронт делает тихий повторный `auth()` по initData).
- [ ] Порт `SessionStore` (create/get/refresh/delete) + Redis-адаптер; DI.
- [ ] Web App: токен в `localStorage`, слать в `Authorization`; на 401 — прозрачный ре-auth.
- [ ] Токен — только идентификатор сессии (в нём нет данных доступа); ревок сессии при бане/отписке.

### 11.2 — Кэш каталога (cache-aside)
- [ ] Агрегированный `GET /api/v1/catalog` — главный экран (hero + карусели) одним ответом, чтобы
      фронт не дёргал `/movies` по каждой полке.
- [ ] Cache-aside: `GET catalog:main` → есть → отдать; нет → собрать из БД → `SET catalog:main <json>
      EX 600` (10 мин) → отдать. Порт `CatalogCache` (get/set/invalidate) + адаптер.
- [ ] ⚠️ **Инвалидация на `/add`**: ingest нового фильма → `invalidate(catalog:main)`, иначе новинка
      не видна до 10 мин (а авто-рассылка Фазы 12 уже зовёт на неё). Не забыть — ключевой момент.
- [ ] Кэшируем только JSON; постеры — статика (Nginx/StaticFiles), их не трогаем.

### 11.3 — Rate limiter (защита API от выкачки/спама)
- [ ] Порт `RateLimiter` + Redis-адаптер: fixed-window `INCR ratelimit:<user_id>`; при первом —
      `EXPIRE 1`; счётчик > N → `429 too_many_requests`. Старт ~5 rps/юзер (данные, подкрутить).
- [ ] FastAPI-зависимость/middleware; ключ — user из сессии (до auth — по IP как фолбэк).
- [ ] Статику постеров не лимитируем; на тяжёлые ручки (`/play`, `/proof`) — отдельные лимиты.
- [ ] Заметка: fixed-window допускает всплеск на стыке окон — для MVP ок; при нужде → sliding.

### 11.4 — Лок отправки видео (анти-двойной-клик)
- [ ] Порт `Lock` + Redis-адаптер: `SET lock:send_video:<user_id> 1 EX 3 NX`. Есть ключ → тихо
      игнорируем повторный `/play` (юзер жмёт кнопку 20 раз на плохом инете); нет → шлём видео.
- [ ] Встроить в путь `/play` → перед `PlaybackService.deliver` (или внутри). Лок снимается по TTL.
- [ ] Тест: два быстрых `/play` подряд → одна отправка (фейковый Lock).

## Фаза 12 — Рассылки и уведомления о новинках
**Цель:** уведомлять юзеров о новом фильме, не ловя флуд-бан Telegram (~30 msg/s), уважая выбор
юзера (вкл/выкл уведомлений). Зависит от Redis-фундамента (Фаза 11.0) — очередь на Redis.

### 12.0 — Очередь рассылок (фоновый worker, crash-safe)
- [ ] Порт `BroadcastQueue` (enqueue батча получателей + прогресс) + Redis-адаптер. Хранилище —
      Redis List/Stream; **устойчивость к падению**: обрабатываемые id не теряются до подтверждения
      (reliable-queue: Stream + consumer group, либо `LMOVE` в processing-лист). Упал воркер —
      прогресс остался в Redis.
- [ ] Отдельный процесс-worker (`app/worker.py` + сервис `worker` в compose): берёт ~25–30 id/с,
      шлёт через Bot API, `sleep(1)` между пачками (глобальный лимит Telegram).
- [ ] Библиотека: свой минимальный Redis-List worker (без новых зависимостей) ИЛИ `arq` (async-
      очередь на Redis, дружит с asyncio/aiogram лучше, чем sync-Celery). **Решить при старте фазы.**
- [ ] ⚠️ Реалии Telegram: ловить `RetryAfter` (спать `retry_after`), помечать заблокировавших бота
      (`bot blocked`/`chat not found`) неактивными и не ретраить их вечно.

### 12.1 — Настройка уведомлений юзером (opt-out, по умолчанию ВКЛ)
- [ ] `User.notifications_enabled: bool = True` (домен) + `UserModel` + миграция (default True,
      backfill существующих в True). Аудитория рассылки = юзеры с `notifications_enabled=True`.
- [ ] `PATCH /api/me/notifications {enabled: bool}` (гейт `get_current_user`) — правит флаг.
- [ ] Web App: тумблер в профиле (👤) «Жаңа фильмдер туралы хабарлау» (по умолчанию включён).

### 12.2 — Авто-уведомление о новинке (главный сценарий)
- [ ] По завершении `/add` (ingest) → поставить в `BroadcastQueue` рассылку по opted-in юзерам:
      постер + `title_kk` + краткое описание + кнопка «Көру ▸ ботта» (deep-link / Web App).
- [ ] Перед рассылкой — инвалидация кэша каталога (11.2), чтобы клик из уведомления показал новинку.
- [ ] Идемпотентность: один фильм не рассылать дважды (флаг «notified» у фильма / ключ в Redis).

### 12.3 — Ручная рассылка админом
- [ ] Триггер: бот-команда `/broadcast` (текст/медиа, только `BOT_ADMIN_USER_IDS`) или кнопка в
      будущей Mini App админки → кастомная рассылка в очередь.
- [ ] Подтверждение админу: «поставлено N получателей» + итог (отправлено / заблокировано).

### Тесты
- [ ] `BroadcastQueue` (enqueue/забор/подтверждение) на фейке; батчинг и пропуск заблокированных.
- [ ] Аудитория = только `notifications_enabled=True`; toggle-эндпоинт.

---

## Идеи на будущее (не в MVP)
- Лидерборды/реферальная программа.
- Mini App админки (чекбоксы категорий из справочника).
- Множественные каналы-архивы.
