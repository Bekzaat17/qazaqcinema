# PLAN.md — дорожная карта QazaqCinema

Рабочий план по фазам. Каждая сессия: открыть этот файл → найти **ТЕКУЩУЮ ПОЗИЦИЮ** →
сделать следующие невыполненные шаги → отметить `[x]` → подвинуть маркер.

**Definition of Done для любой фазы:** `ruff check app tests`, `mypy app`, `pytest` — зелёные;
новое поведение покрыто тестом (где применимо).

---

## 📍 ТЕКУЩАЯ ПОЗИЦИЯ
**Ревью пост-Фаза 12 — хардненинг перед продом (2026-07-06):** полное ревью бэк+фронт (глубина
«устойчивость+чистота», без рискового перфа); код здоров, правки точечные. **P1:** worker не теряет
сообщения на транзиентных сбоях (1 повтор) + retry-ветка снимает заблокировавших; `/play` при
недоступном боте → **409 `bot_unreachable`** (доменное `RecipientUnreachableError`, не 500; фронт просит
открыть бота); инвариант **РОВНО ОДИН worker** задокументирован (очередь single-consumer). **P2:**
`reserve` дедупит payload по `mid`; `set_notifications` точечным `UPDATE`; rate-limit на
`/api/me/notifications`; `PosterStorage.save` без `ext` (всегда JPEG); удалён мёртвый `openBotChat`;
освежены комментарии. Зелёное: **ruff + mypy(100) + pytest(114, +4)** в контейнере + web build (71.9 КБ
gzip). ⚠️ Грабли: БД-тесты гонять только через `./start.sh test` (прямой pytest бьёт по рабочей БД —
conftest drop/create). Дальше → живой прод (Фаза 10: DNS/certbot/webhook на VPS) / живая e2e в Telegram.

**Фаза 12 ЗАВЕРШЕНА — рассылки + уведомления о новинках (2026-07-06): ПОСЛЕДНЯЯ КРУПНАЯ ФАЗА
ЗАКРЫТА.** Бэк + фронт. **Библиотека (план флагнул «решить при старте»):** свой минимальный
Redis-list reliable-queue, БЕЗ новой зависимости (паттерн `infrastructure/cache/`, философия проекта).
**12.0 Очередь+worker:** порт `BroadcastQueue` + `RedisBroadcastQueue` (Redis List `broadcast:pending`
→ LMOVE в `broadcast:processing` → LREM ack → recover; payload `broadcast:msg:<uuid>` EX 24ч; **fail-open**
— Redis down → enqueue 0, /add не падает). Отдельный процесс `app/worker.py` (сервис `worker` в compose):
`recover()` при старте, `reserve(25)`→шлёт→`ack` (at-least-once, ack ПОСЛЕ отправки), `sleep(1)`/пачку
(~25 msg/s < лимит TG). Реалии TG: `RetryAfter`→пауза+повтор; `Forbidden/BadRequest`→снять с рассылок
(`set_notifications False`). Порт `TelegramNotifier.send_broadcast` (фото+кнопка / текст; фолбэк на текст,
если TG не забрал постер по URL). **12.1 Opt-out:** `User.notifications_enabled` (домен+ORM+миграция
`c7e8f9a0b1c2`, server_default true → backfill); **инвариант: upsert НЕ трогает флаг** (не в on_conflict
set_), меняет только `set_notifications` (точечный UPDATE); `list_notifiable()` — аудитория. `PATCH
/api/me/notifications` + `AuthOut.notifications_enabled`. Фронт: тумблер в профиле (колокол + switch,
оптимистично, откат при ошибке). **12.2 Авто-новинка:** `MovieIngestionService.ingest` → `BroadcastService.
notify_new_movie` (в try/except — сбой рассылки не роняет добавление; кэш уже инвалидирован 11.2).
**12.3 Ручная:** бот `/broadcast` (админ-гейт, FSM текст→подтверждение→`broadcast_custom`). `BroadcastService`
(REQUEST, webapp_url примитивом в DI). Тесты (+16): очередь на fakeredis (7, roundtrip/batch/ack-recover/
payload-expire/fail-open), сервис (4, аудитория/контент/URL/тумблер), нотификатор (3, фото/текст/фолбэк),
worker `_deliver` (2, успех/пометка заблокированного), repo (2, list_notifiable+инвариант upsert). Зелёное
в контейнере: **ruff + mypy(100) + pytest(110, 0 скипов)** + web build (71.9 КБ gzip) + браузер-превью
(тумблер true↔false). ⚠️ На живой БД: `alembic upgrade head` (авто в `./start.sh` через сервис `migrate`).
Осталась только живая e2e в Telegram. **ВСЕ 12 ФАЗ ГОТОВЫ.** Дальше → добить Фазу 10 (DNS/certbot/webhook
на VPS) + живой прогон в Telegram (реальные initData/оплата/рассылка) — за пользователем.

