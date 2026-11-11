const KEY = "qazaqplay:game-trials:v1";
export const FREE_GAMES = 3;
export class PracticeTrials {
  private started = 0;
  constructor() {
    try {
      const value = Number(localStorage.getItem(KEY) ?? 0);
      if (Number.isSafeInteger(value) && value >= 0) this.started = value;
    } catch { /* Локальная тренировка работает и без доступа к хранилищу. */ }
  }
  access() {
    return { games_started: this.started, free_left: Math.max(0, FREE_GAMES - this.started),
      allowed: this.started < FREE_GAMES, channel_url: "" };
  }
  recordStart() {
    this.started++;
    try { localStorage.setItem(KEY, String(this.started)); } catch { /* Остаётся в памяти. */ }
  }
}
