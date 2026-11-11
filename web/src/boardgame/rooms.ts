// Ссылка не открывается и не запрашивается: извлекаем только проверенный код.
export function roomCode(value: string): string {
  const raw = value.trim();
  const direct = /^(?:quest_room_)?([a-f0-9]{10})$/i.exec(raw.replace(/[\s-]/g, ""));
  if (direct) return direct[1].toUpperCase();
  try {
    const url = new URL(raw);
    for (const key of ["startapp", "room", "tgWebAppStartParam"]) {
      const match = /^(?:quest_room_)?([a-f0-9]{10})$/i.exec(url.searchParams.get(key) ?? "");
      if (match) return match[1].toUpperCase();
    }
  } catch { /* Пользователь ещё вводит код. */ }
  return "";
}
export const roomLink = (botUrl: string, code: string) => `${botUrl}?startapp=quest_room_${code}`;
export const shareRoomLink = (botUrl: string, code: string) =>
  `https://t.me/share/url?url=${encodeURIComponent(roomLink(botUrl, code))}&text=${encodeURIComponent("QazaqPlay: бірге ойнайық! Бөлме коды: " + code)}`;