**Фаза 10 — код/конфиг прода готовы (2026-07-05):** всё параметризовано через env, локаль
(`./start.sh` = polling + :80) не тронута; живой деплой — по [DEPLOY.md](DEPLOY.md) (домена пока нет).
**Webhook:** тумблер по `BOT_WEBHOOK_URL` (пусто → polling); aiohttp-сервер вебхука В процессе бота
(`app/main.py`: `SimpleRequestHandler`+`setup_application`), Nginx проксирует `/tg/`→`bot:8080`, секрет-
токен валидирует aiogram. **Nginx TLS:** один образ, TLS по env (`WEB_TLS`/`WEB_SERVER_NAME`); entrypoint
`web/nginx/40-qc-config.sh` выбирает http/https-конфиг, **автофолбэк** `WEB_TLS=true` без серта → HTTP
(обслуживает ACME → снимает «курица-яйцо»); сервис `certbot` (profile). **Бэкапы:** `./start.sh backup`
(`pg_dump|gzip`, ротация 14). **CORS/секреты:** `API_CORS_ORIGINS`→домен, `.env.prod.example` дополнен
(webhook/TLS), `certbot/`+`backups/` в .gitignore. **DEPLOY.md** — пошаговый чеклист. Проверено: ruff +
mypy(94) + pytest(85) + `nginx -t` (http / tls-с-сертом / tls-без-серта→http-фолбэк) + `compose config`
(local WEB_TLS=false / prod true) + web-образ собран. Осталось (за пользователем на VPS): DNS, `certbot
certonly`, живой webhook. Дальше → **Фаза 12** (рассылки + уведомления) — последняя крупная.

**Фаза 11 ЗАВЕРШЕНА — 11.1 сессии + 11.2 кэш каталога (2026-07-05):** добили Redis-фазу (бэк + фронт).
**11.1 Сессии:** initData → bootstrap (HMAC 1 раз) → серверная сессия `session:<uuid>` (Redis, TTL 24 ч,
порт `SessionStore`+`RedisSessionStore`, fail-open). `POST /api/auth` отдаёт токен в `AuthOut.token`
(nullable). `get_current_user` стал **двухрежимным**: Authorization с `=` → initData (stateless HMAC —
**фолбэк без Redis**), без `=` → session-токен → Redis → свежий User из БД. Фронт (`lib/api.ts`): токен
в `localStorage`, `authHeader()`=токен??initData, на 401 — прозрачный ре-auth (дедуп параллельных).
**11.2 Кэш:** агрегированный `GET /api/movies/home` (`{hero,movies}` одним ответом, `CatalogHomeOut`) —
cache-aside `catalog:main` EX 600 (порт `CatalogCache`+`RedisCatalogCache`, fail-open, сырой JSON
`Response` на хите); **инвалидация в `MovieIngestionService.ingest`** (новинка видна сразу). Фронт:
`api.home()` в `load()` вместо `movies()`+`hero()`. Тесты (+11): `test_auth_dep` (двухрежим, 4),
`test_catalog_home` (cache-aside, 2), `test_cache` (session+catalog адаптеры на fakeredis +fail-open, 5).
Зелёное: ruff + mypy(94) + pytest(90 в контейнере / 83+7-скипа локально) + web build (71 КБ gzip) +
браузер-превью (главная из `/home`) + живой Redis (сессия TTL 86400, кэш TTL 600). Осталась живая e2e в
Telegram (реальные initData/токен). Дальше → **Фаза 12** (рассылки+уведомления) или добить **Фазу 10** (webhook+TLS+домен).

