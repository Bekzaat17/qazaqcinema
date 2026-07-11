# DEPLOY.md — вывод QazaqCinema в прод

Прод — тот же Docker-стек, что и локально (`./start.sh`), отличие ТОЛЬКО в env-файле
(`.env.prod`). Этот файл — пошаговый чеклист «с нуля до живого бота на домене».

Что даёт прод-режим сверх локального (всё — от ОДНОЙ переменной `PUBLIC_ORIGIN`):
- **Авто-TLS (:443)** — обязателен для Telegram Mini App. **Caddy сам выпускает и продлевает**
  сертификат Let's Encrypt. Никакого certbot, никаких cron — заполнил env и забыл.
- **Webhook вместо polling** — бот слушает апдейты по HTTPS (включается схемой `https://` в `PUBLIC_ORIGIN`).
- **Caddy** — раздаёт SPA и проксирует `/api`, `/posters`, вебхук `/tg/` — всё на одном домене.

---

## 0. Предпосылки
- VPS (Ubuntu/Debian) с публичным IP, установлены **Docker** + **docker compose v2**.
  Рекомендация: **2 ГБ RAM, 1–2 vCPU, ~40 ГБ SSD** (+ желательно 2 ГБ swap на время сборки образов).
  Весь стек в простое ест ~900 МБ; видео раздаёт Telegram (не VPS) → сервер остаётся лёгким.
  1 ГБ RAM технически заведётся, но три Python-процесса + Postgres впритык и сборка может уйти в OOM.
- **Домен** (или поддомен), например `qazaqcinema.rehubpro.kz`.
- Порты **80 и 443** открыты наружу (Caddy берёт по ним ACME-челлендж; firewall/ufw — разреши).
- Прод-бот от [@BotFather](https://t.me/BotFather) (отдельный от dev), канал-архив, чат модерации.

## 1. DNS
Заведи **A-запись** (под)домена на IP VPS:
```
qazaqcinema.rehubpro.kz.  A  <IP_VPS>
```
Проверь: `dig +short qazaqcinema.rehubpro.kz` → должен вернуть IP VPS. Это условие авто-выпуска
сертификата — без корректного DNS Caddy не получит TLS.

## 2. Код и секреты
```bash
git clone <repo> qazaqcinema && cd qazaqcinema
cp .env.prod.example .env.prod
```
Заполни `.env.prod` РЕАЛЬНЫМИ значениями (файл в git не коммитится — секреты):
- **`PUBLIC_ORIGIN=https://qazaqcinema.rehubpro.kz`** — ЕДИНЫЙ адрес. Из него выводятся авто-TLS,
  CORS, URL Mini App и режим бота (webhook). Схема `https://` обязательна — это и есть флаг прода.
- **`ACME_EMAIL=you@example.com`** — твой e-mail для Let's Encrypt (контакт/уведомления).
- `BOT_TOKEN` — прод-токен от @BotFather.
- `BOT_ADMIN_CHAT_ID`, `BOT_ADMIN_USER_IDS`, `BOT_ARCHIVE_CHANNEL_ID`.
- `BOT_WEBHOOK_SECRET` — сгенерируй: `openssl rand -hex 32`.
- `DB_PASSWORD` — сильный пароль: `openssl rand -hex 24`.
- `PAY_KASPI_*`.

> Домен теперь в ОДНОМ месте — `PUBLIC_ORIGIN`. Отдельные `BOT_WEBAPP_URL`/`BOT_WEBHOOK_URL`/
> `API_CORS_ORIGINS`/`WEB_SERVER_NAME` больше не нужны (выводятся из `PUBLIC_ORIGIN`).

## 3. Запуск (сертификат выпустится сам)
```bash
./start.sh prod
```
Caddy на старте увидит `https://`-домен, сходит в Let's Encrypt по ACME (порт 80/443) и получит
сертификат — **автоматически, за секунды**. Затем сам поднимет :443 и редирект с :80.

Проверь:
```bash
curl https://qazaqcinema.rehubpro.kz/api/health   # {"status":"ok",...}
curl -I http://qazaqcinema.rehubpro.kz            # 308 redirect → https
```
Если сертификат не выпустился — смотри логи Caddy: `./start.sh logs web` (частые причины —
DNS ещё не распространился или закрыт порт 80/443; см. Траблшутинг).

## 4. Вебхук
Схема `https://` в `PUBLIC_ORIGIN` включает webhook-режим: бот-контейнер сам вызывает `set_webhook`
на старте (`app/main.py`), Caddy проксирует `https://qazaqcinema.rehubpro.kz/tg/webhook` → `bot:8080`.
Проверь регистрацию:
```bash
curl "https://api.telegram.org/bot<BOT_TOKEN>/getWebhookInfo"
```
Должны быть твой URL и `pending_update_count` близко к 0. Открой Web App в Telegram — каталог
грузится, «Көру» шлёт видео.

## 5. Бэкапы БД (cron)
Ручной дамп: `./start.sh backup` → `backups/qazaqcinema-YYYYmmdd-HHMMSS.sql.gz` (ротация: 14 последних).
Ежедневно в 03:30 (crontab на VPS):
```cron
30 3 * * * cd /path/to/qazaqcinema && ./start.sh backup >> backups/backup.log 2>&1
```
**Восстановление** (осторожно — перезапишет данные):
```bash
gunzip -c backups/qazaqcinema-ГГГГ.sql.gz | \
  docker compose --env-file .env.prod exec -T postgres psql -U qazaqcinema -d qazaqcinema
```

## 6. Продление сертификата
**Ничего делать не нужно.** Caddy продлевает сертификат автоматически (~за 30 дней до истечения)
и держит его в томе `caddy_data` — переживает пересборку и `git pull`.

## 7. Обновление кода
```bash
git pull
./start.sh prod        # пересоберёт образы, применит миграции (сервис migrate), перезапустит
```
Миграции идут автоматически (сервис `migrate` ПЕРЕД api/bot). Сертификат из тома `caddy_data`
никуда не девается. Перед крупным обновлением — `./start.sh backup`.

## 8. Управление / диагностика
```bash
./start.sh ps                 # статус контейнеров
./start.sh logs bot           # логи бота (webhook/ошибки)
./start.sh logs web           # логи Caddy (выпуск сертификата, TLS, проксирование)
./start.sh down               # остановить (тома с БД/постерами/сертификатами сохраняются)
curl https://qazaqcinema.rehubpro.kz/api/health   # redis+db+status
```

## Траблшутинг
- **Сертификат не выпускается** — `./start.sh logs web` (ищи ACME-ошибки). Частое: DNS ещё не
  указывает на VPS (`dig +short <домен>`), закрыт порт 80/443 (ufw/облачный firewall), или упёрся
  в rate-limit Let's Encrypt после многих рестартов с ошибкой (подожди час или используй staging-CA).
- **Вебхук не приходит** — `getWebhookInfo` (`last_error_message`). Частое: TLS ещё не поднялся
  (бот шлёт `set_webhook`, но Telegram не достучался по HTTPS) — дождись сертификата; либо
  `PUBLIC_ORIGIN` не совпал с реальным доменом.
- **«chat not found» при отправке видео** — `BOT_ARCHIVE_CHANNEL_ID` должен быть `-100…`, бот — админ канала.
- **CORS-ошибки** — в проде всё same-origin (Caddy), CORS не должен срабатывать; если да — проверь,
  что `PUBLIC_ORIGIN` = реальный домен, а фронт не ходит напрямую на `:8000`.

## Осталось за рамками (не блокеры)
- Мониторинг/алерты (uptime `/api/health`), off-site копия бэкапов, fail2ban/ufw на VPS.
