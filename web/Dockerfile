# Прод-образ фронта: собираем SPA (node) → раздаём статику + reverse-proxy (nginx).
# Один образ во всех средах; TLS/домен переключаются env-переменными (WEB_TLS/WEB_SERVER_NAME) —
# выбор конфига делает 40-qc-config.sh в entrypoint (см. web/nginx/). В dev при активной
# разработке можно поднять Vite на хосте (host-venv), этот образ раздаёт собранную статику.
FROM node:20-alpine AS build
WORKDIR /web
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
# Конфиги-шаблоны (не в /etc/nginx/templates/, чтобы штатный envsubst их не трогал) +
# скрипт-селектор в entrypoint nginx (запускается ДО старта nginx).
COPY nginx/http.conf nginx/https.conf.template /etc/nginx/qc/
COPY nginx/40-qc-config.sh /docker-entrypoint.d/40-qc-config.sh
RUN chmod +x /docker-entrypoint.d/40-qc-config.sh
COPY --from=build /web/dist /usr/share/nginx/html