**Фаза 11.3 + 11.4 — Redis-хардненинг: локи + rate-limit (2026-07-05):** первый инкремент Фазы 11,
чистый бэкенд (фронт не тронут). **Паттерн порт+Redis-адаптер заложен:** пакет `app/infrastructure/
cache/` + порты `application/ports/{lock,rate_limit}.py`; оба адаптера **fail-open** (Redis down →
пропускаем, основной сценарий не роняем). **11.4 Лок отправки видео:** порт `Lock` → `RedisLock`
(`SET lock:send_video:<user>:<movie> 1 EX 3 NX`), встроен в `PlaybackService.deliver` перед отправкой →
повторный `/play` в окне = тихий no-op (тот же DELIVERED, фронт видит ту же модалку, не ошибку).
**11.3 Rate limiter:** порт `RateLimiter` → `RedisRateLimiter` (фиксированное окно, атомарно
`SET NX EX`+`INCR` пайплайном — без «залипшего» счётчика); FastAPI-зависимость-фабрика
`api/deps/rate_limit.py` (ключ — IP из `X-Forwarded-For`; пер-юзер придёт с сессиями 11.1). Лимиты
(данные): каталог 100/10с на IP (роутер-уровень, покрывает `/play`), `/initiate` 20/60с, `/proof`
15/300с. DI: `Lock`/`RateLimiter` — APP-scope обёртки над Redis. Тесты (13): адаптеры на **fakeredis**
(реальная SET NX / окно) + fail-open на стабе + зависимость 429 + анти-двойной-клик в PlaybackService.
Зелёное: ruff + mypy(90) + pytest(79 в контейнере / 72+7-скипа локально). Проверено вживую против
реального Redis (лок True/False, окно T/T/T/F, TTL=60). Дальше по Фазе 11 → **11.1 сессии** + **11.2
кэш каталога** (оба тронут фронт: localStorage-токен + ре-auth; агрегированный `/catalog` + инвалидация).

**Инфра/DevEx — dev/prod-паритет + Redis-фундамент (2026-07-04/05):** весь стек в Docker, **ОДНА
топология — dev/prod/test отличаются ТОЛЬКО env-файлом** (12-factor; решение пользователя 2026-07-05:
убраны dev/prod-оверлеи → единый `docker-compose.yml`). `./start.sh` (`.env`) / `prod` (`.env.prod`) /
`test` (`.env.test`) / `logs` / `ps` / `down` [`--clean`] / `migrate`. Контейнеры: postgres, redis,
`migrate` (авто `alembic upgrade head` ПЕРЕД api/bot), api, bot, web (nginx :80 — статика +
прокси `/api`+`/posters`); порты БД/Redis/API — на 127.0.0.1. **Тесты — в контейнере** (мультистейдж-
образ, стадия `test`): ruff+mypy+pytest в изолированной `qazaqcinema_test` (footgun «тесты в рабочей
БД» закрыт). **Redis подключён** (Фаза 11.0): клиент в DI (APP-scope, graceful `aclose`) + health-ping
api/bot (fail-open) + `GET /api/health`. Hot-reload — host-venv поверх Docker-инфры (README).
Проверено: `./start.sh test` зелёный (ruff+mypy(84)+pytest(69) в контейнере), web-образ nginx собран,
`/api/health`→`{"redis":"ok","db":"ok","status":"ok"}`. Файлы: `start.sh`, единый `docker-compose.yml`,
мультистейдж `Dockerfile`, `web/{Dockerfile,nginx.conf}`, `.env.{test,prod.example}`, `.dockerignore`,
`api/routers/health.py`. Живой `./start.sh` (стартует реального бота) — за пользователем.
Дальше → живой e2e в Telegram / Redis-фичи (11.1+) / добить Фазу 10 (webhook + TLS + домен).

