import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Dev: проксируем API и постеры на бэкенд, чтобы Mini App ходил «на свой же origin» —
// тогда CORS не нужен, а поведение как в проде (там оба пути обслуживает Nginx — Фаза 10).
// Если бэкенд не на :8000 — поменяй эту строку. Прод-клиенту хватает VITE_API_URL.
const API_TARGET = "http://localhost:8000";

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
