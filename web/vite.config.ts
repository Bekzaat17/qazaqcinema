import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Dev: проксируем API и постеры на бэкенд, чтобы Mini App ходил «на свой же origin» —
// тогда CORS не нужен, а поведение как в проде (там оба пути обслуживает Nginx — Фаза 10).
// Адрес бэкенда берём из API_TARGET: в Docker-dev это http://api:8000 (имя сервиса,
// задаётся в docker-compose.dev.yml), при ручном запуске на хосте — http://localhost:8000.
declare const process: { env: Record<string, string | undefined> };
const API_TARGET = process.env.API_TARGET ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: API_TARGET, changeOrigin: true },
      "/posters": { target: API_TARGET, changeOrigin: true },
    },
  },
});
