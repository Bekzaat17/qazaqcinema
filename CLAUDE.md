# CLAUDE.md — гайд для будущих сессий

Этот файл — память проекта. Прочитай его первым, потом загляни в [PLAN.md](PLAN.md): там отмечено,
**где остановились и что делать дальше**.

## Что это
**QazaqCinema** — онлайн-кинотеатр (Netflix-style) внутри Telegram Web App: редкие мультфильмы
и аниме с казахской озвучкой. Видео лежит в приватном **канале-архиве** Telegram (бэкенд не
стримит тяжёлое видео), защита через `protect_content=True`, монетизация — подписка (Kaspi-чеки +
Telegram Stars). Контент наполняет админ через бот-визард `/add` (видео + постер + метаданные
пошагово); видео уходит в канал-архив, постеры — статикой на VPS.

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
    handlers/     # start, channel_post (автонаполнение), inline_query (подсказка-кнопка), moderation (✅/❌)
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

**Сделано (Фаза 3 — добавление фильмов):** мультиязычные названия (`title_kk/ru/original`) +
миграция `b7f3a9c2d1e4` (pg_trgm/unaccent/f_unaccent + GIN-trgm индексы, проверена на живой БД);
постеры статикой на VPS (`PosterStorage`/`LocalPosterStorage` + StaticFiles `/posters`);
`PgMovieRepository.search` (триграммы) + `CatalogService`; бот-визард `/add` (FSM, админ-гейт) →
`MovieIngestionService.ingest`. Зелёное: ruff + mypy + pytest(29).

**Сделано (Фаза 4 — каталог API):** 3 эндпоинта (`/api/movies`, `/search`, `/{id}`) +
`CatalogService` были готовы с Фазы 3; добавлен тест-страж `tests/test_movie_dto.py`
(«`telegram_file_id` не утекает в `MovieOut`»: нет поля в схеме + значение не появляется в JSON).
Чора: имена миграций → `yyyymmdd_<slug>` (`file_template` в `alembic.ini`; revision id не тронуты).
Зелёное: ruff + mypy(strict, `app`) + pytest(32).

**Проверено вживую (2026-06-29):** миграция применена на рабочей БД (head `b7f3a9c2d1e4`); визард
`/add` прогнан через @qazaqcinema_bot — фильм id=1 в БД, видео в канале-архиве (`protect_content`),
постер в `uploads/posters/`. Грабли: `BOT_ARCHIVE_CHANNEL_ID` должен быть `-100…` (без `-` →
«chat not found»), бот — админ канала. **Фазы 0–4 готовы и проверены вживую.**

**Сделано (Фаза 5 — защищённая выдача видео):** inline не умеет `protect_content` → видео шлёт бот
в личку через `send_protected_video` (`send_video(protect_content=True)`); триггер — `POST
/api/movies/{id}/play` (initData-гейт + `has_active_access`). Новый `PlaybackService` (+юнит-тесты),
порт `send_protected_video`, DI-провайдер `playback`. Inline стал подсказкой-кнопкой. pytest(35).

**Сделано (Фаза 6 — подписка и контроль доступа):** «движок доступа» ДО оплаты.
`SubscriptionService.activate(user, tariff, now)` (compute_expiry → ACTIVE + expires_at +
selected_tariff + DM на казахском) и `expire_due(now)` (просроченные ACTIVE → EXPIRED через
`list_expired`, возвращает кол-во); зависит только от `UserRepository` + `TelegramNotifier`.
apscheduler-джоб `expire_due` каждые 15 мин (REQUEST-scope контейнер `async with container()`),
старт/стоп в `main.py`. API-зависимость `require_active_access` (поверх `get_current_user`) → 403
`no_access`. **Тарифа теперь два** (решение пользователя): `1_day` (тестовый) + `1_month`;
`3_months` убран. Юнит-тесты `SubscriptionService` (5, фейки). Зелёное: ruff + mypy + pytest(40).

**Сделано (Фаза 7 — оплата Kaspi, ручной чек):** `PaymentService.initiate` (валидирует тариф/способ
→ инструкция `PaymentProvider`; `UnknownTariffError`/`UnsupportedMethodError` → 400) + `submit_proof`
(подтверждает приём чека юзеру и тем же send берёт telegram `file_id` → `PaymentRequest(PENDING)` →
уведомляет админов → юзер в `PENDING_REVIEW`). `PaymentModerationService.approve/reject`: approve
дёргает `SubscriptionService.activate` (грант — Фаза 6, не дублируем; идемпотентно — только PENDING,
повтор не грантит дважды), reject → `REJECTED` + юзер `EXPIRED` + DM. Тонкий `moderation.py`
(callback `pay:approve|reject:<id>` → сервис, правит подпись + снимает кнопки). API: `POST
/api/payments/{initiate,proof}` (proof — multipart, гейт `image/*` + лимит 10 МБ). Порт
`acknowledge_payment_proof` + `send_payment_proof_to_admins` (фото + `moderation_keyboard` в
админ-чат; нотифаер тянет клавиатуру из `bot/keyboards`, чтобы формат callback-data жил в одном
месте). DI: `PaymentService` → REQUEST-scope (нужны репозитории), добавлен `moderation`. Юнит-тесты
(9, фейки): PaymentService (5) + PaymentModerationService (4). Зелёное: ruff + mypy(78) + pytest(49).

