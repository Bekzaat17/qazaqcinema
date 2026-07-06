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
- **aiogram 3.x** — бот. **Тумблер polling/webhook** по `BOT_WEBHOOK_URL` (пусто → polling локально;
  задан → aiohttp-вебхук за Nginx в проде, Фаза 10)
- **FastAPI** — API для Web App
- **SQLAlchemy 2.0 async + asyncpg + Alembic** — PostgreSQL
- **dishka** — DI-контейнер (composition root)
- **apscheduler** — фоновые задачи (сброс просроченных подписок)
- **redis (`redis.asyncio`)** — клиент в DI (APP-scope, graceful close) + health-ping + `GET /api/health`.
  **Фазы 11 и 12 закрыты:** сессии (`SessionStore`), кэш каталога (`CatalogCache`), rate-limit, локи,
  **очередь рассылок (`BroadcastQueue`, Фаза 12)** — мелкие порты `application/ports/` + адаптеры
  `infrastructure/cache/`, все **fail-open** (Redis down ничего не роняет: сессии→initData-фолбэк,
  кэш→прямая БД, rate-limit/локи→пропускают, рассылка→enqueue no-op). Очередь — reliable Redis-list
  (crash-safe, at-least-once), разбирает отдельный `worker`-процесс (`app/worker.py`).
- **React 19 + Vite 6 + TypeScript + Tailwind v4** — Web App (`web/`)
- **UI-кит фронта:** иконки — **`lucide-react`** (открытый ISC-набор; единственный источник иконок,
  эмодзи-заглушки заменены на векторные); шрифт — **Inter** (Google Fonts, покрывает казахскую
  кириллицу ә/ғ/қ/ң/ө/ұ/ү/і); компоненты — свои на Tailwind-токенах (философия shadcn/ui, без
  тяжёлой рантайм-библиотеки → лёгкий бандл для мобильной сети); анимации/карусели — нативный CSS
  (scroll-snap, CSS-шторки; уважают `prefers-reduced-motion`)
- **Docker Compose** — **одна топология** для dev/prod/test (postgres, redis, `migrate`, api, bot,
  web/nginx; `certbot`+`test` — profile-gated; + `worker` — Фаза 12), отличие сред ТОЛЬКО в env-файле
  (12-factor; TLS/webhook — тоже по env). Единый запуск — **`./start.sh`** (всё в Docker; тесты — тоже
  в контейнере, образ-стадия `test`; `./start.sh backup` — дамп БД)

## Архитектура: Clean / Hexagonal + DDD-lite
Принцип: **домен не знает про aiogram/FastAPI/Postgres**. Зависимости направлены внутрь (DIP).
Bot и API — два «presentation»-входа, оба тонкие: достать данные → делегировать сервису → отдать ответ.

