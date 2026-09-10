# CLAUDE.md — гайд по проекту

Читать первым. Что осталось сделать — в [PLAN.md](PLAN.md), живой прод — в [DEPLOY.md](DEPLOY.md).

⚠️ **Перед первой правкой кода — [CODESTYLE.md](CODESTYLE.md)**: слои и запрет импортов чужого
слоя, имена, энумы против справочников, `AppError` и Outcome-значения, время, куда добавлять
новое без костылей. Часть правил проверяет ruff, остальное — на авторе правки.

## Что это
**QazaqCinema** — онлайн-кинотеатр внутри Telegram Mini App: мультфильмы и аниме с казахской
озвучкой. Видео лежит в приватном канале-архиве Telegram и выдаётся ботом в личку с
`protect_content=True`; бэкенд видео не стримит. Монетизация — подписка (Kaspi-чек с ручной
модерацией + Telegram Stars). Каталог наполняет админ визардом `/add`. Публичный канал
`@qazaqcinema_kz` ведётся автоматически: фильм дня, новинки, контент про казахский язык и квизы.
Прод: `https://qazaqcinema.kz`, бот `@qazaqcinema_bot`.

## Стек
- **Python 3.13**, aiogram 3 (бот), FastAPI (API + SSR SEO-страницы на Jinja2), SQLAlchemy 2.0
  async + asyncpg + Alembic (PostgreSQL 16), dishka (DI), apscheduler, redis.asyncio, Pillow, PyYAML.
- **Web App:** React 19 + Vite 6 + TypeScript + Tailwind v4; иконки `lucide-react`, шрифт Inter.
- **Инфра:** Docker Compose, одна топология для dev/prod/test (postgres, redis, migrate, api, bot,
  worker, web=Caddy). Разница сред — только env-файл. Проверки: ruff + mypy(strict) + pytest.

## Архитектура: Clean / Hexagonal
Домен не знает про aiogram/FastAPI/Postgres. Bot и API — тонкие входы: достать данные →
сервис → ответ. Сервисы зависят от `application.ports.*`, никогда от `infrastructure.*`.

```
app/
  bot/                 # aiogram. handlers: start, add_movie (/add), broadcast, daily (/daily),
                       #   milestone (/milestone), inline_query, moderation (✅/❌ чеков), quiz
                       #   (кнопки квиза + комментарии группы), stars. keyboards/, security.is_admin
  api/                 # FastAPI. routers: auth, catalog (/api/movies), favorites, me, payments,
                       #   events (paywall/search — метрики с фронта), support, public_seo
                       #   (/m/<slug>, /catalog, /sitemap.xml, /robots.txt), health
                       # schemas — DTO без telegram_file_id; deps — get_current_user, rate_limit
  domain/              # ядро без зависимостей
    entities/          # Movie, User, Series/Season, PaymentRequest, Delivery, enums
    catalog/           # categories (данные), daily.pick_daily_id (фильм дня), popularity
    tariffs/           # тарифная сетка (данные)
    subscription/      # compute_expiry
    analytics/         # EventKind, DailyReport/render_report, weekly_report, milestone, percent
    seo/               # slug.py (<id>-<translit>), keywords.py (как ищут: бренд, суффиксы,
                       #   теги категорий), landing.py (тексты страниц категорий)
    channel/           # post.py (тексты постов о фильмах), cards.py (спека карточек),
                       #   holidays.py (календарь праздников: правила дат + holiday_for),
                       #   content/ (kinds, topics, item, plan=сетка слотов, split,
                       #   render/ (Registry рендереров), answers/ (нормализация, чекеры, разбор))
    mention.py, registry.py
  application/
    ports/             # Protocol: repositories, payments, telegram, security, session, lock,
                       #   rate_limit, catalog_cache, broadcast, storage, images, channel,
                       #   discussion, content, cards, daily_pin
    services/          # use-cases (auth, catalog, playback, subscription, payment, stars,
                       #   moderation, ingestion, series, broadcast, favorite, support, activity,
                       #   analytics, milestone, daily, seo, channel, content_posting,
                       #   content_seed, quiz, video_retention)
  infrastructure/
    db/                # models (ORM), engine, sql, content_repositories, content_codec,
                       #   repositories/ (catalog, users, payments, analytics)
    cache/             # Redis: session, catalog, lock, rate_limiter, broadcast (очередь), daily_pin
    telegram/          # init_data (HMAC), notifier, channel (публикатор), discussion (группа),
                       #   media (фото с диска: канал и рассылка)
    payments/          # kaspi (ручной чек), stars
    images/            # pillow (постеры), cards_pillow (карточки канала)
    storage/local.py   # постеры на диске (том uploads, StaticFiles /posters)
    content/           # yaml_loader (content/*.yaml → домен)
    analytics/         # admin_filter — журнал событий без действий админов
    di/providers.py    # composition root; scheduler.py — все фоновые джобы
  config/settings.py   # pydantic-settings: BOT_/DB_/REDIS_/PAY_/API_/MEDIA_ + PUBLIC_ORIGIN
  main.py (бот, polling/webhook)  worker.py (рассылки)  tools/ (seed_content, preview_post)
web/src/               # App.tsx (экран и правила показа), hooks/ (данные, поиск, возврат в
                       #   приложение, версия сборки), components/, lib/ (api, telegram,
                       #   catalog, lastPage, devMock), ui/, index.css (@theme — токены)
content/               # пул канала: *.yaml + images/ + fonts/
migrations/            # Alembic, имена файлов yyyymmdd_<slug>
```