**Не сделано — по приоритету (детали в PLAN.md):**
1. Оплата: Telegram Stars (инвойс `create_invoice_link(XTR)` + `pre_checkout`/`successful_payment` →
   `SubscriptionService.activate`, авто-подписка помесячно, Фаза 8). Регистрируется в
   `payment_providers` (DI) без правок сервисов. (Kaspi — Фаза 7, готова.)
2. Фронтенд: каталог/карусели, поиск, модалки, пэйволл (2 тарифа), кнопка «Көру» → `POST /play`,
   загрузка чека → `POST /proof`.
3. Прод: webhook + Nginx.
⚠️ Чоры (вне фаз): (a) `conftest` шьёт рабочую БД через `create_all` (дрейф схемы) — изолировать
тест-БД; (b) `confirm_add` без `try/except` — при ошибке зависает «⏳ Сақталуда…» без текста.

## Решения, которые уже приняты (не пересматривать без причины)
- **Python 3.13**. Backend — **FastAPI** (не Django/PHP): ложится на async-стек.
- **БД — PostgreSQL** (asyncpg + Alembic). ORM-модели отделены от доменных сущностей намеренно.
- `telegram_file_id` — **только боту**, в API-DTO отсутствует. Видео отдаётся ТОЛЬКО ботом через
  `send_video(protect_content=True)` (inline-результаты `protect_content` НЕ умеют — проверено на
  aiogram 3.29); API `/play` лишь триггерит отправку после initData-гейта. Это ядро безопасности.
- **Постеры — файлами на VPS** (не Telegram file_id/прокси): постер публичен (витрина), крошечный,
  нужен стабильный URL под `<img>`. Порт `PosterStorage` → `LocalPosterStorage` + StaticFiles
  `/posters`; видео остаётся в канале-архиве. Постер скачивается один раз при `/add`.
- **Названия фильма — мультиязычные**: `title_kk` (основное, казахское), `title_ru`,
  `title_original` (оба nullable). Фронт показывает казахское основным.
- **Поиск каталога — pg_trgm + unaccent** (не FTS): триграммы дают опечатки/подстроку и **работают
  для казахского** (у Postgres FTS нет казахского словаря). Immutable-обёртка `f_unaccent` (stock
  `unaccent` лишь STABLE → в индекс по выражению нельзя); один и тот же `f_unaccent` в запросе и в
  GIN-индексе, иначе индекс не используется.
- **Наполнение каталога — бот-визард `/add` (FSM)**, не подпись-#ключи; `caption_parser` — утилита.
- Тесты репозиториев идут через `create_all` (не миграции): conftest сам заводит `pg_trgm`/
  `unaccent`/`f_unaccent` и делает drop+create (иначе дрейф схемы от старых прогонов).
- Категория/статус/способ оплаты в БД — **VARCHAR**, не PG-ENUM (добавить значение без миграции).
- `users.telegram_id` и `payment_requests.user_id` — **BIGINT** без автоинкремента (Telegram ID).
- **Оплата — Strategy-порт** `PaymentProvider`: Kaspi (MVP, ручной чек) + Telegram Stars
  (авто-подписка, **только помесячная** по ограничению Telegram). **Тарифа два** (решение
  2026-06-29): `1_day` — разовый тестовый доступ; `1_month` — основной (`recurring=True`, пригоден
  под авто-подписку Stars). `3_months` убран. Менять сетку — `domain/tariffs/catalog.py` (данные).
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
- **Имена миграций — `yyyymmdd_<slug>`** (через `file_template` в alembic.ini). Случайный hex от
  Alembic — лишь уникальный `revision id` (по нему связи `down_revision`/`alembic_version`), дата в
  имени файла — для людей; id внутри файла при переименовании не трогаем.
- **Подписка — отдельный «движок доступа» ДО оплаты** (Фаза 6): `SubscriptionService.activate/
  expire_due` + `has_active_access` — единая точка грант/ревок/проверки. Способы оплаты (Kaspi/Stars)
  лишь вызывают `activate`; не размазывать активацию по платёжным хендлерам.
- **Фронтенд Mini App** (решения 2026-06-30, детали в PLAN.md Фаза 9): каталог/поиск/карточка —
  свободны всем (только initData), гейт подписки ТОЛЬКО на «Көру» (`POST /play` → 403). Видео не
  играется в Mini App (`protect_content`) → «Көру» шлёт его в чат с ботом, фронт показывает модалку
  «видео отправлено» + кнопка «Жабу» (`WebApp.close()`), НЕ авто-закрытие. Тема — фиксированная
  тёмная брендовая (не тема Telegram). Язык UI — казахский (`title_kk` основной). Пэйволл — bottom
  sheet, 2 тарифа, **Kaspi первым/акцентным**, Stars вторым. Постеры: полка 2:3, hero 16:9.
