// Тонкая обёртка над Telegram WebApp SDK.

export function getWebApp() {
  return window.Telegram?.WebApp;
}

export function getInitData(): string {
  return window.Telegram?.WebApp?.initData ?? "";
}

export function ready(): void {
  window.Telegram?.WebApp?.ready();
}

/** Открыть чат с ботом по inline-запросу movie_<id> (защищённая выдача видео). */
export function watchMovie(movieId: number): void {
  window.Telegram?.WebApp?.switchInlineQuery(`movie_${movieId}`, ["users"]);
}
