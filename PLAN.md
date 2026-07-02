# PLAN.md — дорожная карта QazaqCinema

Рабочий план по фазам. Каждая сессия: открыть этот файл → найти **ТЕКУЩУЮ ПОЗИЦИЮ** →
сделать следующие невыполненные шаги → отметить `[x]` → подвинуть маркер.

**Definition of Done для любой фазы:** `ruff check app tests`, `mypy app`, `pytest` — зелёные;
новое поведение покрыто тестом (где применимо).

---

## 📍 ТЕКУЩАЯ ПОЗИЦИЯ
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

## Фаза 8 — Оплата: Telegram Stars (авто-подписка)
**Цель:** нативная оплата цифрового контента + помесячная авто-подписка.
- [ ] Сверить актуальную доку Telegram Payments (Stars/XTR, subscription_period)
- [ ] `TelegramStarsProvider.initiate`: `create_invoice_link(currency="XTR", …)`
- [ ] Хендлеры `pre_checkout_query` + `successful_payment` → `SubscriptionService.activate`
- [ ] Зарегистрировать Stars в `payment_providers` (DI) — без правок сервисов
- [ ] Обработка авто-продления (recurring) для тарифа `1_month`

## Фаза 9 — Фронтенд: Web App (Telegram Mini App)
**Цель:** тёмный Netflix-style интерфейс. Каталог листают ВСЕ; подписка проверяется только
в момент «Көру». Дизайн обсуждён и зафиксирован 2026-06-30 (решения ниже).

### Зафиксированные решения (UX/UI)
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
- [ ] Sticky topbar: компактный логотип слева, иконка профиля/статуса подписки справа (👤).
- [ ] Поиск ОТДЕЛЬНОЙ строкой во всю ширину (`/movies/search?q=`), а не рядом с лого.
- [ ] Hero-баннер сверху (одна новинка, 16:9) — оживляет редкий каталог, CTA «Көру ▸ ботта».
- [ ] Карусели: «Жаңа түскен» (новинки, `/movies` по дате) + «Танымал» (топ по рейтингу) +
      ряды по категориям («Мультфильмдер», «Аниме» из `/movies?category=`).
- [ ] ⚠️ Маленький каталог: ряд рендерим только если в нём ≥ N уникальных (нет в hero), иначе
      одни и те же тайтлы дублируются в 4 рядах. Старт: Hero + «Жаңа» + ряды категорий.

### Карточка фильма + просмотр
- [ ] Карточка (bottom sheet / экран): постер, `title_kk` (+ `title_original`), год, рейтинг ⭐,
      описание, категория; крупная кнопка «Көру ▸ ботта» (с замком 🔒, если нет доступа).
- [ ] «Көру» → `POST /api/movies/{id}/play`: 200 → модалка «видео отправлено» + «Жабу»
      (`WebApp.close()`); 403 `no_access` → открыть пэйволл-шторку; 404 → тост об ошибке.
- [ ] Заменить заглушку `web/src/lib/telegram.ts:watchMovie` (старый `switchInlineQuery`) на
      `api.play(id)` + хэндофф-модалку.

### Пэйволл (bottom sheet, 2 тарифа)
- [ ] Контекстная шторка снизу поверх карточки (не отдельный экран): «чтобы посмотреть X — оформи».
- [ ] 2 тарифа из `/api/payments/tariffs`: `1_day` (349 ₸, «сынап көру») и `1_month`
      (1899 ₸, бейдж «ең тиімді» + дробная цена ₸/күн).
- [ ] Способы оплаты: **Kaspi первым** (перевод + загрузка чека → «10–15 мин ішінде тексереміз»),
      Telegram Stars вторым («бірден» — мгновенно). Kaspi: `initiate` → реквизиты → `proof` (чек).
- [ ] Нативная нижняя `MainButton` для главного действия оплаты.

### Состояния пользователя
- [ ] new / expired → листает всё, «Көру» открывает пэйволл.
- [ ] pending_review → баннер сверху «Чек тексерілуде ⏳», «Көру» заблокирован.
- [ ] active → в профиле (👤) счётчик «осталось N дней» + дата `expires_at`.

### Нативный Telegram + сборка
- [ ] `expand()` при старте, `BackButton` для навигации назад, `HapticFeedback` на «Көру»/оплату.
- [ ] Скелетоны постеров при загрузке (мобильная сеть); пустые/ошибочные состояния.
- [ ] Доавторизация: `api.auth()` при старте (статус/доступ для замков и профиля).
- [ ] API-клиент: добавить `auth()`, `movies()`, `searchMovies()`, `play()`, `initiatePayment()`,
      `submitProof()` в `web/src/lib/api.ts` (сейчас только `tariffs()`).
- [ ] Сборка `npm run build`, отдача статики (Nginx или FastAPI StaticFiles).

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
