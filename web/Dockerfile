# Прод-образ фронта: собираем SPA (node) → раздаём статику + reverse-proxy + авто-TLS (Caddy).
# Один образ во всех средах; домен/TLS/CORS-режим переключаются ОДНОЙ переменной PUBLIC_ORIGIN
# (http://localhost → HTTP локально; https://домен → авто-сертификат Let's Encrypt в проде).
# Caddy сам выпускает и продлевает сертификат — certbot/cron не нужны. В dev при активной
# разработке можно поднять Vite на хосте (host-venv), этот образ раздаёт собранную статику.
FROM node:20-alpine AS build
WORKDIR /web
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM caddy:2-alpine
COPY Caddyfile /etc/caddy/Caddyfile
COPY --from=build /web/dist /srv
