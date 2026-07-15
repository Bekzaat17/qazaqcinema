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
- **aiogram 3.x** — бот. **Тумблер polling/webhook** по схеме `PUBLIC_ORIGIN` (http → polling локально;
  https → aiohttp-вебхук за Caddy в проде, Фаза 10)
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
  web (Caddy, авто-TLS); `test` — profile-gated; + `worker` — Фаза 12), отличие сред ТОЛЬКО в env-файле
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

## Состояние: MVP готов (Фазы 0–13 закрыты). Детали и что осталось — в [PLAN.md](PLAN.md)

Весь код готов и зелёный (`./start.sh test`: ruff + mypy(strict) + pytest в контейнере). Все 13 фаз
закрыты: каркас (SOLID) → БД+репозитории → авторизация (сессии поверх initData-bootstrap) →
добавление фильмов (бот-визард `/add`) → каталог+API → защищённая выдача видео (`protect_content`) →
подписка+контроль доступа → оплата (Kaspi ручной чек + Telegram Stars авто-подписка) → фронтенд Mini
App → прод-конфиг (webhook/TLS по env) → Redis (сессии/кэш/rate-limit/локи, все fail-open) → рассылки
(Redis-очередь + worker + opt-out) → каталог (браузинг по категориям + сортировка + таб-навигация).

**Осталось только живое** (не код, за пользователем): деплой на VPS по [DEPLOY.md](DEPLOY.md) (домен,
DNS, заполнить `PUBLIC_ORIGIN`=https://домен — Caddy сам выпустит TLS, webhook включится схемой) и e2e в Telegram (реальные initData/оплата/
рассылка/выдача видео на @qazaqcinema_bot). Юнит/интеграционные тесты и браузер-превью — зелёные.

⚠️ После правок схемы БД — миграция (`alembic upgrade head`, авто через сервис `migrate`); тест-БД при
смене схемы пересоздать (`dropdb qazaqcinema_test` → `./start.sh test`; `create_all` не добавляет
колонки в существующие таблицы).

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
- **Kaspi: способ перевода — по заполненности env** (решение 2026-07-11, «данные», не код): внутри
  Kaspi два независимых способа — **перевод по номеру** (`PAY_KASPI_NUMBER`) и **оплата по ссылке**
  Kaspi Pay (`PAY_KASPI_LINK`). Доступность выводится из ЗАПОЛНЕННОСТИ: пусто → `None` (`KaspiManual
  Provider.initiate`: `self._x or None`) → способ скрыт на пэйволле. Заданы оба → доступны оба (кнопка
  «Kaspi-ге өту» + карточка «Аудару нөмірі» с разделителем «немесе»); задан один — только он. Массива
  способов в env НЕТ намеренно — переключение = правка тех же строк, без нового флага и без кода.
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
- **Единый `PUBLIC_ORIGIN` — ОДИН источник правды для домена** (решение 2026-07-11, замена россыпи
  `BOT_WEBAPP_URL`/`BOT_WEBHOOK_URL`/`API_CORS_ORIGINS`/`WEB_SERVER_NAME`): в env домен пишется РАЗ,
  со схемой (`https://qazaqcinema.rehubpro.kz` прод / `http://localhost` локально). Из него
  `AppConfig._derive_from_public_origin` (валидатор pydantic, `settings.py`) выводит: `api.cors_origins`
  (= [origin]), `bot.webapp_url` (= origin+"/"), `bot.webhook_url` (= origin при https, иначе "").
  Схема — флаг среды: **https ⟹ TLS + webhook**, http ⟹ без TLS + polling (Telegram и так требует HTTPS
  для webhook). Та же переменная уходит в Caddy как site address (compose `environment:`). Поля
  `webapp_url`/`webhook_url`/`cors_origins` напрямую из env НЕ задаются — лишь хранилище результата.
- **Прод — авто-TLS через Caddy, webhook по env** (решение 2026-07-11, замена nginx+certbot): **web —
  один образ Caddy** (`web/Caddyfile` + `web/Dockerfile`), раздаёт SPA и проксирует `/api`,`/posters`,
  `/tg/`. **HTTPS полностью автоматический** — Caddy сам выпускает и продлевает сертификат Let's Encrypt
  (никакого `certbot`/cron/скриптов-селекторов; «курица-яйцо» и ручной выпуск сняты в принципе). Сертификаты
  живут в томе `caddy_data` (переживают пересборку/`git pull`). Дев/прод отличаются ТОЛЬКО значением
  `PUBLIC_ORIGIN` (http://localhost → HTTP :80; https://домен → авто-TLS :443 + редирект). **webhook** —
  включается схемой `https` в `PUBLIC_ORIGIN`; aiohttp-сервер вебхука живёт В процессе бота (не
  FastAPI-роут), чтобы бот сохранял владение диспетчером+шедулером, а api оставался чистым. Секреты
  приложения в Caddy-контейнер НЕ пробрасываем (только `PUBLIC_ORIGIN` + `ACME_EMAIL` через
  `environment:`, не `env_file`). `ACME_EMAIL` — контакт Let's Encrypt (dev/test = `test@testmail.com`,
  непустой намеренно: пустая env-строка ломает парсинг `email` в Caddyfile — проверено `caddy validate`).
  Бэкапы — `./start.sh backup` (`pg_dump|gzip`, ротация 14). Живой деплой — по **DEPLOY.md**.