**Данные vs код.** Тарифы, категории, темы контента, сетка слотов, лимиты — данные (правка
строки, без миграции; в БД это VARCHAR, не PG-ENUM). Способы оплаты, формы контента
(рендереры) — код: новый класс, без правки существующих.

**Fail-open.** Все Redis-адаптеры и журнал событий деградируют молча: Redis лёг → сессии
откатываются на initData, кэш промахивается, лок/лимитер пропускают, очередь рассылок
no-op. Публикация в канал и запись событий не имеют права уронить основной путь.

## Команды
```bash
./start.sh                # dev: весь стек в Docker (env=.env), миграции авто
./start.sh prod           # те же контейнеры, env=.env.prod (единственный правильный способ деплоя)
./start.sh test           # ruff+mypy+pytest в контейнере, БД qazaqcinema_test — НЕ на прод-сервере
./start.sh seed [--check] # content/*.yaml → БД + картинки в том uploads (идемпотентно, upsert по slug)
./start.sh logs|ps|down|migrate|backup
```
На прод-сервере проверки гонять в одноразовом контейнере, мимо compose (иначе пересоздаётся
боевой postgres):
```bash
docker build --target test -t qc-checks:local .
docker run --rm -v $PWD/app:/app/app -v $PWD/tests:/app/tests qc-checks:local sh -c "ruff check app tests && mypy app"
docker run --rm --network host --env-file .env.test -e DB_HOST=127.0.0.1 -e REDIS_HOST=127.0.0.1 \
  -e DB_PASSWORD="$(grep ^DB_PASSWORD= .env.prod | cut -d= -f2-)" \
  -v $PWD/app:/app/app -v $PWD/tests:/app/tests qc-checks:local pytest -q
```
Фронт (node на хосте нет, поэтому тоже в контейнере — `tsc -b && vite build`):
```bash
docker run --rm -v $PWD/web:/web -w /web node:20-alpine npm run build
```
Тесты репозиториев идут через `create_all` + TRUNCATE в БД с именем на `_test` (conftest
отказывается работать с другой). После смены схемы тест-БД пересоздать: `dropdb` → `createdb`.
Ручной `docker compose up` на проде — только как `ENV_FILE=.env.prod docker compose --env-file
.env.prod ...`, иначе контейнеры получат dev-пароль к БД.

Git: коммитить и пушить прямо в `main`, без фича-веток.

