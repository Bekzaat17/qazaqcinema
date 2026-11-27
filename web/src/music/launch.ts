// Куда открыть Mini App: кинотеатр или музыка, и на каком треке/плейлисте.
//
// Музыка — отдельный экран со своей навигацией, но то же приложение и та же сессия:
// переключаемся без перезагрузки (history.pushState), чтобы не терять initData.

import { getWebApp } from "../lib/telegram";

export interface MusicTarget {
  trackId: number | null;
  playlistCode: string | null;
}

const START = /^(?:[a-z]{1,16}-)?(?:(music)|t_(\d+)|pl_([A-Za-z0-9_-]{4,16}))$/;

function startParam(): string {
  const query = new URLSearchParams(window.location.search);
  return query.get("tgWebAppStartParam") ?? getWebApp()?.initDataUnsafe?.start_param ?? "";
}

/** Цель из ссылки: `?app=music&t=42&pl=code` (кнопка бота) или `startapp=t_42`. */
export function musicTarget(): MusicTarget | null {
  const query = new URLSearchParams(window.location.search);
  if (query.get("view") === "cinema") return null;
  if (query.get("app") === "music") {
    const track = /^\d+$/.exec(query.get("t") ?? "");
    const playlist = /^[A-Za-z0-9_-]{4,16}$/.exec(query.get("pl") ?? "");
    return { trackId: track ? Number(track[0]) : null, playlistCode: playlist ? playlist[0] : null };
  }
  const match = START.exec(startParam());
  if (!match) return null;
  return { trackId: match[2] ? Number(match[2]) : null, playlistCode: match[3] ?? null };
}

export function isMusicLaunch(): boolean {
  return musicTarget() !== null;
}

/**
 * Переключить экран без перезагрузки, сохранив Telegram initData и сессию SDK.
 *
 * ⚠️ Музыка — это `/?app=music`, а не путь `/music`: путь `/music` отдаёт SEO-страницу
 * (Caddy ведёт его на api), и обновление WebView открыло бы её вместо приложения.
 */
export function navigateApp(target: "music" | "cinema"): void {
  const url = new URL(window.location.href);
  url.pathname = "/";
  for (const key of ["app", "t", "pl"]) url.searchParams.delete(key);
  if (target === "cinema") url.searchParams.set("view", "cinema");
  else {
    url.searchParams.delete("view");
    url.searchParams.set("app", "music");
  }
  window.history.pushState(null, "", url);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

/** Ссылка на трек для «Бөлісу»: открывает Mini App сразу на нём. */
export function trackShareUrl(botUsername: string, trackId: number): string {
  return `https://t.me/${botUsername}?startapp=t_${trackId}`;
}

/** Окно «Поделиться» Telegram: выбор чата и готовый текст со ссылкой. */
export function shareLink(url: string, text: string): string {
  return `https://t.me/share/url?url=${encodeURIComponent(url)}&text=${encodeURIComponent(text)}`;
}
