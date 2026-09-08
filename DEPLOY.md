# DEPLOY.md — прод

Прод — тот же Docker-стек, что локально, отличие только в env-файле (`.env.prod`).
Живёт на `https://qazaqcinema.kz`. Разделы 0–4 — развёртывание с нуля, 5–9 — то, что уже
настроено на текущем сервере и должно быть повторено при переезде.

Всё прод-поведение включается ОДНОЙ переменной `PUBLIC_ORIGIN=https://домен`:
- **авто-TLS** — Caddy сам выпускает и продлевает сертификат Let's Encrypt, certbot и cron не нужны;
- **webhook вместо polling** — включается схемой `https://`;
- **CORS и URL Mini App** — выводятся оттуда же.

---

## 0. Предпосылки
- VPS (Ubuntu/Debian) с публичным IP, Docker + docker compose v2.
  Рекомендация: 2 ГБ RAM, 1–2 vCPU, ~40 ГБ SSD (+ 2 ГБ swap на время сборки образов). Стек в
  простое ест ~900 МБ; видео раздаёт Telegram, не VPS.
- Домен с A-записью на IP VPS: `dig +short qazaqcinema.kz` должен вернуть этот IP.
  Без корректного DNS сертификат не выпустится.
- Порты 80 и 443 открыты наружу — по ним идёт ACME-челлендж. ⚠️ На свежем Ubuntu часто активен
  ufw с одним OpenSSH; открыть ДО первого запуска (неудачные попытки бьются об rate-limit
  Let's Encrypt):
  ```bash
  ufw status && ufw allow 80/tcp && ufw allow 443/tcp
  ```
- Прод-бот от @BotFather (отдельный от dev), канал-архив, чат модерации, публичный канал и
  группа обсуждений к нему.

## 1. Код и секреты
```bash
git clone git@github.com:Bekzaat17/qazaqcinema.git && cd qazaqcinema
cp .env.prod.example .env.prod
```
Заполнить `.env.prod` (в git не коммитится):
- `PUBLIC_ORIGIN=https://qazaqcinema.kz` — единый адрес, схема `https://` и есть флаг прода.
- `ACME_EMAIL` — контакт для Let's Encrypt (непустой; пустая строка ломает парсинг Caddyfile).
- `BOT_TOKEN`, `BOT_ADMIN_CHAT_ID`, `BOT_ADMIN_USER_IDS`, `BOT_ARCHIVE_CHANNEL_ID`.
- `BOT_PUBLIC_CHANNEL_ID`, `BOT_PUBLIC_CHANNEL_USERNAME`, `BOT_DISCUSSION_GROUP_ID`
  (бот — админ канала с правом публикации и админ группы с правом удаления сообщений).
- `BOT_WEBHOOK_SECRET` и `DB_PASSWORD` — сгенерировать: `openssl rand -hex 32` / `-hex 24`.
- `PAY_KASPI_NUMBER`, `PAY_KASPI_NAME`, `PAY_KASPI_LINK` (пустое поле просто скрывает способ).
- `LEGACY_ORIGINS` — старые домены, если есть: Caddy редиректит их permanent на `PUBLIC_ORIGIN`.

Отдельных `BOT_WEBAPP_URL` / `BOT_WEBHOOK_URL` / `API_CORS_ORIGINS` / `WEB_SERVER_NAME` нет —
всё выводится из `PUBLIC_ORIGIN`.

## 2. Запуск
```bash
./start.sh prod
```
Caddy увидит `https://`-домен, сходит в Let's Encrypt по ACME и получит сертификат за секунды,
затем поднимет :443 и редирект с :80. Сертификаты живут в томе `caddy_data` и переживают
пересборку и `git pull`.

```bash
curl https://qazaqcinema.kz/api/health   # {"status":"ok","db":"ok","redis":"ok"}
curl -I http://qazaqcinema.kz            # 308 → https
```
Сертификат не выпустился — `./start.sh logs web` (частые причины в Траблшутинге).

## 3. Вебхук
Схема `https://` включает webhook: бот-контейнер сам зовёт `set_webhook` на старте, Caddy
проксирует `https://домен/tg/webhook` → `bot:8080`.
```bash
curl "https://api.telegram.org/bot<BOT_TOKEN>/getWebhookInfo"
```
Должны быть ваш URL и `pending_update_count` около нуля.

### Аварийный обход: `BOT_FORCE_POLLING`
Webhook требует, чтобы Telegram извне открыл TCP-соединение к :443. Некоторые KZ-хостеры и
транзиты режут входящий трафик именно с диапазонов Telegram (`149.154.160.0/20`,
`91.108.4.0/22`). Признак: `getWebhookInfo` показывает `Connection timed out` и растущий
`pending_update_count`, при этом сервер доступен со всего остального интернета (check-host.net).
Таймаут именно на TCP-подключении означает, что запрос не доходит до приложения — виноват
сетевой путь, а не код.

Исходящий путь при этом обычно жив, поэтому лечится polling'ом. В `.env.prod`:
```dotenv
BOT_FORCE_POLLING=1
```
и `./start.sh prod`. Флаг перебивает вывод из `PUBLIC_ORIGIN`: `webhook_url` пустеет, бот снимает
webhook и уходит в `getUpdates`, а Mini App и CORS остаются на https. Правильный фикс — попросить
хостера разблокировать диапазоны; после этого вернуть `0`.

## 4. Контент канала
Пул постов лежит в git (`content/*.yaml` + картинки) и заливается в БД сидером — на проде это
нужно после каждого пополнения:
```bash
./start.sh seed --check   # валидация YAML без БД
./start.sh seed           # upsert по slug + картинки в том uploads
```
Идемпотентно: повторный прогон не плодит дублей.

## 5. Бэкапы
На сервере работает `/root/backup_qazaqcinema.sh` (в репозитории его нет — при переезде
перенести вручную). Каждый запуск собирает ОДИН архив: дамп Postgres, том `uploads` (постеры и
карточки канала — их нет в Telegram, восстановить неоткуда), том `caddy_data` (сертификаты),
`.env.prod` и `docker-compose.yml`. Локально хранятся последние 10, `rclone sync` зеркалит папку
в Google Drive (`gdrive:qazaqcinema_backup`) — в облаке ровно те же 10. При сбое (лежал postgres,
rclone не обновил токен, полон диск) скрипт пишет админу в Telegram напрямую через Bot API.

```cron
0 5 * * * /root/backup_qazaqcinema.sh >> /root/backups/cron.log 2>&1
```

Встроенная `./start.sh backup` — только дамп БД в `backups/`, без томов и без облака; годится
как ручной снимок перед крупным обновлением.

**Восстановление** (перезапишет данные):
```bash
gunzip -c dump.sql.gz | ENV_FILE=.env.prod docker compose --env-file .env.prod \
  exec -T postgres psql -U qazaqcinema -d qazaqcinema
```

## 6. Мониторинг
`/root/monitor_qazaqcinema.sh` раз в 5 минут проверяет, что все контейнеры (postgres, redis, api,
bot, worker, web) запущены и что `/api/health` отвечает `status:ok`. Если нет — сам пробует
поднять стек (`docker compose up -d`), ждёт 20 секунд и перепроверяет; и только если не
поднялось, шлёт админу в Telegram. Сообщение уходит на СМЕНЕ состояния (файл `monitor.state`),
поэтому спама нет. Алерт идёт напрямую в `api.telegram.org`, а не через своего бота: бот и есть
то, что могло лечь.

```cron
*/5 * * * * /root/monitor_qazaqcinema.sh
```

⚠️ Чего этот способ не поймает: падение самого VPS и отвал сети — крон умрёт вместе с ними. Для
этого нужен внешний пингер (UptimeRobot, Healthchecks.io, BetterStack — у всех есть бесплатный
тариф). Одно другого не заменяет: свой крон видит «стек болен, сервер жив», внешний — «сервера нет».

## 7. Логи
**Логи контейнеров настроены в compose и трогать их не нужно**: якорь `x-logging`, json-file
`max-size 10m` × `max-file 3` = жёсткий потолок ≤30 МБ на сервис (~180 МБ на стек). ⚠️ Docker
ротирует по РАЗМЕРУ, а не по времени, и подключать сюда logrotate НЕЛЬЗЯ — драйвер держит свои
смещения в файле. Нужна временная отсечка — это смена драйвера на `journald` + `MaxRetentionSec`.

**Логи хостовых скриптов** закрывает logrotate — двумя конфигами, по владельцу логов
(файлы в системе, `git pull` их не приносит):

| Конфиг | Что ротирует | Как |
|---|---|---|
| `/etc/logrotate.d/qazaqcinema` | `/root/backups/*.log` — бэкапы, их крон, мониторинг | `monthly`, 3 архива, `maxage 90` |
| `/etc/logrotate.d/google_indexer` | `/root/logs/*.log` — SEO-крон (индексатор, отчёт) | `weekly`, 8 архивов, `copytruncate` |

```
/root/backups/*.log {
    monthly
    rotate 3
    maxage 90
    compress
    delaycompress
    missingok
    notifempty
    su root root
}
```
⚠️ **Один файл в двух конфигах — `duplicate log entry`**, после которого logrotate бросает
обработку. Поэтому `/root/logs/*.log` в конфиг `qazaqcinema` не добавлять: их уже ведёт
`google_indexer`.

⚠️ logrotate не понимает комментарий в конце строки директивы (`rotate 3  # ...` →
`bad rotation count`, и весь файл молча пропускается). Только отдельными строками.
Проверка — свой конфиг (`Handling 1 logs`, ни одного `error`) и весь набор на дубли:
```bash
logrotate -d /etc/logrotate.d/qazaqcinema
logrotate -d /etc/logrotate.conf | grep -i error
```
Гоняет системный `logrotate.timer`, отдельный крон не нужен.

## 8. SEO-крон на хосте
Два скрипта в `/root` (тоже вне репозитория):
- `google_indexer.py` — читает `sitemap.xml`, помнит в state-файле, что уже отправлял, и шлёт в
  Google Indexing API только новое и изменившееся по `<lastmod>`, держась суточной квоты 200 URL.
- `searchconsole_report.py` — ежедневный SEO-отчёт из Search Console в Telegram: показы, клики,
  позиция за сутки и за неделю против предыдущего периода, разбор запросов.

```cron
20 3 * * * /root/google_indexer.py >/dev/null 2>>/root/logs/google_indexer.cron.log
35 21 * * * /root/searchconsole_report.py >/dev/null 2>>/root/logs/searchconsole_report.cron.log
```

## 9. Обновление кода
```bash
git pull
./start.sh prod        # пересоберёт образы, применит миграции, перезапустит
```
Миграции идут автоматически сервисом `migrate` ПЕРЕД api/bot. Перед крупным обновлением —
`./start.sh backup`. Пополнили `content/` — после деплоя `./start.sh seed`.

⚠️ **Ручной `docker compose up` рвёт креды к БД.** Compose резолвит `env_file: ${ENV_FILE:-.env}`,
и `--env-file` на эту переменную НЕ влияет — она уйдёт в дефолт `.env` (dev-пароль), тогда как
живой Postgres хранит прод-пароль, заданный при инициализации тома. Итог —
`InvalidPasswordError` у migrate и api. Нужны оба флага разом:
```bash
ENV_FILE=.env.prod docker compose --env-file .env.prod -f docker-compose.yml up -d <сервис>
```
Проще и надёжнее — всегда `./start.sh prod`, она идемпотентна.

⚠️ **`./start.sh test` на прод-сервере не запускать.** Ветка `test` поднимает postgres с
`.env.test`, где `DB_NAME=qazaqcinema_test` → меняется `POSTGRES_DB` в `environment:` → compose
пересоздаёт боевой контейнер БД. Данные в томе выживают, но сайт моргает, а контейнер остаётся
с тестовым env до следующего `./start.sh prod`. Проверки здесь гонять в одноразовом контейнере,
мимо compose:
```bash
docker build --target test -t qc-checks:local .
docker run --rm -v $PWD/app:/app/app -v $PWD/tests:/app/tests qc-checks:local \
  sh -c "ruff check app tests && mypy app"
# pytest — против ОТДЕЛЬНОЙ qazaqcinema_test в том же живом постгресе
docker run --rm --network host --env-file .env.test -e DB_HOST=127.0.0.1 -e REDIS_HOST=127.0.0.1 \
  -e DB_PASSWORD="$(grep ^DB_PASSWORD= .env.prod | cut -d= -f2-)" \
  -v $PWD/app:/app/app -v $PWD/tests:/app/tests qc-checks:local pytest -q
```
Тест-БД после смены схемы пересоздать (`create_all` не добавляет колонки в существующие таблицы):
```bash
docker exec qazaqcinema-postgres-1 sh -c "dropdb -U qazaqcinema qazaqcinema_test && createdb -U qazaqcinema qazaqcinema_test"
```

## 10. Диагностика
```bash
./start.sh ps                 # статус контейнеров
./start.sh logs bot           # webhook, джобы, ошибки
./start.sh logs web           # Caddy: выпуск сертификата, TLS, проксирование
curl https://qazaqcinema.kz/api/health
```

- **Сертификат не выпускается** — `./start.sh logs web`, искать ACME-ошибки. Частое: DNS ещё не
  указывает на VPS, закрыт 80/443, или rate-limit Let's Encrypt после серии неудач (подождать час
  или взять staging-CA).
- **Вебхук не приходит** — `getWebhookInfo` и `last_error_message`. Частое: TLS ещё не поднялся,
  `PUBLIC_ORIGIN` не совпал с реальным доменом, либо хостер режет диапазоны Telegram (см. §3).
- **«chat not found» при отправке видео** — `BOT_ARCHIVE_CHANNEL_ID` должен быть `-100…`, бот —
  админ канала.
- **Под постами канала нет комментариев** — у поста inline-клавиатура: Telegram не пересылает
  такие посты в группу обсуждений. Либо кнопки, либо комментарии (см. CLAUDE.md, «Публичный канал»).
- **CORS-ошибки** — в проде всё same-origin через Caddy; если срабатывает, значит фронт ходит
  напрямую на `:8000` или `PUBLIC_ORIGIN` не тот.
- **Тесты падают с `ProgrammingError` про колонку** — пересоздать `qazaqcinema_test` (см. §9).

## Осталось за рамками
Внешний пингер (см. §6), off-site копия дампов вне Google Drive, fail2ban.
