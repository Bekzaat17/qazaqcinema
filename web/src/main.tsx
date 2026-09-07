import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "./App";
import ErrorBoundary from "./components/ErrorBoundary";
import "./index.css";
import { initWebApp } from "./lib/telegram";

initWebApp(); // ready + expand + брендовые цвета шапки/фона (dev-preview: no-op вне Telegram)

const root = document.getElementById("root");
if (root) {
  createRoot(root).render(
    <StrictMode>
      {/* Снаружи App: падение самого App — как раз тот случай, ради которого граница и
          нужна, и она обязана выжить его размонтирование. */}
      <ErrorBoundary>
        <App />
      </ErrorBoundary>
    </StrictMode>,
  );
}
