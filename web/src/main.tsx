import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "./App";
import "./index.css";
import { initWebApp } from "./lib/telegram";

initWebApp(); // ready + expand + брендовые цвета шапки/фона (dev-preview: no-op вне Telegram)

const root = document.getElementById("root");
if (root) {
  createRoot(root).render(
    <StrictMode>
      <App />
    </StrictMode>,
  );
}