## Инварианты и решения
Коротко, по областям. Это то, что легко сломать, не зная почему оно так.

### Безопасность и доступ
- `telegram_file_id` — только боту; в API-DTO его нет. Видео идёт исключительно
  `send_video(protect_content=True)` в личку; `POST /api/movies/{id}/play` лишь триггер.
  Inline-режим видео не отдаёт (inline-результаты `protect_content` не умеют).
- Авторизация Web App: initData валидируется HMAC + TTL 24 ч по `auth_date` один раз в
  `POST /api/auth` → сессия в Redis (`session:<uuid>`, 24 ч) → клиент шлёт токен.
  `get_current_user` двухрежимный: токен или сырой initData (различаем по `=`). Токен
  непрозрачный, статус доступа всегда свежий из БД. JWT нет.
- Админ-действия (модерация чеков, `/add`, `/broadcast`, `/daily`, `/milestone`) — под
  `bot/security.is_admin` по `BOT_ADMIN_USER_IDS`, не только через видимость кнопок.
- Rate-limit — FastAPI-зависимость, ключ по IP из `X-Forwarded-For`; лимиты — данные в роутерах.
  У `GET /api/me` лимит щедрый (120/мин): мобильные юзеры сидят за общим CGNAT.

### Пользователь и чат с ботом
- Без открытого чата с ботом кинотеатр не работает (бот не может написать первым).
  Признак — `users.bot_started_at`: ставит `/start` и успешная выдача, снимает только реальная
  недоставка (`RecipientUnreachableError`). Ещё его ставит `allows_write_to_pm` из initData и
  `POST /api/me/write-access` после `WebApp.requestWriteAccess()` (попап показывается один раз за
  заход, с задержкой после готовности экрана). Отсутствие флага в initData ничего не снимает.
- `UserRepository.upsert` НИКОГДА не трогает `notifications_enabled`, `free_view_*`,
  `bot_started_at` — только точечные сеттеры. Иначе вход в Mini App затирал бы выбор юзера.
- Шторка `BotStartSheet` (`t.me/<bot>?start=web`, через `openTelegramLink`) показывается
  превентивно только там, где на кону подарок; у подписки/фильма дня сначала пробуем отправить,
  шторку рисует обработчик 409 — флаг может быть устаревшим.
- `/start` заводит юзера в БД (`UserActivityService`, под try/except — БД не должна оставить
  человека без приветствия). `/start` регистрируется через `set_my_commands`: кнопка-меню занята
  Mini App, а большую кнопку START Telegram рисует только тем, кто бота не запускал.

### Каталог
- Названия мультиязычные: `title_kk` основное, `title_ru`/`title_original` nullable.
- Категории — массив `categories VARCHAR[]` + GIN, фильтр `&&` («хотя бы одна»). Массив, а не
  join-таблица: категория остаётся свободными данными.
- Поиск — pg_trgm + unaccent через immutable-обёртку `f_unaccent` (и в запросе, и в
  GIN-индексе, иначе индекс не используется). FTS не годится: у Postgres нет казахского словаря.
- Популярность — `play_count` (+1 на реальной доставке) и `favorites_count`, формула в
  `domain/catalog/popularity.py`; `ORDER BY ... , rating DESC NULLS LAST, id DESC`.
- Главная = hero + две полки (Жаңа түскен, Танымал), всё лимитируется на бэке. Браузинг по
  категориям, сортировка и пагинация подгрузкой — в табе «Каталог»; третий таб «Таңдаулы»
  (избранное без гейта подписки). Сортировка — Literal-белый-список, сырых строк в SQL нет.
- Кэш каталога — cache-aside в namespace `catalog:*` (`home:<местный день>` 600 с,
  `categories` 600 с, `browse:*` 60 с). `MovieIngestionService.ingest` чистит весь namespace.
- Сериалы: `Series` — только название; постер/названия/категории живут на `Season` и копируются
  на каждую серию при `ingest`; серия имеет только номер. FK `season_id` — `ON DELETE SET NULL`.