**Пост-Фаза 9 — хардненинг + фичи (2026-07-04):** ревью после готовности фронта закрыл забытые
куски. **Security:** админ-гейт на модерацию оплат (`is_admin`, `app/bot/security.py`) + TTL на
initData (`auth_date`, 24 ч). **Категории** расширены плоско (+`film/serial/otandyq/kids`, без
миграции). **Постер** валидируется/нормализуется через порт `ImageProcessor` (Pillow → 2:3/JPEG,
битый → `ValueError`). **Hero** курируется: `is_featured` + горизонтальный баннер `hero_image_url`
(миграция `a1b2c3d4e5f6`), выбор на бэке (`get_hero` → `GET /api/movies/hero`), визард `/add`
спрашивает «на главную?»+баннер, `confirm_add` в try/except (закрыт footgun). Фронт: широкий hero
3:2, `buildShelves(movies, heroId)`. Зелёное: ruff + mypy(83) + pytest(69) + web build + браузер-
превью + миграция offline. ⚠️ На живой БД: `alembic upgrade head`. Ранее удалён мёртвый
`channel_post`. Дальше → **Фаза 10 (прод)** / живая e2e в Telegram (фазы 5–8).

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
- [x] **Изоляция БД тестов от рабочей** (footgun 2026-06-29; «закрытие» 2026-07-04 оказалось
      НЕПОЛНЫМ; по-настоящему закрыто 2026-07-06). Суть: `conftest` рушил/чистил БД по
      `DatabaseConfig().dsn`. Ревизия 2026-07-06 вскрыла, что изоляция НЕ работала: `docker compose
      run` (путь `./start.sh test`) **не применяет `env_file`**, только `environment:` → в тест-
      контейнере `DB_NAME` дефолтил в `qazaqcinema` (рабочая!), и `./start.sh test` втихую сносил
      рабочие данные. **Настоящий фикс (три слоя):** (1) `docker-compose.yml` — `DB_NAME:
      qazaqcinema_test` задан ЯВНО в `environment:` тест-сервиса (не через env_file); (2) `conftest`
      — предохранитель `_require_test_db()`: рушить/чистить можно ТОЛЬКО БД на `_test`, иначе тест
      пропускается (любой хостовый `pytest` по рабочей БД теперь СКИПается, а не вайпает); (3)
      **убран `drop_all`** (по просьбе пользователя): `create_all` идемпотентен, данные между
      тестами чистит `TRUNCATE`. ⚠️ Следствие: при смене схемы тест-БД `qazaqcinema_test` надо
      пересоздать (`dropdb qazaqcinema_test` → `./start.sh test`), т.к. `create_all` не добавляет
      колонки в существующие таблицы. Проверено: `./start.sh test` = 114 passed по `_test`-БД,
      рабочая `qazaqcinema` не тронута.
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
- [x] **Удалён мёртвый `channel_post`-скелет** (чистка хвостов, 2026-07-04). Хендлер
      `@channel_post(F.video)` с Фазы 0 только `return` — автонаполнение каталога из канала
      отменено в пользу визарда `/add` (решение в CLAUDE.md), т.е. код был заведомо dead.
      Удалён `app/bot/handlers/channel_post.py` + снят из `bot/setup.py`; попутно поправлены
      устаревшие строки CLAUDE.md (список handlers + `deps/` уже не TODO). Зелёное: ruff +
      mypy(79) + pytest(57) + import-смоук (bot.setup/main/api.app).

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
- [x] Бот: роутеры (start✓, inline_query, moderation), `setup.py` (`channel_post`-скелет позже
      удалён — см. Чоры; `add_movie`/`stars` добавлены в Фазах 3/8)
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

