import { getWebApp } from "../lib/telegram";
import { isQuestStartParam } from "./startParam";

export function isQuestLaunch(): boolean {
  const query = new URLSearchParams(window.location.search);
  if (query.get("view") === "cinema") return false;
  return (
    window.location.pathname.replace(/\/$/, "") === "/quest" ||
    query.get("game") === "quest" ||
    isQuestStartParam(query.get("tgWebAppStartParam")) ||
    isQuestStartParam(getWebApp()?.initDataUnsafe?.start_param)
  );
}

/** Переключаем экраны без перезагрузки, сохраняя Telegram initData и сессию SDK. */
export function navigateApp(target: "quest" | "cinema"): void {
  const url = new URL(window.location.href);
  url.pathname = target === "quest" ? "/quest" : "/";
  url.searchParams.delete("game");
  if (target === "cinema") url.searchParams.set("view", "cinema");
  else url.searchParams.delete("view");
  window.history.pushState(null, "", url);
  window.dispatchEvent(new PopStateEvent("popstate"));
}