- Картинка у фильма одна — постер 2:3 (`ImageProcessor`, Pillow, `ImageOps.fit`), в двух
  копиях: крупная `<uuid>.jpg` (600×900) и превью `<uuid>_sm.webp` (400×600) для сеток и
  полок. Превью в WebP — на четверть меньше байт при том же виде (49 → 36 КБ на живом
  каталоге), а сетками ограничены и SSR-страницы, и Mini App. ⚠️ URL превью нигде не хранится, его выводят `thumb_url`
  (бэк) и `thumbUrl` (фронт) — расширение оба берут из формата `POSTER_THUMB`; смена
  формата = прогон `./start.sh thumbs --force` вместе с деплоем. Hero рисуется из
  крупной копии (размытый увеличенный фон + чёткая копия). `hero_image_url` остался
  только как og:image для старых фильмов; шага баннера в визарде нет.

### Фильм дня
- Hero главной = фильм дня, бесплатный для всех. Выбор — чистая функция
  `domain/catalog/daily.pick_daily_id`: детерминированный по МЕСТНЫМ суткам (Asia/Almaty),
  перестановка внутри круга (каждый фильм ровно раз за круг), пул — весь каталог.
- Источник правды один на витрину и выдачу — `DailyMovieService`. Порядок оснований в
  `PlaybackService`: подписка → фильм дня → свой подарок → захват подарка → пэйволл.
  Фильм дня подарок не тратит; событие `daily_play`.
- Закреп админом `/daily <id>` — порт `DailyPin` (Redis, живёт до местной полуночи, снимается
  сам). Срок бесплатности считает бэк (`hero_free_until`), фронт только форматирует.

### Подписка и оплата
- `SubscriptionService.activate/expire_due/has_active_access` — единственная точка гранта,
  ревока и проверки; способы оплаты только зовут `activate`. Доступ считается по `expires_at > now`
  в реальном времени, джоб `expire_due` (15 мин) лишь проставляет статус, шлёт DM и забирает видео.
- Тарифы — данные `domain/tariffs/catalog.py`: `1_day` (разовый), `1_month` (`recurring`,
  под Stars). Цены в тенге и в звёздах (`price_xtr`) — там же.
- Kaspi: два способа по заполненности env — `PAY_KASPI_NUMBER` (перевод по номеру) и
  `PAY_KASPI_LINK` (Kaspi Pay). Пусто → способ скрыт на пэйволле. Чек → `payment_requests` →
  админам карточка с ✅/❌ (`ModerationService`).
- Stars: `currency="XTR"`, `provider_token=""`, сумма = число звёзд, `subscription_period=2592000`
  (единственный допустимый). Активация только на `successful_payment`; payload `<user_id>:<slug>`.
- `payment_requests` — единая аудит-таблица по всем способам (`proof_file_id` у Kaspi,
  `external_charge_id` у Stars).

### Выдача и удаление видео
- Telegram не даёт боту удалить сообщение старше 48 ч, поэтому выдачи чистятся ПО ВОЗРАСТУ:
  ежечасный `purge_stale` сносит старше `STALE_AFTER=40 ч` пачками (`BATCH_SIZE` — размер одного
  запроса, цикл выгребает всё). Подписчик просто жмёт «Көру» ещё раз.
- `delete_message` возвращает `DeleteOutcome` (DELETED / REFUSED / FAILED), классификация в адаптере.
  `FAILED` оставляет строку с `attempts+=1`, `next_attempt_at=+1 ч` (без него сбойная строка
  зациклила бы `list_due`), после `MAX_ATTEMPTS=6` сносим. Интервал ровный, не экспонента: до
  потолка Telegram остаётся 8 ч.
- Лок отправки живёт внутри `PlaybackService.deliver` (`send_video:<user>:<movie>`).