```
app/
  bot/            # Presentation #1. ТОЛЬКО здесь импортируется aiogram
    handlers/     # start, add_movie (визард /add), broadcast (/broadcast), inline_query, moderation (✅/❌), stars (оплата)
    keyboards/    # webapp-кнопка, клавиатура модерации
  api/            # Presentation #2. FastAPI
    routers/      # auth (initData), catalog (фильмы), payments (тарифы/чек), me (тумблер рассылок), health
    schemas/      # pydantic DTO — БЕЗ telegram_file_id наружу
    deps/         # auth: get_current_user + require_active_access (initData-гейт)
  domain/         # Ядро. Без внешних зависимостей. POPO + dataclass
    entities/     # Movie, User (+ has_active_access), PaymentRequest, enums
    tariffs/      # Tariff (VO) + catalog.py (тарифная сетка как данные)
    parsing/      # caption_parser (чистая функция #title… → ParsedMovie)
    catalog/      # справочник категорий (данные, не enum)
    subscription/ # expiry.compute_expiry (чистый расчёт срока)
    registry.py   # generic Registry[T] (PEP 695) — задел для slug-плагинов
  application/    # Use-cases
    ports/        # Protocol-интерфейсы: repositories, payments, telegram, security, broadcast  ← границы DIP/ISP
    services/     # Auth, Catalog, MovieIngestion, Subscription, Payment, Broadcast — зависят ТОЛЬКО от портов
  infrastructure/ # Адаптеры (реализации портов)
    db/           # models (ORM) + engine + repositories (мапят ORM↔domain)
    telegram/     # init_data (HMAC-валидатор) + notifier (поверх aiogram Bot)
    payments/     # kaspi (ручная), stars (Telegram Stars) — реализации PaymentProvider
    cache/        # Redis-адаптеры: session, catalog, lock, rate_limiter, broadcast (все fail-open)
    di/           # providers.py — composition root (dishka)
    scheduler.py  # apscheduler
  config/         # pydantic-settings, load_config()
  main.py         # сборка контейнера, polling/webhook
  worker.py       # процесс-worker рассылок (Redis-очередь → Bot API, Фаза 12)
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
| Reliable-queue (Redis) + worker | `application/ports/broadcast.py` ↔ `infrastructure/cache/broadcast.py`, `app/worker.py` |
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
./start.sh                       # локально: весь стек в Docker (env=.env), миграции авто
./start.sh prod                  # ТЕ ЖЕ контейнеры, env=.env.prod (отличие сред — только env-файл)
./start.sh test                  # ruff+mypy+pytest В КОНТЕЙНЕРЕ (env=.env.test, БД qazaqcinema_test)
./start.sh logs / ps / down / migrate    # логи / статус / стоп (--clean стирает тома) / миграции
# Web → http://localhost/  |  API/docs → :8000/docs  |  health → :8000/api/health

# Гранулярно на хосте (нужен .venv; для hot-reload подними в Docker только postgres+redis):
.venv/bin/pytest                 # тесты домена (без БД); интеграционные — нужен postgres
.venv/bin/ruff check app tests   # линт
.venv/bin/mypy app               # типы (strict)
.venv/bin/alembic upgrade head   # применить миграции (offline DDL: + --sql)
.venv/bin/uvicorn app.api.app:app --reload   # API с автоперезагрузкой (host-venv)
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

**Сделано (Фаза 8 — оплата Telegram Stars, авто-подписка):** `TelegramStarsProvider.initiate` →
`bot.create_invoice_link(currency="XTR", provider_token="", subscription_period=2592000 для
recurring)` — помесячный тариф уходит подпиской, разовый (`1_day`) обычным инвойсом. Бот-хендлеры
`bot/handlers/stars.py`: `pre_checkout_query` (быстрая in-memory валидация payload, лимит ~10 c) +
`successful_payment` → `StarsPaymentService.confirm` (запись `PaymentRequest(STARS, APPROVED,
external_charge_id)` + грант через `SubscriptionService.activate`; авто-продление recurring —
тем же путём, продлевает от текущего срока). Тариф получил `price_xtr` (данные: 1_day=50, 1_month=250),
`TariffOut` отдаёт его фронту. Payload `<user_id>:<slug>` (`build_payload` в провайдере ↔
`parse_payload` в сервисе). DI: Stars в `payment_providers` (с Bot), `StarsPaymentService` (REQUEST).
Константы Stars сверены с докой Telegram (payments-stars). Юнит-тесты (8): сервис (6) + провайдер на
фейковом Bot (2). Зелёное: ruff + mypy(80) + pytest(57). **Оба способа оплаты (Kaspi + Stars) готовы.**

**Сделано (Фаза 9 — фронтенд Mini App):** тёмный кино-UI на React 19 + Tailwind v4. **UI-кит:**
иконки `lucide-react` (эмодзи-заглушки заменены), шрифт Inter, свои компоненты на дизайн-токенах
(`web/src/index.css` → `@theme`: `bg/surface/brand/gold/kaspi/star`…), нативные CSS-анимации/
scroll-snap-полки. Экраны: sticky topbar (лого + профиль со статус-точкой), поиск отдельной строкой
(дебаунс → `/movies/search`), hero-баннер, полки (`buildShelves`: hero + «Жаңа түскен» + ряды
категорий с порогом ≥3 против дублей на малом каталоге). Оверлеи (bottom-sheet + единая нативная
`BackButton` на весь стек): карточка фильма, пэйволл (2 тарифа, `1_ай` акцент + «ең тиімді»/₸-в-күн,
**Kaspi первым** → реквизиты+копирование+загрузка чека, Stars вторым → `WebApp.openInvoice`),
профиль (статус подписки: «N күн қалды»/pending/жазылу), хэндофф-модалка «видео ботқа жіберілді» →
`WebApp.close()`. Полный API-клиент (`auth/movies/searchMovies/getMovie/play/tariffs/initiate/proof`)
с типизированной `ApiError` (ветвление 403→пэйволл, 404→тост). SDK-обёртка: `expand`, брендовые
цвета, `HapticFeedback`, `BackButton`, `openInvoice`. Dev-прокси Vite (`/api`+`/posters` → :8000,
без CORS). DEV-мок бэкенда (`lib/devMock.ts`, вне Telegram; из прод-бандла вырезан). Проверено в
браузере (mobile-viewport): все экраны/потоки. Зелёное: `tsc -b` (strict) + `vite build` (71 КБ gzip).
Осталась живая e2e внутри Telegram (реальные initData/оплата) — разблокирует e2e фаз 5–8.

**Сделано (пост-Фаза 9 — хардненинг + фичи, 2026-07-04):** ревью после готовности фронта.
**Security:** (1) админ-гейт на модерацию оплат — `pay:approve/reject` проверяют `is_admin`
(раньше в группе-админчате чек мог одобрить любой участник; общий `app/bot/security.py`, на него же
переведён `/add`); (2) TTL на initData — `TelegramInitDataVerifier` сверяет `auth_date` (24 ч) после
HMAC → реплей украденного initData отсекается. **Категории:** плоско расширены (+`film/serial/
otandyq/kids`, данные, без миграции) + зеркало на фронте. **Постер:** порт `ImageProcessor`
(`ports/images.py` + `infrastructure/images/pillow.py`) — Pillow приводит постер к 2:3, hero-баннер
к 3:2, пере-кодирует в JPEG, битую картинку → `ValueError`. **Hero:** `is_featured` +
`hero_image_url` (миграция `a1b2c3d4e5f6`); выбор hero — на бэке (`MovieRepository.get_hero`:
`is_featured DESC, id DESC` → `GET /api/movies/hero`); визард `/add` спрашивает «на главную?» +
горизонтальный баннер; `confirm_add` обёрнут в try/except. Фронт: `Hero.tsx` — широкий баннер 3:2,
`buildShelves(movies, heroId)`. Зелёное: ruff + mypy(83) + pytest(69) + web build + браузер-превью.
⚠️ Миграцию применить на живой БД: `alembic upgrade head`.

**Сделано (инфра/DevEx — единый `./start.sh` + Redis-фундамент, 2026-07-04/05):** весь стек в Docker,
**одна топология для dev/prod/test — отличие ТОЛЬКО в env-файле** (12-factor; решение пользователя
2026-07-05: убраны dev/prod-оверлеи, dev==prod). `./start.sh {dev|prod|test|logs|ps|down|migrate}`:
`dev`→`.env`, `prod`→`.env.prod`, `test`→`.env.test` — те же контейнеры (postgres, redis, `migrate`,
api, bot, web-nginx :80). Порты БД/Redis/API — на 127.0.0.1 (хосту доступны, наружу нет). Миграции —
сервис `migrate` ПЕРЕД api/bot; `uploads/` — том. **Тесты — в контейнере** (мультистейдж-образ, стадия
`test`): `./start.sh test` гоняет ruff+mypy+pytest против postgres в изолированной `qazaqcinema_test`
(footgun «тесты в рабочей БД» закрыт). Hot-reload (когда нужен) — host-venv поверх Docker-инфры
(README). **Redis подключён** (Фаза 11.0): клиент в DI (APP-scope, graceful `aclose`), health-ping на
старте api/bot (fail-open), `GET /api/health` (`{redis,db,status}`). Проверено вживую: `./start.sh
test` зелёный (ruff+mypy(84)+pytest(69) в контейнере), web-образ nginx собран, `/api/health` →
`{"redis":"ok","db":"ok","status":"ok"}`. Файлы: `start.sh`, `docker-compose.yml` (единый), `Dockerfile`
(мультистейдж runtime/test), `web/{Dockerfile,nginx.conf}`, `.env.{test,prod.example}`, `.dockerignore`;
Redis — `api/routers/health.py` + провайдер в `di/providers.py` + ping в `api/app.py`/`main.py`.

**Сделано (Фаза 11.3 + 11.4 — Redis-хардненинг: локи + rate-limit, 2026-07-05):** первый инкремент
Фазы 11, чистый бэкенд (фронт не тронут). Заложен паттерн порт+Redis-адаптер: пакет
`app/infrastructure/cache/` + порты `application/ports/{lock,rate_limit}.py`; оба адаптера **fail-open**
(Redis недоступен → пропускаем, основной сценарий не роняем — деградация живёт в адаптере, сервис про
неё не знает). **11.4 Лок отправки видео:** порт `Lock` → `RedisLock` (`SET lock:<key> 1 EX ttl NX`,
release по TTL), встроен в `PlaybackService.deliver` перед отправкой; ключ `send_video:<user>:<movie>`
→ повторный `/play` в 3-сек окне = тихий no-op, но возвращает **DELIVERED** (фронт показывает ту же
модалку, а не ошибку). **11.3 Rate limiter:** порт `RateLimiter` → `RedisRateLimiter` (фиксированное
окно, атомарно `SET NX EX`+`INCR` в пайплайне — TTL один раз на окно, нет «залипшего» счётчика без
TTL); FastAPI-зависимость-фабрика `api/deps/rate_limit.py` (ключ — IP из `X-Forwarded-For` за Nginx,
фолбэк `request.client`; пер-юзер-ключ придёт с сессиями 11.1). Лимиты (данные, в роутерах): каталог
100/10с на IP (роутер-уровень `/api/movies`, покрывает и `/play`), `/initiate` 20/60с, `/proof`
15/300с. DI: `Lock`/`RateLimiter` — APP-scope стейтлес-обёртки над Redis. Тесты (13): адаптеры на
**fakeredis** (реальная SET NX / окно + fail-open на стабе), зависимость (429 + ключ по XFF),
анти-двойной-клик в PlaybackService. Зелёное: ruff + mypy(90) + pytest(79 в контейнере). Проверено
вживую против реального Redis (лок True/False, окно T/T/T/F, TTL=60). ⚠️ Новая dev-зависимость
`fakeredis`.

**Сделано (Фаза 11.1 + 11.2 — сессии + кэш каталога, 2026-07-05): ФАЗА 11 ЗАКРЫТА.** Бэк + фронт.
**11.1 Сессии:** initData → bootstrap (HMAC 1 раз) → серверная сессия `session:<uuid4().hex>` (Redis,
`{user_id,username}`, TTL 24 ч; порт `SessionStore` + `RedisSessionStore`, fail-open). `POST /api/auth`
отдаёт токен в `AuthOut.token` (nullable — Redis down → None). `get_current_user` стал **двухрежимным**
(`api/deps/auth.py`): Authorization с `=` → initData (stateless HMAC, Redis не нужен — **fail-open
фолбэк**); без `=` → session-токен → Redis → свежий User из БД (статус/срок — правда там). Промах →
401 `session_expired`, битый initData → 401 `invalid_init_data`. Обе ветки безопасны (токен неугадываем,
initData — HMAC). ⚠️ Изменено решение «stateless initData»: теперь initData — bootstrap+фолбэк, а не
каждый-клик. Фронт (`lib/api.ts`): токен в `localStorage`, `authHeader()`=токен??initData, на 401 —
прозрачный ре-auth по initData + повтор ОДИН раз (`refreshSession` дедуплицирует параллельные 401,
bootstrap с `retried:true` против рекурсии). **11.2 Кэш:** агрегированный `GET /api/movies/home`
(`{hero,movies}` одним ответом, `CatalogHomeOut`) — cache-aside `catalog:main` EX 600 (порт
`CatalogCache` + `RedisCatalogCache`, fail-open, на хите — сырой JSON `Response` без пересериализации);
**инвалидация в `MovieIngestionService.ingest`** после `add` (новинка видна сразу). Фронт: `api.home()`
в `load()` вместо `movies()`+`hero()`; DEV-мок отдаёт `/api/movies/home`. Тесты (+11): `test_auth_dep`
(двухрежим 4), `test_catalog_home` (cache-aside 2, +страж file_id), `test_cache` (session/catalog
адаптеры на fakeredis + fail-open, 5), `test_ingestion_service` (invalidate на ingest). Зелёное: ruff +
mypy(94) + pytest(90 в контейнере) + web build (71 КБ gzip) + браузер-превью (главная из `/home`) +
живой Redis (сессия TTL 86400, кэш TTL 600). Осталась живая e2e в Telegram (реальные initData/токен).

**Сделано (Фаза 10 — прод: webhook + TLS + бэкапы, 2026-07-05): код/конфиг готовы, живой деплой — по
[DEPLOY.md](DEPLOY.md).** Всё через env, локаль (polling+:80) не тронута. **Webhook:** тумблер по
`BOT_WEBHOOK_URL` (пусто → polling); реализация — aiohttp-сервер вебхука В процессе бота
(`app/main.py`: `SimpleRequestHandler`+`setup_application`+`set_webhook`), а НЕ FastAPI-роут (бот
сохраняет владение диспетчером+шедулером; api не трогаем). Nginx `/tg/`→`bot:8080`, секрет-токен
заголовка валидирует aiogram. Config `BOT_WEBHOOK_{URL,PATH,SECRET,PORT}`. **Nginx TLS:** один образ,
TLS по env (`WEB_TLS`/`WEB_SERVER_NAME`); entrypoint-скрипт `web/nginx/40-qc-config.sh` рендерит
http.conf (:80) или https.conf.template (:443, envsubst только домена — nginx-vars не трогает).
**Автофолбэк** `WEB_TLS=true` без сертификата → HTTP :80 (обслуживает ACME) — снимает «курица-яйцо».
Сервис `certbot` (profile) для выпуска/продления; certs — bind-mount `./certbot/`. **Бэкапы:**
`./start.sh backup` (`pg_dump|gzip`, ротация 14, cron). **CORS/секреты:** `API_CORS_ORIGINS`→домен
(в проде всё same-origin за nginx), `.env.prod.example` дополнен, `certbot/`+`backups/` в .gitignore.
Проверено: ruff+mypy(94)+pytest(85) + `nginx -t` (http / tls-с-сертом / tls-без-серта→фолбэк) +
`compose config` (local false / prod true) + web-образ собран. ⚠️ Живые шаги (DNS, certbot certonly,
webhook) — на VPS по DEPLOY.md; домена пока нет.

**Сделано (Фаза 12 — рассылки + уведомления о новинках, 2026-07-06): ПОСЛЕДНЯЯ КРУПНАЯ ФАЗА ЗАКРЫТА.**
Бэк + фронт. **Библиотека (план флагнул «решить при старте»):** свой минимальный Redis-list reliable-
queue, БЕЗ новой зависимости (паттерн `infrastructure/cache/`, философия проекта; arq отклонён).
**Очередь (12.0):** порт `BroadcastQueue` (`ports/broadcast.py`: enqueue/reserve/ack/recover +
`BroadcastMessage`/`BroadcastJob`) → `RedisBroadcastQueue` — Redis List `broadcast:pending`, **crash-safe**
(reserve=`LMOVE` в `broadcast:processing`, не теряется до `ack`=`LREM`; `recover` при старте возвращает
незавершённые → at-least-once), payload `broadcast:msg:<uuid>` EX 24ч, **fail-open** (Redis down →
enqueue 0, /add не падает). **Worker (`app/worker.py`, сервис `worker` в compose):** `reserve(25)`→шлёт→
`ack` ПОСЛЕ отправки, `sleep(1)`/пачку (~25 msg/s < лимит TG); `RetryAfter`→пауза+повтор, `Forbidden/
BadRequest`→`set_notifications(False)`. Порт `TelegramNotifier.send_broadcast` (фото+web_app-кнопка /
текст; фолбэк на текст, если TG не забрал постер по URL). **Opt-out (12.1):** `User.notifications_enabled`
(домен+ORM+миграция `c7e8f9a0b1c2`, server_default true→backfill); **инвариант: `upsert` НЕ трогает флаг**
(не в on_conflict set_) — меняет только `set_notifications` (точечный UPDATE); `list_notifiable()` —
аудитория; `PATCH /api/me/notifications` + `AuthOut.notifications_enabled`; фронт — тумблер в профиле
(колокол+switch, оптимистичный, откат при ошибке). **Авто-новинка (12.2):** `MovieIngestionService.ingest`
→ `BroadcastService.notify_new_movie` в try/except (сбой рассылки не роняет добавление; кэш уже инвалидирован
11.2). **Ручная (12.3):** бот `/broadcast` (админ-гейт, FSM текст→подтверждение→`broadcast_custom`).
`BroadcastService` (REQUEST, webapp_url примитивом в DI, как kaspi у провайдера). Тесты (+16): очередь на
fakeredis (7), сервис (4), нотификатор (3), worker `_deliver` (2), repo-инвариант (2). Зелёное в контейнере:
**ruff + mypy(100) + pytest(110, 0 скипов)** + web build (71.9 КБ gzip) + браузер-превью (тумблер true↔false).
⚠️ На живой БД: `alembic upgrade head` (авто в `./start.sh` через `migrate`). **ВСЕ 12 ФАЗ ГОТОВЫ.**

**Сделано (Ревью пост-Фаза 12 — хардненинг перед продом, 2026-07-06):** полное ревью проекта
(бэк+фронт), глубина «устойчивость+чистота» (без рискового перфа). Код признан здоровым — правки
точечные. **Устойчивость (P1):** (1) worker `_deliver` — транзиентные сбои (`TelegramNetworkError`/
`ServerError`, они ⊂ `TelegramAPIError`) больше не теряются: один повтор; ветка после `RetryAfter`
теперь тоже снимает заблокировавших с рассылок; (2) `/play` при недоступном получателе (не открыл чат
с ботом) → адаптер ловит Telegram `Forbidden`/«chat not found» → доменное `RecipientUnreachableError`
→ `PlaybackOutcome.BOT_BLOCKED` → **409 `bot_unreachable`** (не 500), фронт показывает «Алдымен ботпен
чатты ашыңыз»; (3) инвариант **РОВНО ОДИН worker** зафиксирован в docstring очереди + comment в compose
(reliable-queue single-consumer: `recover` при 2+ репликах утащит чужие in-flight → дубли). **Чистота
(P2):** `reserve` резолвит payload один раз на `mid` (не N GET на пачку); `set_notifications` — точечный
`UPDATE` (без загрузки строки); rate-limit на `PATCH /api/me/notifications` (30/60с); `PosterStorage.save`
— убран мёртвый/небезопасный `ext` (постер всегда JPEG после `ImageProcessor`); удалён мёртвый фронт-
экспорт `openBotChat`; освежены устаревшие комментарии. Зелёное в контейнере: **ruff + mypy(100) +
pytest(114, +4)** + web build (71.9 КБ gzip).

**Сделано (Ревью пост-Фаза 12 — изоляция тест-БД была СЛОМАНА, починена, 2026-07-06):** ревизия вскрыла,
что «изоляция БД тестов» (заявленная закрытой 2026-07-04) **не работала**: `docker compose run` (путь
`./start.sh test`) НЕ применяет `env_file`, только `environment:` → в тест-контейнере `DB_NAME` дефолтил
в рабочую `qazaqcinema`, и `./start.sh test` втихую сносил рабочие данные (этим же conftest-ом я и
затёр локальную БД в этой сессии). **Фикс в три слоя:** (1) `docker-compose.yml` — `DB_NAME:
qazaqcinema_test` задан ЯВНО в `environment:` тест-сервиса; (2) `conftest` — предохранитель
`_require_test_db()`: рушить/чистить только БД на `_test`, иначе тест СКИПается (хостовый `pytest` по
рабочей БД больше не вайпает — проверено: 9 skip); (3) **убран `drop_all`** (просьба пользователя) —
`create_all` идемпотентен, данные чистит `TRUNCATE`. ⚠️ При смене схемы пересоздать тест-БД
(`dropdb qazaqcinema_test` → `./start.sh test`; `create_all` не добавляет колонки в существующие
таблицы). Проверено: `./start.sh test` = 114 passed по изолированной `_test`-БД, рабочая не тронута.

**Не сделано — по приоритету (детали в PLAN.md):**
1. Прод (Фаза 10): ✅ **код/конфиг готовы** (webhook-тумблер, nginx TLS по env + автофолбэк, бэкапы,
   CORS, DEPLOY.md). Осталось живое (на VPS, за пользователем): DNS, `certbot certonly`, живой webhook.
2. Redis (Фаза 11): ✅ **ЗАКРЫТА ВСЯ** — фундамент (11.0) + сессии (11.1) + кэш каталога (11.2) +
   rate-limit (11.3) + локи (11.4). Порты `application/ports/` + адаптеры `infrastructure/cache/`,
   все fail-open. Осталась только живая e2e в Telegram (реальные initData/токен).
3. Рассылки (Фаза 12): ✅ **ЗАКРЫТА ВСЯ** — очередь+worker (12.0), opt-out+тумблер (12.1), авто-новинка
   (12.2), ручной `/broadcast` (12.3). Reliable Redis-list, fail-open, свой worker (без arq). Осталась
   только живая e2e в Telegram (реальная рассылка на аудитории).
⚠️ Чоры (вне фаз): (a) ✅ исправлено (2026-07-04): `./start.sh test` гонит pytest в ИЗОЛИРОВАННОЙ
`qazaqcinema_test` (env-override `DB_NAME` через `.env.test`) — рабочую БД не трогает; сам `conftest`
по-прежнему `drop/create` по своей `DatabaseConfig().dsn`, но теперь это тест-БД; (b) ✅ исправлено
(2026-07-04): `confirm_add` обёрнут в try/except — при ошибке внятный текст вместо зависшего
«⏳ Сақталуда…».

## Решения, которые уже приняты (не пересматривать без причины)
- **Python 3.13**. Backend — **FastAPI** (не Django/PHP): ложится на async-стек.
- **БД — PostgreSQL** (asyncpg + Alembic). ORM-модели отделены от доменных сущностей намеренно.
- `telegram_file_id` — **только боту**, в API-DTO отсутствует. Видео отдаётся ТОЛЬКО ботом через
  `send_video(protect_content=True)` (inline-результаты `protect_content` НЕ умеют — проверено на
  aiogram 3.29); API `/play` лишь триггерит отправку после initData-гейта. Это ядро безопасности.
- **Постеры — файлами на VPS** (не Telegram file_id/прокси): постер публичен (витрина), крошечный,
  нужен стабильный URL под `<img>`. Порт `PosterStorage` → `LocalPosterStorage` + StaticFiles
  `/posters`; видео остаётся в канале-архиве. Постер скачивается один раз при `/add`.
- **Изображения — нормализуются через порт `ImageProcessor`** (Pillow-адаптер, решение 2026-07-04):
  постер → 2:3, hero-баннер → 3:2, пере-кодирование в JPEG (`ImageOps.fit`); битая картинка →
  `ValueError` (ловит визард). Размеры/качество — данные (`POSTER`/`HERO` в `ports/images.py`).
- **Hero главной — курируется, не наугад** (решение 2026-07-04): флаг `is_featured` (ставится в
  `/add`) + отдельный горизонтальный баннер `hero_image_url`; выбор делает бэкенд
  (`get_hero`: свежайший featured → фолбэк новизна), фронт лишь рендерит `GET /api/movies/hero`.
- **initData — с TTL** (решение 2026-07-04): HMAC + проверка `auth_date` (24 ч) против реплея;
  модерация оплат — под явным админ-гейтом (`app/bot/security.is_admin`, не только видимость кнопок).
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
- **Telegram Stars — сверенные константы** (Фаза 8, docs `core.telegram.org/bots/payments-stars`):
  валюта `currency="XTR"`; `provider_token=""` (для Stars пусто); `amount` в XTR = число звёзд
  напрямую (XTR без дробной части, не ×100); `subscription_period=2592000` (30 дней) — единственный
  допустимый период Stars-подписки. **Цена в звёздах — данные тарифа** `price_xtr` (1_day=50,
  1_month=250; бизнес-значения, подкрутить в `domain/tariffs/catalog.py`). Активация — только на
  `successful_payment` (не на `initiate`): `StarsPaymentService.confirm` → `SubscriptionService.
  activate`; авто-продление recurring идёт тем же хендлером. Payload `<user_id>:<slug>`.
- **Заявки на оплату** — единая таблица `payment_requests` (аудит), универсальная по способу:
  `proof_file_id` для Kaspi, `external_charge_id` для Stars/фиата.
- **Авторизация Web App — сессии поверх initData-bootstrap** (Фаза 11.1, 2026-07-05; ранее было
  «stateless initData на каждый запрос»): initData валидируется HMAC один раз в `POST /api/auth` →
  серверная сессия в Redis (`session:<uuid>`, TTL 24 ч) → клиент шлёт токен. `get_current_user` —
  **двухрежимный**: токен (Redis) ИЛИ initData (stateless-фолбэк, различаем по `=` в строке). initData
  НЕ выкинут — он bootstrap И fail-open фолбэк (Redis down → вход по HMAC работает). JWT по-прежнему нет
  (токен — непрозрачный id сессии, данных доступа в нём нет; статус/срок всегда свежие из БД).
- **Тарифы/категории — данные** (словарь), не классы; способы оплаты/ключи парсера — код (OCP).
- **DI — dishka**, composition root в `infrastructure/di/providers.py`. APP-scope: config, движок,
  Bot, провайдеры оплаты; REQUEST-scope: сессия БД, репозитории, сервисы.
- Каждая секция конфига объявляет свой `env_file=".env"` и `env_prefix` (вложенные BaseSettings
  через `default_factory` НЕ наследуют env_file родителя). Списки из env — через `NoDecode` +
  валидатор (иначе pydantic-settings пытается JSON-декодить).
- Alembic берёт DSN из `DatabaseConfig` (для миграций BOT_TOKEN не нужен); переопределение
  `alembic -x dsn=...`.
- **Единый запуск + dev/prod-паритет — `./start.sh` (решение 2026-07-04, уточнено 2026-07-05):** весь
  стек в Docker, **ОДНА топология** (единый `docker-compose.yml`, без оверлеев) — dev/prod/test
  отличаются ТОЛЬКО env-файлом (`.env`/`.env.prod`/`.env.test`; 12-factor, решение пользователя).
  Порты БД/Redis/API — на 127.0.0.1 (одинаково везде). Миграции — сервис `migrate` ПЕРЕД api/bot.
  `ENV_FILE` + `--env-file` управляют и `env_file:` сервисов, и интерполяцией `${...}`. **Тесты — в
  контейнере** (мультистейдж-образ, стадия `test`), БД `qazaqcinema_test` (footgun «тесты в рабочей БД»
  закрыт). Hot-reload — не в контейнере (dev==prod), а host-venv поверх Docker-инфры (README).
- **Прод (Фаза 10) — webhook/TLS тоже по env, не оверлеями** (2026-07-05): **webhook** — тумблер
  `BOT_WEBHOOK_URL` (пусто → polling); aiohttp-сервер вебхука живёт В процессе бота (не FastAPI-роут),
  чтобы бот сохранял владение диспетчером+шедулером, а api оставался чистым. **TLS** — один web-образ,
  `WEB_TLS`/`WEB_SERVER_NAME` из env; entrypoint-скрипт `web/nginx/40-qc-config.sh` выбирает http/https
  конфиг, envsubst подставляет ТОЛЬКО домен (nginx-переменные не трогает — явный список). **Автофолбэк**
  на HTTP, если `WEB_TLS=true`, но сертификата ещё нет (обслуживает ACME → «курица-яйцо» снята). certs —
  bind-mount `./certbot/`, сервис `certbot` под profile. Секреты в nginx-контейнер НЕ пробрасываем
  (только `WEB_TLS`/`WEB_SERVER_NAME` через `environment:`, не `env_file`). Бэкапы — `./start.sh backup`
  (`pg_dump|gzip`, ротация 14). Живой деплой — по **DEPLOY.md**.
- **Redis подключён как фундамент (Фаза 11.0, 2026-07-05):** клиент `redis.asyncio` в DI (APP-scope,
  graceful `aclose`), health-ping на старте api/bot (**fail-open** — недоступность Redis не роняет
  старт), `GET /api/health` пингует Redis+БД. Фичи (сессии/кэш/rate-limit/локи) — поверх этого через
  свои порты+адаптеры (Фаза 11.1+), сервисы про Redis не знают (DIP).
- **Redis-фичи — fail-open + адаптер владеет ключами** (Фаза 11, 2026-07-05): каждый концерн —
  мелкий порт (`Lock`, `RateLimiter`, `SessionStore`, `CatalogCache`; ISP) + адаптер в
  `infrastructure/cache/`. **Деградация — в адаптере**: Redis недоступен → лок/лимитер пропускают
  (`acquire`/`hit` → True), кэш → промах (`get` → None), сессии → None (клиент откатывается на initData) —
  чтобы Redis не ронял основной путь (лучше повторная отправка/пропуск лимита/сбор из БД, чем отказ).
  Namespace-префиксы (`lock:`, `ratelimit:`, `session:`, `catalog:`) — в адаптере, домен их не знает.
  Лок отправки видео живёт ВНУТРИ `PlaybackService.deliver` (не в роутере — «не двойным клиентом», а
  самим use-case'ом), ключ `send_video:<user>:<movie>`, release по TTL. Rate-limit — FastAPI-зависимость
  (`api/deps/rate_limit.py`), ключ по IP из `X-Forwarded-For`; лимиты — данные в роутерах. **Сессии
  (11.1):** initData → bootstrap → токен; `get_current_user` двухрежимный (токен ИЛИ initData-фолбэк,
  различаем по `=`); токен непрозрачный, доступ всегда свежий из БД. **Кэш каталога (11.2):**
  cache-aside `catalog:main` EX 600 за агрегированным `GET /api/movies/home`, **инвалидация в
  `MovieIngestionService.ingest`** (иначе новинка не видна до TTL). Тесты кэш-адаптеров — на
  **fakeredis** (dev-зависимость), не на живом Redis (тот в `./start.sh test` не поднимается).
- **Рассылки — свой Redis-list reliable-queue + отдельный worker, БЕЗ arq** (Фаза 12, 2026-07-06):
  план флагнул «arq vs своё» — выбрали своё (нет новой зависимости, ровно паттерн `infrastructure/
  cache/` порт+адаптер, философия проекта). Очередь `BroadcastQueue` (`broadcast:pending` List) —
  **crash-safe**: `reserve`=`LMOVE` в `broadcast:processing` (задание не теряется до `ack`=`LREM`),
  `recover` при старте возвращает незавершённые (**at-least-once**: `ack` идёт ПОСЛЕ отправки → лучше
  повтор, чем потеря). Payload — раз на рассылку (`broadcast:msg:<uuid>` EX 24ч), задания хранят лишь
  `{mid,chat}`. **Fail-open** (Redis down → enqueue no-op, /add не падает). Разбирает **отдельный
  процесс** `app/worker.py` (сервис `worker` в compose) — глобальный лимит Telegram (~25 msg/s) в ОДНОМ
  месте, не блокирует бота/API. Реалии TG: `RetryAfter`→пауза+повтор, `Forbidden/BadRequest`→снять с
  рассылок. **Opt-out `notifications_enabled`** (по умолчанию ВКЛ): инвариант — `upsert` НЕ трогает флаг
  (не в on_conflict set_), меняет только точечный `set_notifications` (логин/оплата не сбрасывают выбор).
  Авто-новинка — в `ingest` (try/except, не роняет добавление); ручная — бот `/broadcast` (админ-гейт).
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
  sheet, 2 тарифа, **Kaspi первым/акцентным**, Stars вторым. Постеры: полка 2:3, hero 3:2
  (горизонталь под мобилку — решение 2026-07-04, не 16:9).
- **UI-кит фронта (решение 2026-07-04):** иконки — **`lucide-react`** (открытый ISC-набор; ставим ЕГО,
  а не эмодзи/дефолтные глифы — единый источник иконок). Шрифт — **Inter** (Google Fonts; критично —
  покрывает казахскую кириллицу, т.к. все тайтлы `title_kk`). Компоненты — **свои** на Tailwind v4
  дизайн-токенах (`@theme` в `web/src/index.css`), философия shadcn/ui: владеем кодом, без тяжёлой
  рантайм-UI-библиотеки → лёгкий бандл для мобильной сети. Анимации/карусели — **нативный CSS**
  (scroll-snap-полки, CSS-шторки; `prefers-reduced-motion`), без JS-каруселей. Менять акцент/палитру —
  правкой токенов в `@theme` (одно место).
- **Dev-инфра фронта:** Vite-прокси `/api`+`/posters` → бэкенд (`API_TARGET` — env-переменная в
  `web/vite.config.ts`; в Docker-dev `http://api:8000`, на хосте `http://localhost:8000`) →
  фронт на своём origin, CORS не нужен (прод — Nginx, Фаза 10). Вне Telegram в DEV работает мок
  бэкенда `web/src/lib/devMock.ts` (динамический import под `import.meta.env.DEV && !initData` →
  из прод-бандла вырезается) — можно открыть Mini App в браузере без бэка; статус юзера в моке
  переключается константой `AUTH.status`.