- **Лимиты ресурсов и логов в compose** (решение 2026-07-11, под дешёвый VPS): у каждого сервиса
  `deploy.resources.limits.memory` (postgres 512М, api/bot 384М, worker/migrate 256М, redis 192М,
  web 128М) — потолки-ПРЕДОХРАНИТЕЛИ от разрастания, не резервирования; реальный простой ~900М.
  Логи — якорь `x-logging` (json-file, `max-size 10m` × `max-file 3` = ≤30М/сервис). Docker ротирует
  по РАЗМЕРУ, не по времени — «логи на 3 месяца» дословно невозможно, но при нашем трафике 30М это
  перекрывает с запасом. Целевой VPS — **2 ГБ RAM / 1–2 vCPU / ~40 ГБ SSD** (видео раздаёт Telegram
  через `protect_content`, не VPS → бэкенд лёгкий; тяжёлого трафика на сервере нет).
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
  различаем по `=`); токен непрозрачный, доступ всегда свежий из БД. **Кэш каталога (11.2/13):**
  cache-aside в namespace `catalog:*` — ключи `home` (EX 600), `categories` (EX 600), `browse:…`
  (EX 60; много комбинаций фильтр×сортировка×страница + дрейф сорта «по просмотрам» → короткий TTL).
  Порт `CatalogCache` — ключевой (`get(key)/set(key,payload,ttl)/invalidate`), namespace-префикс в
  адаптере; **инвалидация в `MovieIngestionService.ingest`** чистит ВЕСЬ namespace (`SCAN catalog:*`
  → `DEL`), иначе новинка не видна до TTL. Тесты кэш-адаптеров — на **fakeredis** (dev-зависимость).
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
- **Каталог/навигация (Фаза 13, 2026-07-06):** UI — **две вкладки через фиксированный нижний таб-бар**
  (`Басты | Каталог`), НЕ оверлей и НЕ кнопка (каталог — равноправная витрина; масштабируется под будущие
  вкладки). **Главная = hero + 2 полки** (Жаңа түскен + Танымал), категорийные ряды с главной убраны —
  браузинг по категориям живёт в табе «Каталог» (чипы-мультивыбор + сортировка + пагинация-подгрузка).
  **«Барлығы →» на полках главной НЕ показываем**: New/Popular — сортировки, а не категории, вести им
  некуда; вход во «весь каталог» — только таб. Правило: «Барлығы →» принадлежит КАТЕГОРИЙНЫМ рядам (если
  такие вернут на главную). **Популярность = счётчик просмотров `play_count`** (не рейтинг, не ручной
  флаг): `+1` на реальной доставке видео; «Танымал»/сорт-по-просмотрам — `ORDER BY play_count DESC,
  rating DESC NULLS LAST, id DESC` (холодный старт сам падает на рейтинг→новизну — полка не пустеет).
  **Вся выборка/лимит/сортировка — на бэке** (ответ `/home` = O(полки×14), не растёт с каталогом; сорт —
  Literal-белый-список, сырой строки в SQL нет, тай-брейк `id DESC`). Пагинация — подгрузка-при-скролле
  (не нумерация); карусели остаются нативным scroll-snap (бесконечный JS-луп отклонён — принцип «без
  JS-каруселей»).
- **Имена миграций — `yyyymmdd_<slug>`** (через `file_template` в alembic.ini). Случайный hex от
  Alembic — лишь уникальный `revision id` (по нему связи `down_revision`/`alembic_version`), дата в
  имени файла — для людей; id внутри файла при переименовании не трогаем.
- **Подписка — отдельный «движок доступа» ДО оплаты** (Фаза 6): `SubscriptionService.activate/
  expire_due` + `has_active_access` — единая точка грант/ревок/проверки. Способы оплаты (Kaspi/Stars)
  лишь вызывают `activate`; не размазывать активацию по платёжным хендлерам.
  **Доступ пропадает НЕ по джобу**: `has_active_access` считает `expires_at > now` в реальном времени
  на каждом запросе → 403 приходит секунда-в-секунду. `expire_due` (15 мин) лишь проставляет статус,
  шлёт DM и забирает видео — «бесплатных 15 минут» не бывает.
- **Выданные видео живут 40 часов, чистка ПО ВОЗРАСТУ** (решение 2026-07-15, `VideoRetentionService`):
  ⚠️ **Telegram не даёт боту удалить сообщение старше 48 часов** (Bot API `deleteMessage`, проверено по
  доке). Поэтому исходная схема «удалим всё при истечении подписки» на месячном тарифе физически НЕ
  работала: к 30-му дню почти все выдачи неудаляемы, юзер оставался с коллекцией навсегда — а `suppress`
  в адаптере делал провал невидимым (ошибка «>48 ч» выглядела как успех). Решение: ежечасный джоб
  `purge_stale` сносит выдачи старше `STALE_AFTER=40 ч` (запас 8 ч до потолка на случай простоя джоба).
  Побочно чинится и `purge_for_user` при истечении: в таблице теперь НЕТ ничего старше ~41 ч → удаление
  всегда попадает в окно. Для подписчика не потеря: подписка жива → жмёт «Көру» и получает видео снова.
  Чистка идёт ПАЧКАМИ (`list_stale(cutoff, BATCH_SIZE=100)` в цикле) — в память попадает одна пачка.
  **Строки удаляются независимо от ответа Telegram** — это условие завершения цикла: оставленная строка
  вернулась бы следующим `list_stale` и зациклила джоб. Отказ логирует адаптер (`delete_message → bool`,
  не молчит). Флуд-лимит (`RetryAfter`) переживает АДАПТЕР (пауза+повтор) — `aiogram` в `application/`
  не протекает. Менять срок/пачку — данные в `video_retention_service.py`.
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
  фронт на своём origin, CORS не нужен (прод — Caddy, Фаза 10). Вне Telegram в DEV работает мок
  бэкенда `web/src/lib/devMock.ts` (динамический import под `import.meta.env.DEV && !initData` →
  из прод-бандла вырезается) — можно открыть Mini App в браузере без бэка; статус юзера в моке
  переключается константой `AUTH.status`.