### Рассылки
- Своя reliable-очередь на Redis-list (`broadcast:pending` → `LMOVE` в `processing` → `ack` после
  отправки, `recover` на старте; at-least-once). Payload раз на рассылку (`broadcast:msg:<uuid>`,
  24 ч). Разбирает отдельный процесс `worker.py`: один глобальный лимит Telegram, `RetryAfter` →
  пауза, `Forbidden/BadRequest` → снять с рассылок.
- Рассылка о новинке В ЛИЧКИ — по выбору админа на каждом фильме (шаг «🔔» визарда).
  Аудитория всегда `notifications_enabled = true`; ручная — `/broadcast`. Пост в канал этому
  тумблеру НЕ подчиняется (см. «Публичный канал»).
- Рассылка в личку и пост в канал — разные механизмы: `web_app`-кнопка в каналах не работает,
  там только `url` на `t.me/<bot>?startapp=m_<id>`.
- Постер в рассылке уходит ФАЙЛОМ с диска (`BroadcastMessage.photo_path`, как в канале):
  по ссылке Telegram его не скачает. Поэтому воркеру смонтирован том `uploads`, а в payload
  очереди лежит путь относительно медиа-корня. Файла на диске нет → письмо уходит текстом.

### Визард `/add`
- Навигация данными: порядок шагов — `_ORDER`, тексты — `_PROMPTS`, меню правки — `EDIT_FIELDS`
  в `handlers/add_movie.py`. Новый шаг = строка в этих трёх, не новый хендлер. «Артқа», «Әрі
  қарай» и «Түзету» (прыжок к одному полю и назад к сводке, флаг `edit`) работают одинаково везде.
- Ошибка сохранения НЕ чистит FSM — админ повторяет «Сақтау» или правит поле.
- Порядок: видео → категории (мультивыбор чекбоксами, ≥1) → сериал/сезон → постер → названия →
  год → рейтинг → описание → рассылка → сводка. Выбрана серия существующего сезона — постер,
  категории, названия и описание пропускаются (`_SEASON_SKIP`): их несёт сам сезон.

### Аналитика и отчёты
- Событий — короткий список значимых фактов (`domain/analytics/events.EventKind`: start, open,
  play, free_play, daily_play, subscribe, expire, write_access, paywall, …; VARCHAR в БД). Клики по
  каталогу не пишем. `open` пишется только в `AuthService.bootstrap`, не в `authenticate`
  (тот дёргается на каждом запросе при лежащем Redis).
- `paywall` шлёт ФРОНТ (`POST /api/events/paywall` из `openPaywall`): решение «доступа нет»
  принимает клиент, сервер видит лишь единицы. Дубль с серверной записью снят флагом `track=false`
  на ветке 403. Поиск логируется тоже с фронта (`POST /api/events/search`, после дебаунса).
- Действия админов в статистику не попадают: декоратор `AdminBlindEventRepository` на записи;
  счётчики людей исключают админов явно (`exclude`).
- Ежевечерний отчёт в 22:00 по Алматы (`REPORT_TZ` явно: контейнеры в UTC), окно — скользящие
  24 ч до отправки. Снимок пишется в `daily_reports` upsert по `day`; проценты не хранятся,
  `render_report` считает их из чисел (`None` при пустом знаменателе). `misfire_grace_time=3600 +
  coalesce`. Планировщик живёт только в процессе бота.
- Еженедельный дайджест (вс 22:10) агрегирует снимки `daily_reports`, а не сырые события:
  состояние на момент (`catalog_size`, `users_total`) из сырья не восстановить. `opens_unique`
  за неделю — сумма дневных уникальных, не недельный охват (осознанно).
- Вехи — `/milestone <текст>` (лента `milestones`, дата только текущая). Модель монетизации не
  хранится как состояние: подарок и фильм дня работают одновременно.
