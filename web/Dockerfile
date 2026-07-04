# Прод-образ фронта: собираем SPA (node) → раздаём статику + проксируем API (nginx).
# Используется только ./start.sh prod (docker-compose.prod.yml). В dev фронт крутит
# Vite-дев-сервер (docker-compose.dev.yml), этот Dockerfile там не участвует.
FROM node:20-alpine AS build
WORKDIR /web
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /web/dist /usr/share/nginx/html