## Фаза 10 — Прод ✅ код/конфиг готовы (2026-07-05); живой деплой — по [DEPLOY.md](DEPLOY.md)
> База была готова с 2026-07-04. Добито 2026-07-05: всё параметризовано через env, локаль
> (polling+:80) не тронута. Живые шаги (DNS, certbot, set_webhook) — на VPS по DEPLOY.md.
- [x] aiogram **webhook вместо polling** — тумблер по `BOT_WEBHOOK_URL` (пусто → polling). Реализация:
      aiohttp-сервер вебхука В процессе бота (`SimpleRequestHandler`+`setup_application`, `app/main.py`),
      а НЕ FastAPI-роут — так бот сохраняет владение диспетчером+шедулером, api не трогаем. Nginx
      проксирует `/tg/` → `bot:8080`. Секрет-токен заголовка валидирует aiogram. Config:
      `BOT_WEBHOOK_{URL,PATH,SECRET,PORT}`.
- [x] **Nginx TLS + домен** — один образ, TLS переключается env (`WEB_TLS`/`WEB_SERVER_NAME`);
      entrypoint-скрипт `web/nginx/40-qc-config.sh` выбирает http.conf (:80) или https.conf.template
      (:443, envsubst домена). **Автофолбэк**: `WEB_TLS=true` без сертификата → HTTP :80 (обслуживает
      ACME) — снимает «курица-яйцо». Сервис `certbot` (profile) для выпуска/продления. Проверено
      `nginx -t`: http / tls-с-сертом / tls-без-серта→http.
- [x] Прод-конфиг compose + отдача статики `web/dist` (nginx) — единый `docker-compose.yml`.
- [x] Секреты (`.env.prod` вне git — шаблон дополнен webhook/TLS) + **бэкапы БД** (`./start.sh backup`
      — `pg_dump|gzip`, ротация 14, cron в DEPLOY.md; `certbot/`+`backups/` в .gitignore).
- [x] CORS под домен — `API_CORS_ORIGINS` (env; в проде всё равно same-origin за nginx); шаблон → домен.
- [x] **DEPLOY.md** — пошаговый чеклист вывода в прод (DNS → секреты → certbot → webhook → бэкапы → продление).

## Фаза 11 — Redis: скорость и устойчивость (сессии, кэш, rate-limit, локи) ✅ (2026-07-05)
**Цель:** снять нагрузку с БД и защитить API. Redis в стеке (`redis>=5.2`, `redis.asyncio`;
`RedisConfig.dsn`); **фундамент 11.0 готов** (клиент в DI + health-ping + `GET /api/health`), фичи —
greenfield. Каждый концерн — через свой порт (`application/ports/`) + Redis-адаптер
(`infrastructure/cache/`); сервисы про Redis не знают (DIP). Ключи — с префиксами (`session:`,
`catalog:`, `ratelimit:`, `lock:`).

**Когда:** 11.1 (сессии) и 11.2 (кэш) — компаньоны Фазы 9 (фронт), тянутся параллельно с ней;
11.3 (rate-limit) и 11.4 (локи) — hardening, удобно с Фазой 10 (прод).

### 11.0 — Redis-фундамент
- [x] `redis.asyncio`-клиент: APP-scoped DI-провайдер из `RedisConfig.dsn` + graceful `aclose`
      (async-генератор в `di/providers.py`); health-ping при старте API (`api/app.py` lifespan) и
      бота (`main.py`) — fail-open. Бонус: `GET /api/health` (`api/routers/health.py`) пингует
      Redis+БД → `{redis,db,status}`. Проверено вживую (2026-07-05): `{"redis":"ok","db":"ok"}`.
- [x] Пакет `infrastructure/cache/` (адаптеры) + порты `SessionStore`/`CatalogCache`/`RateLimiter`/
      `Lock` (мелкие, раздельные — ISP). Все четыре готовы (11.1–11.4).