- Спрос — `search_queries` (append-only журнал поисков, включая нулевые результаты) — очередь на
  озвучку. Блок «Іздеп, таппағаны» — и в дневном отчёте, и в недельном дайджесте (там окно то же,
  что у вех): сколько искали, сколько зря и ТОП-10 нулевых с числом попыток и числом РАЗНЫХ людей
  (десять попыток одного и десять человек — разный сигнал). В снимок блок НЕ пишется и колонок не
  требует: журнал append-only, повторный запрос даёт то же самое (`SearchSummary` — живой запрос,
  текст рисует общий `render_demand_block`). Запрос — пользовательский текст, а отчёт уходит
  HTML → блок его экранирует.

### SEO и вход извне
- Google не видит Mini App, поэтому бэкенд отдаёт настоящий SSR: `/m/<id>-<slug>`, `/catalog`,
  `/catalog/<категория>`, `/sitemap.xml` (приоритет 1.0 у `/catalog`, корень — пустая SPA),
  `/robots.txt`. Caddy проксирует эти пути на api до SPA-фолбэка. Рендер из БД на лету.
- **Хабы листаются, а не растут**: страница отдаёт `SEO_PAGE_SIZE`=48 карточек, дальше
  `?page=N`. Без этого один документ тяжелел с каждым фильмом — на 186 карточках страница
  тянула 9 МБ постеров, и краулер бросал рендер не догрузив. Правила пагинации — чистые, в
  `domain/seo/pagination`: страница 2+ **канонична сама себе** (canonical на первую выбросил
  бы из индекса её фильмы), `?page=1` → 301 на чистый URL, номер страницы входит в `<title>`
  ДО обрезки до 65 символов (иначе у всех страниц один заголовок = дубли), все страницы
  пагинации перечислены в sitemap. Листалка — обычные `<a href>`: только по ним краулер
  доходит до карточек со второй страницы.
- **Ни одна страница не читает каталог целиком.** Свой срез — `list_page` с `LIMIT`
  (сортировка `newest`: «плавающий» порядок перекладывал бы фильмы между `?page=2` и
  `?page=3` между обходами), счётчики разделов — один `GROUP BY`, похожие — `list_related`
  (число общих категорий считает SQL). Единственное исключение — sitemap: он обязан
  перечислить каждый URL.
- Поиск на страницах — СЕРВЕРНЫЙ, `/catalog?q=<…>` под `noindex, follow` (и `Disallow` в
  robots): страницы результатов Google индексировать не рекомендует, но ссылки с них
  обходит. По отрисованным карточкам искать нельзя — их на странице всего 48 из всего
  каталога.
- Вся SEO-логика в `SeoBuilder` (`seo_service.py`): билингвальный title, description ≤160,
  OG/Twitter, JSON-LD schema.org/Movie. Формулировки спроса и тексты посадочных страниц —
  ДАННЫЕ в `domain/seo/keywords.py` и `landing.py` (новая фраза = строка, без правки логики).
- Slug `<id>-<translit>`: id — источник правды, старый хвост и `/m/42` → 301 на актуальный.
- Deep-link `t.me/<bot>?startapp=m_<id>`: фронт читает `start_param`/`#m<id>`
  (`web/lib/telegram.getStartMovieId`), бот `/start m_<id>` — фолбэк. Deep-link главнее
  сохранённого экрана. Гостю в браузере — экран `NotInTelegram` с кнопкой `t.me/<bot>?start=web`.
- `LEGACY_ORIGINS` в env — старые домены, Caddy редиректит их permanent на `PUBLIC_ORIGIN`.

### Публичный канал
- Публикация — порт `ChannelPublisher` (`infrastructure/telegram/channel.py`), канал не настроен
  (`BOT_PUBLIC_CHANNEL_ID=0`) → тихий no-op; ошибки Telegram глушатся (канал — витрина).
  `publish` возвращает `message_id` (нужен для разбора квиза и комментариев).
- Пост о новинке уходит на КАЖДЫЙ залитый фильм, тумблер рассылки визарда его не касается:
  канал — витрина, и лента там повторяет каталог. Гейт по `notify` был причиной того, что при
  заливке пачками (админ жмёт «🔕 Жоқ») канал молчал вообще.
