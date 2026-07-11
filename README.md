# QazaqCinema 🎬

Онлайн-кинотеатр (Netflix-style) внутри **Telegram Web App** — редкие мультфильмы и аниме
с казахской озвучкой. Видео хранится в приватном канале-архиве Telegram (экономия на хостинге),
контент защищён от скачивания (`protect_content=True`), оплата — Kaspi-чеки + Telegram Stars.

> 📖 **Перед работой над кодом** прочитай [CLAUDE.md](CLAUDE.md) (архитектура и принятые решения)
> и [PLAN.md](PLAN.md) (пошаговая дорожная карта — где остановились и что дальше).

## Возможности
- **Наполнение каталога**: админ добавляет фильм через бот-визард `/add` (видео → постер →
  на главную?/баннер → категория → названия → метаданные). Видео уходит в канал-архив; постер
  нормализуется (Pillow → 2:3) и кладётся статикой на VPS.
- **Защищённый просмотр**: видео шлёт бот в личку с `protect_content=True` (нельзя скачать,
  переслать, записать экран). `telegram_file_id` никогда не уходит на фронтенд; триггер — `POST /play`.
- **Подписка**: 2 тарифа (1 күн / 1 ай). Kaspi-чеки с ручной модерацией (MVP) + Telegram Stars
  как нативная авто-подписка.
- **Web App**: тёмный интерфейс с нижней таб-навигацией (**Басты / Каталог**). Главная —
  hero-баннер (курируется бэком) + карусели «Жаңа түскен» (новинки) и «Танымал» (по просмотрам).
  Каталог — фильтр по категориям (мультивыбор) + сортировка (дата/рейтинг/просмотры, asc/desc) +
  пагинация подгрузкой. Плюс поиск, карточка фильма, пэйволл (Kaspi/Stars). Вся выборка и лимиты — на
  бэке (ответ главной не растёт с каталогом).
- **Рассылки**: авто-уведомление о новинке + ручная рассылка админом (`/broadcast`); у пользователя —
  тумблер отписки. Фоновый worker разбирает надёжную Redis-очередь, соблюдая лимиты Telegram.

## Стек
- **Backend**: Python 3.13, **aiogram 3** (бот), **FastAPI** (API), **SQLAlchemy 2.0 async** +
  **asyncpg** + **Alembic** (PostgreSQL), **dishka** (DI), **apscheduler** (крон), **Pillow**
  (нормализация постеров/hero-баннеров).
- **Frontend**: React 19 + Vite 6 + TypeScript + Tailwind CSS v4.
- **Инфраструктура**: Docker Compose — **одна топология** для dev/prod/test (postgres, redis, api,
  bot, web (Caddy), worker), отличие сред только в env-файле; единый запуск `./start.sh`, миграции авто.
  **Redis** несёт сессии, кэш каталога, rate-limit, локи и очередь рассылок — все адаптеры
  **fail-open** (падение Redis не роняет основной путь). Прод (авто-TLS + webhook) — от одной
  переменной `PUBLIC_ORIGIN` (Caddy сам выпускает/продлевает сертификат Let's Encrypt).

## Структура
```
app/
  bot/            # aiogram: handlers (start, add_movie, broadcast, inline_query, moderation, stars), keyboards, security
  api/            # FastAPI: routers (auth, catalog, payments, me, health), schemas (DTO), deps
  domain/         # ядро без внешних зависимостей: entities, tariffs, parsing, catalog, subscription
  application/    # ports (Protocol-интерфейсы) + services (use-cases)
  infrastructure/ # адаптеры: db, telegram, payments, cache (Redis), images, di, scheduler
  config/         # pydantic-settings
  main.py         # запуск бота (polling/webhook по env)
  worker.py       # воркер рассылок (Redis-очередь → Bot API)
web/              # Web App (React + Vite + TS + Tailwind)
migrations/       # Alembic
tests/            # тесты домена + интеграционные (репозитории)
```

## Быстрый старт

**Одна топология для всех сред** (12-factor): dev и prod — один и тот же стек в Docker
(postgres, redis, api, bot, web (Caddy)), отличие **только в env-файле**. Миграции применяются
автоматически (сервис `migrate` перед стартом api/bot).

```bash
./start.sh                  # локально (env = .env); создаст .env из .env.example, если нет
./start.sh prod             # ТЕ ЖЕ контейнеры, env = .env.prod
./start.sh test             # ruff + mypy + pytest В КОНТЕЙНЕРЕ (env = .env.test, изолированная БД)
./start.sh logs [сервис]    # логи (Ctrl-C — выйти)
./start.sh migrate          # применить миграции и выйти
./start.sh down             # остановить (тома сохраняются; --clean — стереть тома)
./start.sh help             # список команд
```

После старта: **Web → http://localhost/**, API-доки → http://localhost:8000/docs, health-check →
`GET http://localhost:8000/api/health` → `{"redis":"ok","db":"ok","status":"ok"}`.

Env-файл по режиму: `dev → .env`, `prod → .env.prod` (шаблон `.env.prod.example`, секреты вне git),
`test → .env.test` (в репо, БД `qazaqcinema_test`). Нет файла — `start.sh` создаёт из шаблона; для
prod попросит вписать секреты (`BOT_TOKEN`, `DB_PASSWORD`, …).

> Прод: авто-TLS + webhook — от ОДНОЙ переменной `PUBLIC_ORIGIN` (`https://домен` → Caddy сам
> выпускает сертификат, бот в webhook; `http://localhost` → HTTP :80 + polling). Из неё же выводится
> CORS. Живой деплой (домен, DNS) — по [DEPLOY.md](DEPLOY.md).

<details><summary>Hot-reload на время активной разработки (host-venv поверх Docker-инфры)</summary>

Контейнерный web — собранная статика (без HMR), api/bot — без `--reload` (так dev == prod). Для
быстрой итерации подними в Docker только БД+Redis, а приложение гоняй на хосте (порты проброшены
на 127.0.0.1):

```bash
docker compose --env-file .env up -d postgres redis   # только БД + Redis
.venv/bin/alembic upgrade head                        # миграции
.venv/bin/uvicorn app.api.app:app --reload            # API → :8000 (автоперезагрузка)
.venv/bin/python -m app.main                          # бот (polling)
cd web && npm run dev                                 # Vite HMR → :5173 (проксирует /api на :8000)
```
</details>

## Команды
```bash
./start.sh test                        # ruff + mypy + pytest в контейнере (изолированная БД) — рекомендуется

.venv/bin/pytest                       # (на хосте) тесты домена; интеграционные — нужен postgres
.venv/bin/ruff check app tests         # линт
.venv/bin/mypy app                     # типы (strict)

.venv/bin/alembic revision --autogenerate -m "msg"   # новая миграция по diff моделей
.venv/bin/alembic upgrade head                       # применить
.venv/bin/alembic upgrade head --sql                 # offline DDL без подключения к БД
```

## Безопасность (ядро продукта)
- `telegram_file_id` отдаётся **только боту**, в API-схемах (`MovieOut`) его нет.
- Видео шлёт бот в личку с `protect_content=True` (inline-результаты `protect_content` не умеют).
- Каждый запрос Web App к API авторизуется по Telegram `initData` (валидация HMAC + TTL по
  `auth_date` против реплея, см. `app/infrastructure/telegram/init_data.py`).
- Модерация оплат (`pay:approve/reject`) — под явным админ-гейтом (`app/bot/security.is_admin`).
