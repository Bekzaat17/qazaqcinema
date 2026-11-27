import { StrictMode, Suspense, lazy, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";

import ErrorBoundary from "./components/ErrorBoundary";
import "./index.css";
import { initWebApp } from "./lib/telegram";
import { isMusicLaunch } from "./music/launch";

const Showcase = lazy(() => import("./ui-kit/Showcase"));
const App = lazy(() => import("./App"));
const MusicApp = lazy(() => import("./music/MusicApp"));

function AppRouter() {
  const [music, setMusic] = useState(isMusicLaunch);
  const [showcase, setShowcase] = useState(() => location.pathname === "/ui-kit");
  useEffect(() => {
    const onNavigate = () => {
      setMusic(isMusicLaunch());
      setShowcase(location.pathname === "/ui-kit");
    };
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
      {showcase ? <Showcase /> : music ? <MusicApp /> : <App />}
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
