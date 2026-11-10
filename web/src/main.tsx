import { StrictMode, Suspense, lazy, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";

import ErrorBoundary from "./components/ErrorBoundary";
import "./index.css";
import { initWebApp } from "./lib/telegram";
import { isQuestLaunch } from "./quest/launch";

const App = lazy(() => import("./App"));
const QuestApp = lazy(() => import("./quest/QuestApp"));

function AppRouter() {
  const [quest, setQuest] = useState(isQuestLaunch);
  useEffect(() => {
    const onNavigate = () => setQuest(isQuestLaunch());
    window.addEventListener("popstate", onNavigate);
    return () => window.removeEventListener("popstate", onNavigate);
  }, []);
  return (
    <Suspense
      fallback={
        <div role="status" style={{ padding: 32 }}>
          Жүктелуде…
        </div>
      }
    >
      {quest ? <QuestApp /> : <App />}
    </Suspense>
  );
}

initWebApp(); // ready + expand + брендовые цвета шапки/фона (dev-preview: no-op вне Telegram)

const root = document.getElementById("root");
if (root) {
  createRoot(root).render(
    <StrictMode>
      {/* Снаружи App: падение самого App — как раз тот случай, ради которого граница и
          нужна, и она обязана выжить его размонтирование. */}
      <ErrorBoundary>
        <AppRouter />
      </ErrorBoundary>
    </StrictMode>,
  );
}