- [x] Политика деградации — вся **fail-open**: health-ping; rate-limit/локи → пропускают; сессии →
      initData-фолбэк (двухрежимный `get_current_user`); кэш → прямой сбор из БД. Redis down не роняет ничего.

### 11.1 — Сессионные токены (auth) ✅ (2026-07-05)
> ⚠️ Изменено решение «stateless initData, без JWT»: initData остался **bootstrap-ом** (HMAC 1 раз),
> далее — серверная сессия в Redis. initData НЕ выкинут — он и bootstrap, и **fail-open фолбэк**.
- [x] `POST /api/auth`: валидирует initData → `SessionStore.create` (`session:<uuid4().hex>` →
      `{user_id, username}` TTL 24 ч) → отдаёт токен в `AuthOut.token` (nullable: Redis down → None).
- [x] `get_current_user` **двухрежимный** (`api/deps/auth.py`): Authorization с `=` → initData
      (stateless HMAC, Redis не нужен — фолбэк); без `=` → session-токен → Redis → свежий User из БД
      (статус/срок — правда там). Промах/протух → 401 `session_expired`, битый initData → 401
      `invalid_init_data`. Различаем по форме, обе ветки одинаково безопасны (токен неугадываем, initData — HMAC).
- [x] Порт `SessionStore` (`application/ports/session.py`, методы create/get — минимально; refresh/
      delete отложены до их вызывающих: sliding-TTL/ревок при бане) + `RedisSessionStore`
      (`infrastructure/cache/session.py`, **fail-open**); DI (APP-scope).
- [x] Web App (`lib/api.ts`): токен в `localStorage` (`qc_session`); `authHeader()` = токен ?? initData;
      на 401 — прозрачный ре-auth по initData + повтор запроса ОДИН раз; `refreshSession` дедуплицирует
      параллельные 401. Bootstrap-запрос `retried:true` (не зацикливать ре-auth на своём 401).
- [x] Токен — только идентификатор сессии (данных доступа нет). Ревок при бане/отписке — с их фичей.
- Тесты: `test_auth_dep.py` (4 — обе ветки + 401 промах/битый initData), `test_cache.py`
      (RedisSessionStore roundtrip + fail-open). Проверено вживую на реальном Redis (TTL=86400).

### 11.2 — Кэш каталога (cache-aside) ✅ (2026-07-05)
- [x] Агрегированный `GET /api/movies/home` — главный экран (hero + все фильмы) одним ответом
      (`CatalogHomeOut`), фронт больше не дёргает `/movies`+`/hero` раздельно. (Путь — в роутере
      `/api/movies`, чтобы переиспользовать rate-limit+auth; отступление от плановых `/api/v1/catalog`.)
- [x] Cache-aside: `cache.get()` → хит → отдаём сырой JSON `Response` (без пересериализации); промах →
      собираем из БД → `SET catalog:main <json> EX 600` → отдаём. Порт `CatalogCache`
      (`application/ports/catalog_cache.py`, get/set/invalidate) + `RedisCatalogCache` (**fail-open**).
- [x] ⚠️ **Инвалидация на `/add`**: `MovieIngestionService.ingest` после `add` зовёт
      `cache.invalidate()` → новинка видна сразу (не ждёт TTL; авто-рассылка Фазы 12 тоже придёт на неё).
- [x] Кэшируем только JSON; постеры — статика, не трогаем. Фронт: `api.home()` в `load()`,
      `buildShelves(homeRes.movies, homeRes.hero?.id)`. DEV-мок отдаёт `/api/movies/home`.
- Тесты: `test_catalog_home.py` (хит без БД / промах строит+кэширует + DTO не утекает file_id),
      `test_cache.py` (RedisCatalogCache set/get/invalidate + fail-open), `test_ingestion_service.py`
      (invalidate на ingest). Проверено вживую (Redis TTL=600) + браузер-превью (главная из `/home`).

