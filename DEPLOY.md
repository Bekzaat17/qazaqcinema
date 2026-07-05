# DEPLOY.md — вывод QazaqCinema в прод

Прод — тот же Docker-стек, что и локально (`./start.sh`), отличие ТОЛЬКО в env-файле
(`.env.prod`). Этот файл — пошаговый чеклист «с нуля до живого бота на домене». Всё, что
можно, уже параметризовано; здесь — живые шаги, которые выполняешь на VPS.

Что даёт прод-режим сверх локального:
- **Webhook вместо polling** — бот слушает апдейты по HTTPS (включается `BOT_WEBHOOK_URL`).
- **TLS (:443)** — обязателен: Telegram Mini App работает только по HTTPS.
- **Nginx** — раздаёт SPA, проксирует `/api`, `/posters`, вебхук `/tg/` — всё на одном домене.

---

## 0. Предпосылки
- VPS (Ubuntu/Debian) с публичным IP, установлены **Docker** + **docker compose v2**.
- **Домен** (или поддомен), например `cinema.example`.
- Прод-бот от [@BotFather](https://t.me/BotFather) (отдельный от dev), канал-архив, чат модерации.

## 1. DNS
Заведи **A-запись** домена на IP VPS:
```
cinema.example.  A  <IP_VPS>
```
Проверь: `dig +short cinema.example` → должен вернуть IP VPS.

## 2. Код и секреты
```bash
git clone <repo> qazaqcinema && cd qazaqcinema
cp .env.prod.example .env.prod
```
Заполни `.env.prod` РЕАЛЬНЫМИ значениями (файл в git не коммитится — секреты):
- `BOT_TOKEN` — прод-токен от @BotFather.
- `BOT_ADMIN_CHAT_ID`, `BOT_ADMIN_USER_IDS`, `BOT_ARCHIVE_CHANNEL_ID`.
- `BOT_WEBAPP_URL=https://cinema.example/` — домен Web App.
- `BOT_WEBHOOK_URL=https://cinema.example` — тот же домен (без пути); наличие → бот в режиме webhook.
- `BOT_WEBHOOK_SECRET` — сгенерируй: `openssl rand -hex 32`.
- `DB_PASSWORD` — сильный пароль: `openssl rand -hex 24`.
- `WEB_SERVER_NAME=cinema.example`, `WEB_TLS=true`.
- `API_CORS_ORIGINS=https://cinema.example`, `PAY_KASPI_*`.

> Домен фигурирует в `BOT_WEBAPP_URL`, `BOT_WEBHOOK_URL`, `WEB_SERVER_NAME`, `API_CORS_ORIGINS`
> — везде один и тот же.

## 3. Первый запуск (пока по HTTP — ради выпуска сертификата)
`WEB_TLS=true` уже стоит, но сертификата ещё нет — nginx **сам поднимется на :80** и будет
обслуживать ACME-челлендж (безопасный фолбэк, см. `web/nginx/40-qc-config.sh`).
```bash
./start.sh prod
```
Проверь, что HTTP отвечает: `curl http://cinema.example/api/health` → `{"status":"ok",...}`.

## 4. TLS-сертификат (Let's Encrypt / certbot)
Выпусти сертификат (webroot-метод — nginx уже отдаёт `/.well-known/acme-challenge/`):
```bash
docker compose --env-file .env.prod --profile certbot run --rm certbot \
  certonly --webroot -w /var/www/certbot \
  -d cinema.example --email you@example.com --agree-tos --no-eff-email
```
Сертификат ляжет в `./certbot/conf/live/cinema.example/`. Теперь перезапусти web — он увидит
сертификат и переключится на :443:
```bash
docker compose --env-file .env.prod restart web
```
Проверь: `curl https://cinema.example/api/health` → `{"status":"ok",...}`, `http://…` редиректит на `https://…`.

## 5. Вебхук
При `BOT_WEBHOOK_URL` бот-контейнер сам вызывает `set_webhook` на старте (`app/main.py`),
Nginx проксирует `https://cinema.example/tg/webhook` → `bot:8080`. Проверь регистрацию:
```bash
curl "https://api.telegram.org/bot<BOT_TOKEN>/getWebhookInfo"
```
Должны быть твой URL и `pending_update_count` близко к 0. Открой Web App в Telegram — каталог
грузится, «Көру» шлёт видео.

## 6. Бэкапы БД (cron)
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

## 7. Продление сертификата (cron)
Let's Encrypt живёт 90 дней. Дважды в день пытаемся продлить (реально продлит только под истечение)
и перезагружаем nginx:
```cron
15 2,14 * * * cd /path/to/qazaqcinema && docker compose --env-file .env.prod --profile certbot run --rm certbot renew --quiet && docker compose --env-file .env.prod exec web nginx -s reload
```

## 8. Обновление кода
```bash
git pull
./start.sh prod        # пересоберёт образы, применит миграции (сервис migrate), перезапустит
```
Миграции идут автоматически (сервис `migrate` ПЕРЕД api/bot). Перед крупным обновлением — `./start.sh backup`.

## 9. Управление / диагностика
```bash
./start.sh ps                 # статус контейнеров
./start.sh logs bot           # логи бота (webhook/ошибки)
./start.sh logs web           # логи nginx (какой конфиг выбран, TLS)
./start.sh down               # остановить (тома с БД/постерами сохраняются)
curl https://cinema.example/api/health   # redis+db+status
```

## Траблшутинг
- **nginx на :80 вместо :443** — нет сертификата или `WEB_TLS≠true`. Логи web покажут причину
  (`[qc] nginx: …`). Выпусти сертификат (шаг 4) и `restart web`.
- **Вебхук не приходит** — проверь `getWebhookInfo` (`last_error_message`). Частое: `BOT_WEBHOOK_URL`
  не совпал с реальным доменом/сертификатом, либо TLS ещё не поднялся (бот шлёт `set_webhook`, но
  Telegram не может достучаться по HTTPS). TLS должен работать ДО того, как заведётся вебхук.
- **«chat not found» при отправке видео** — `BOT_ARCHIVE_CHANNEL_ID` должен быть `-100…`, бот — админ канала.
- **CORS-ошибки** — в проде всё same-origin (nginx), CORS не должен срабатывать; если да — проверь,
  что фронт ходит на тот же домен (`BOT_WEBAPP_URL`), а не напрямую на `:8000`.

## Осталось за рамками (не блокеры)
- Мониторинг/алерты (uptime `/api/health`), off-site копия бэкапов, fail2ban/ufw на VPS.