- ⚠️ Картинки уходят ТОЛЬКО файлом с диска (`ChannelPost.photo_path` → `FSInputFile`), и это
  не стилистика: по URL картинку качает сам Telegram со своих серверов, а входящий трафик с его
  диапазонов режет хостер (тот же повод, что у `BOT_FORCE_POLLING`) — постер молча не доезжал и
  пост уходил текстом. Публичный URL постера в `ChannelPost` не передаётся вообще.
  Путь «публичный URL → файл» знает `PosterStorage.local_path`, а не сервис.
- ⚠️ Пост с inline-клавиатурой Telegram НЕ пересылает в группу обсуждений → под ним нет
  комментариев. Место под постом одно: либо кнопки, либо «Комментарии». Посты о фильмах сейчас
  с url-кнопкой (комментариев нет), квизы с вариантами — callback-кнопки (комментарии не нужны),
  жұмбақ и поздравления — без кнопок (там комментарии и есть смысл поста).
- Группа обсуждений: Telegram авто-форвардит пост в группу (`is_automatic_forward`,
  `forward_origin.message_id` = id в канале); комментарии несут `message_thread_id` = id форварда.
  Порт `DiscussionGroup` (удалить комментарий, ответить в ветку); `BOT_DISCUSSION_GROUP_ID=0` →
  хендлер инертен. Комментировать можно без вступления в группу (галочка «Вступить для отправки
  сообщений» в группе должна быть выключена).
- Контент-план без LLM в рантайме: пул в `content/*.yaml` + `content/images/`, сидер
  (`./start.sh seed`) льёт в `content_items` upsert по `slug`. `kind` = ФОРМА поста
  (`quiz_choice`, `quiz_open`, `longread`, `saying`, `term_list`, `greeting` — рендереры в
  `Registry`), `topic` = тема (данные). `payload` JSONB ↔ типизированные dataclass'ы через
  `content_codec`.
- Сетка (`domain/channel/content/plan.py`, время Алматы): Пн квиз 12:00 → разбор 21:00 · Вт нақыл
  сөз 19:00 · Ср атаулары 19:00 · Чт квиз 12:00 → 21:00 · Вс қара сөз 19:00 (фолбэк — saying, когда
  45 қара сөз без повторов кончатся). Фильм дня — 10:00. Один ежечасный джоб спрашивает
  `slot_for(now)`. Ротация — LRU по `last_posted_at` в SQL; `scheduled_for` — редакторский пин.
- Праздники — отдельный механизм от сетки: праздник привязан к ДАТЕ, а не к дню недели, и
  элементом пула быть не может (пул крутится LRU-ротацией). Справочник —
  `domain/channel/holidays.py` (`Fixed` — число, `NthWeekday` — «3-е воскресенье сентября»,
  `Lunar` — таблица дат по годам), тексты и картинки — `content/holidays.yaml` (slug тот же,
  что у праздника; форма `greeting`, рубрика `meiram`). Джобов столько, сколько РАЗЛИЧНЫХ
  времён в справочнике (`POST_TIMES`: 00:01 Жаңа жыл, 09:00 остальные, 12:00 Ұстаз күні —
  он раз в несколько лет падает на Қарттар күні, и часы разведены, чтобы вышли оба).
  Многодневные праздники поздравляются один раз, в первый день. В праздник обычный слот
  сетки МОЛЧИТ (фильм дня остаётся), иначе за сутки три поста об одном дне.
- ⚠️ Ораза айт и Құрбан айт — по объявлению ДУМК (muftyat.kz): в `Lunar.dates` даты по 2030-й,
  `announced_through` отделяет объявленные от прогноза. Года нет в таблице → поздравления не
  будет (промолчать честнее, чем поздравить не в тот день). Про сверку 1 декабря напоминает
  джоб `holiday_calendar_review`: он же перечисляет незаполненное (`holidays.review_notes`),
  а сверку списка с законом делает человек — закон меняется (Конституция күні переехал
  с 30 тамыз на 15 наурыз). Скорбных дат (31 мамыр) в справочнике нет
  намеренно — канал поздравляет, а поминальный пост требует другого тона.