### 11.3 — Rate limiter (защита API от выкачки/спама) ✅ (2026-07-05)
- [x] Порт `RateLimiter` (`application/ports/rate_limit.py`) + `RedisRateLimiter`
      (`infrastructure/cache/rate_limiter.py`): фиксированное окно, атомарно `SET key 0 EX window NX`
      + `INCR` в одном пайплайне (TTL ставится один раз на окно и самоочищается — нет «залипшего»
      счётчика без TTL). `hit(key,limit,window) → bool`; ключ с префиксом `ratelimit:`.
- [x] FastAPI-зависимость-фабрика `api/deps/rate_limit.py` (`rate_limit(limit,window,scope)`);
      ключ — IP из `X-Forwarded-For` (за Nginx), фолбэк `request.client` (dev). Пер-юзер-ключ из
      сессии — с 11.1. Лимит исчерпан → `429 too_many_requests`.
- [x] Лимиты (данные, крутить в роутерах): каталог 100/10с на IP (роутер-уровень `/api/movies`,
      покрывает list/search/get/hero/**play**), `/initiate` 20/60с, `/proof` 15/300с. Постеры —
      статика (Nginx/StaticFiles), не лимитируем. Щедро против ложных 429 на CGNAT-IP мобильных.
- [x] **Fail-open** в адаптере: Redis недоступен → `hit` возвращает True (лучше обслужить, чем 429
      всем). Заметка про всплеск на стыке окон — в докстринге адаптера (для MVP ок).
- [x] Тесты: `test_cache.py` (fakeredis — окно T/T/T/F, независимость ключей, fail-open на стабе) +
      `test_rate_limit_dep.py` (429 при превышении, ключ по X-Forwarded-For). Проверено вживую на реальном Redis.

### 11.4 — Лок отправки видео (анти-двойной-клик) ✅ (2026-07-05)
- [x] Порт `Lock` (`application/ports/lock.py`) + `RedisLock` (`infrastructure/cache/lock.py`):
      `SET lock:<key> 1 EX ttl NX`; `acquire(key,ttl) → bool` (True — взял, False — занято). Явного
      release нет — снимается по TTL (для анти-двойного-клика ключ должен пережить операцию).
- [x] Встроен ВНУТРИ `PlaybackService.deliver` (после гейта доступа и загрузки фильма, перед
      отправкой). Ключ — `send_video:<user_id>:<movie_id>` (пер-юзер+фильм, чтобы клики по разным
      фильмам не мешали). Повтор в окне → тихий no-op, но возвращает **DELIVERED** (фронт покажет ту
      же модалку «видео отправлено», а не ошибку). **Fail-open** (Redis down → acquire True → шлём).
- [x] Тест: два быстрых `deliver` той же пары → одна отправка (`test_playback_service.py`, реалистичный
      NX-фейк `_OneShotLock`); адаптер — на fakeredis (`test_cache.py`).

## Фаза 12 — Рассылки и уведомления о новинках ✅ (2026-07-06)
**Цель:** уведомлять юзеров о новом фильме, не ловя флуд-бан Telegram (~30 msg/s), уважая выбор
юзера (вкл/выкл уведомлений). Зависит от Redis-фундамента (Фаза 11.0) — очередь на Redis.
**Решение по библиотеке:** свой минимальный Redis-list reliable-queue, БЕЗ новой зависимости
(паттерн `infrastructure/cache/` порт+адаптер, философия проекта; arq отклонён).

### 12.0 — Очередь рассылок (фоновый worker, crash-safe) ✅
- [x] Порт `BroadcastQueue` (`application/ports/broadcast.py`: enqueue/reserve/ack/recover +
      `BroadcastMessage`/`BroadcastJob`) + `RedisBroadcastQueue` (`infrastructure/cache/broadcast.py`).
      Хранилище — Redis List `broadcast:pending`; **crash-safe:** `reserve` = `LMOVE` в
      `broadcast:processing` (не теряется до `ack`=`LREM`), `recover` при старте возвращает незавершённые
      (at-least-once). Payload `broadcast:msg:<uuid>` EX 24ч (задания хранят лишь `{mid,chat}`). **Fail-open.**
- [x] Отдельный процесс-worker `app/worker.py` (+ сервис `worker` в compose): `reserve(25)` → шлёт →
      `ack` ПОСЛЕ отправки, `sleep(1)`/пачку (~25 msg/s < лимит Telegram).
- [x] Библиотека: **свой Redis-List worker** (без новых зависимостей) — решено при старте фазы.
- [x] ⚠️ Реалии Telegram: `RetryAfter` → пауза `retry_after`+1 и повтор; `Forbidden`/`BadRequest`
      (bot blocked / chat not found) → `set_notifications(False)`, не ретраим вечно. `_deliver` не
      пробрасывает — иначе «мёртвый» получатель зациклит очередь (crash до ack покрыт recover).

### 12.1 — Настройка уведомлений юзером (opt-out, по умолчанию ВКЛ) ✅
- [x] `User.notifications_enabled: bool = True` (домен) + `UserModel` + миграция `c7e8f9a0b1c2`
      (server_default true → backfill). **Инвариант:** `upsert` НЕ трогает флаг (не в on_conflict set_),
      меняет только `set_notifications` (точечный UPDATE) → логин/activate/expire не сбрасывают opt-out.
      Аудитория = `list_notifiable()` (telegram_id с флагом True).
- [x] `PATCH /api/me/notifications {enabled}` (`api/routers/me.py`, гейт `get_current_user`) →
      `BroadcastService.set_user_notifications`. `AuthOut.notifications_enabled` — фронт без доп. запроса.
- [x] Web App: тумблер в профиле (👤, колокол `Bell` + switch) «Жаңа фильмдер туралы хабарлау» —
      оптимистичный, откат при ошибке, синк в `App.auth`. DEV-мок отдаёт `/api/me/notifications`.

### 12.2 — Авто-уведомление о новинке (главный сценарий) ✅
- [x] `MovieIngestionService.ingest` → `BroadcastService.notify_new_movie` (постер+`title_kk`+описание
      + кнопка «🍿 Көру» web_app) по opted-in. В try/except — сбой рассылки НЕ роняет добавление фильма.
- [x] Инвалидация кэша каталога — уже в ingest (Фаза 11.2), ДО рассылки → клик из уведомления видит новинку.
- [x] Идемпотентность на уровне вызова: ingest зовёт notify один раз на фильм (persistent-флаг «notified»
      не понадобился — единственный триггер; отмечено как возможное усиление, если триггеров станет больше).

### 12.3 — Ручная рассылка админом ✅
- [x] Бот-команда `/broadcast` (`bot/handlers/broadcast.py`, только `BOT_ADMIN_USER_IDS`, FSM
      текст→предпросмотр→подтверждение) → `BroadcastService.broadcast_custom` → очередь. MVP — текст
      (медиа-рассылки — задел на будущее, расширить `BroadcastMessage`).
- [x] Подтверждение админу: «✅ N қолданушыға кезекке қойылды».

### Тесты ✅
- [x] `BroadcastQueue` на fakeredis (`test_broadcast_queue.py`, 7): roundtrip/batch/ack+recover/
      payload-expire/empty/fail-open. `_deliver` worker'а (`test_worker.py`, 2): успех + пометка
      заблокировавшего (`set_notifications False`). Нотификатор (`test_notifier.py`, 3): фото/текст/фолбэк.
- [x] Аудитория = только `notifications_enabled=True` + инвариант upsert (`test_repositories.py`, 2);
      сервис (`test_broadcast_service.py`, 4): аудитория/контент/URL/тумблер. Итог в контейнере: pytest 110.

---

## Идеи на будущее (не в MVP)
- Лидерборды/реферальная программа.
- Mini App админки (чекбоксы категорий из справочника).
- Множественные каналы-архивы.
