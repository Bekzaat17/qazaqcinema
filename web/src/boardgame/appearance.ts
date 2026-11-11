import type { PlayerAppearance, Portrait } from "../ui-kit/PlayerAvatar";

export function telegramAvatar(value: string | undefined): string {
  if (!value || value.length > 2048) return "";
  try {
    const url = new URL(value);
    return url.protocol === "https:" && url.host === "t.me" && !url.username && !url.password
      && url.pathname.startsWith("/i/userpic/") && !url.hash ? value : "";
  } catch { return ""; }
}

export function savedPortrait(): Portrait {
  try { return localStorage.getItem("qazaqplay:portrait") === "female" ? "female" : "male"; }
  catch { return "male"; }
}
export function savePortrait(value: Portrait) {
  try { localStorage.setItem("qazaqplay:portrait", value); }
  catch { /* Выбор остаётся в текущем сеансе. */ }
}

const BOT_PORTRAITS: Record<string, Portrait> = {
  balanced: "female", builder: "male", careful: "female",
};
export function playerAppearance(
  player: { id: string; bot: string },
  appearances?: Record<string, PlayerAppearance>,
): PlayerAppearance {
  const saved = appearances?.[player.id];
  return saved ? { ...saved, avatar_url: telegramAvatar(saved.avatar_url) }
    : { portrait: BOT_PORTRAITS[player.bot] ?? "male" };
}