- Идемпотентность в схеме: `channel_post_log.slot_key` UNIQUE (у праздника ключ
  `<дата>:holiday-<slug>`), `quiz_answers (post_id, user_id)` UNIQUE (засчитывается первый
  ответ).
- Квиз: `quiz_choice` — callback-кнопки A–E, всплывашка видна только нажавшему; `quiz_open` — бот
  читает комментарий, записывает, удаляет (антиспойлер), отвечает в ветку. Проверка ответа —
  нормализация (регистр, пунктуация, свёртка қ→к ө→о ұ/ү→у ә→а і→и ң→н ғ→г, латиница) + `accept[]`
  + допуск 1 опечатки на слово ≥5 букв. Разбор генерируется из ответов и уходит reply на пост,
  кнопки снимаются.
- Картинки: карточки-цитаты кодом (Pillow, шаблон в стиле Mini App), портреты и фото предметов —
  Wikimedia Commons с автором и лицензией в YAML (печатаются в подвале). Авторы — с истёкшими
  правами (†до 1955) + фольклор; Момышұлы — короткие цитаты как цитирование. Әуезов не берём.
- `longread` длиннее 4096 → `split_text` режет по абзацам, части уходят подряд; карточка первой.

### Фронтенд
- Фиксированная тёмная брендовая тема (не тема Telegram), язык UI — казахский. Компоненты свои на
  токенах `@theme` в `index.css`; без рантайм-UI-библиотек и JS-каруселей (scroll-snap,
  `prefers-reduced-motion`).
- Пэйволл — bottom sheet, Kaspi первым. «Көру» шлёт видео в чат и показывает `HandoffModal` с
  кнопкой «Жабу» (`WebApp.close()`), без авто-закрытия.
- Статус подписки фронт освежает сам: опрос `GET /api/me` каждые 20 с пока `pending_review`, и
  всегда на `visibilitychange`/`focus`. Не через `POST /api/auth` — тот плодит сессии.
- Последний экран запоминается на 60 мин (`lib/lastPage.ts`, localStorage).
- Вне Telegram в DEV работает мок бэкенда `lib/devMock.ts` (динамический import, из прод-бандла
  вырезается). Vite-прокси `/api`+`/posters` → `API_TARGET`.

### Инфраструктура и конфиг
- `PUBLIC_ORIGIN` — единственный источник правды для домена: из него выводятся CORS,
  `bot.webapp_url`, `bot.webhook_url` (https ⟹ webhook + авто-TLS Caddy, http ⟹ polling без TLS).
  `BOT_FORCE_POLLING=1` — аварийный обход, если хостер режет входящие с диапазонов Telegram.
- Вебхук — aiohttp-сервер внутри процесса бота (`/tg/webhook`, порт 8080 за Caddy), не роут FastAPI.
- Каждая секция конфига — свой `BaseSettings` с `env_prefix` и `env_file` (вложенные не наследуют).
  Списки из env — `NoDecode` + валидатор. Alembic берёт DSN из `DatabaseConfig`
  (`-x dsn=...` переопределяет).
- Compose: лимиты памяти на сервис — предохранители, логи json-file 10m×3. Тома: `pgdata`,
  `uploads` (постеры + `channel/` карточки; смонтирован api/bot/worker — все трое шлют
  картинки с диска), `caddy_data` (сертификаты).
- Джобы (`infrastructure/scheduler.py`, все в процессе бота): `expire_due` 15 мин · `purge_stale`
  60 мин · дневной отчёт 22:00 · недельный вс 22:10 · фильм дня в канал 10:00 · `content_post`
  каждый час :00 · `quiz_results` каждый час :00 · `holiday_post_HHMM` (по одному на каждое
  время из календаря праздников) · `holiday_calendar_review` 1 декабря 10:00.
