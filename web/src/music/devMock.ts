// DEV-ONLY мок музыкальных ручек: раздел открывается в обычном браузере без бэкенда.
// Подключается из lib/devMock (сам он в прод-сборку не попадает).

import type { MusicHome, Playlist, PlaylistDetail, Track } from "./api";

let toneUrl: string | null = null;

/** Тихий синус на 40 с в WAV: плеер проверяется без внешних файлов и сети. */
function tone(): string {
  if (toneUrl) return toneUrl;
  const rate = 8000;
  const seconds = 40;
  const samples = rate * seconds;
  const buffer = new ArrayBuffer(44 + samples);
  const view = new DataView(buffer);
  const write = (offset: number, text: string) => [...text].forEach((c, i) => view.setUint8(offset + i, c.charCodeAt(0)));
  write(0, "RIFF");
  view.setUint32(4, 36 + samples, true);
  write(8, "WAVEfmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, rate, true);
  view.setUint32(28, rate, true);
  view.setUint16(32, 1, true);
  view.setUint16(34, 8, true);
  write(36, "data");
  view.setUint32(40, samples, true);
  for (let i = 0; i < samples; i++) view.setUint8(44 + i, 128 + Math.round(18 * Math.sin((2 * Math.PI * 330 * i) / rate)));
  toneUrl = URL.createObjectURL(new Blob([buffer], { type: "audio/wav" }));
  return toneUrl;
}

const raw: [string, string, number, boolean][] = [
  ["Ауру", "Қайрат Нұртас", 214, true],
  ["Қара-Торғай", "Ninety One", 198, true],
  ["Сен", "Dimash", 241, false],
  ["Ақ көйлек", "Ирина Кайратовна", 187, true],
  ["Туған жер", "Мақпал Жүнісова", 263, true],
  ["Мама", "Jah Khalib", 205, true],
  ["Ұмытылмас күндер", "Kenshi", 176, true],
  ["Алматы түні", "Qarakesek", 229, true],
];

const TRACKS: Track[] = raw.map(([title, performer, duration, streamable], index) => ({
  id: index + 1,
  title,
  performer,
  duration_sec: duration,
  cover_url: index % 3 === 0 ? `https://picsum.photos/seed/music${index}/320/320` : null,
  stream_url: streamable ? "tone" : null,
  play_count: 100 - index * 9,
  saves_count: 20 - index,
}));

const LIBRARY = new Set([1, 2, 4]);
const PLAYLISTS: { playlist: Playlist; ids: number[] }[] = [
  {
    playlist: { id: 1, title: "Жолға", track_count: 4, covers: [], share_url: "https://t.me/qazaqcinema_bot?startapp=pl_demo1234", is_own: true },
    ids: [1, 2, 3, 5],
  },
];

const withStream = (track: Track): Track => ({ ...track, stream_url: track.stream_url ? tone() : null });
const byIds = (ids: number[]) => ids.map((id) => TRACKS.find((t) => t.id === id)).filter((t): t is Track => !!t).map(withStream);

function detail(entry: (typeof PLAYLISTS)[number]): PlaylistDetail {
  return { ...entry.playlist, track_count: entry.ids.length, tracks: byIds(entry.ids) };
}

export function mockMusic(path: string, url: URL, init?: RequestInit): { handled: boolean; data?: unknown; status?: number } {
  const method = init?.method ?? "GET";
  const body = init?.body ? (JSON.parse(String(init.body)) as Record<string, string>) : {};
  if (path === "/api/music/home") {
    const home: MusicHome = {
      recent: TRACKS.map(withStream),
      popular: [...TRACKS].sort((a, b) => b.play_count - a.play_count).map(withStream),
      requests: [{ query: "Скриптонит — Вечеринка", votes: 7 }, { query: "Ұлытау — Сарыарқа", votes: 3 }],
    };
    return { handled: true, data: home };
  }
  if (path === "/api/music/tracks") {
    const q = (url.searchParams.get("q") ?? "").toLowerCase();
    return { handled: true, data: TRACKS.filter((t) => `${t.performer} ${t.title}`.toLowerCase().includes(q)).map(withStream) };
  }
  let m = /^\/api\/music\/tracks\/(\d+)$/.exec(path);
  if (m) return { handled: true, data: byIds([Number(m[1])])[0] };
  if (/^\/api\/music\/tracks\/\d+\/(played)$/.test(path)) return { handled: true, data: undefined };
  if (/\/send$/.test(path)) return { handled: true, data: { status: "sent", count: 1 } };
  if (path === "/api/music/library") return { handled: true, data: byIds([...LIBRARY].reverse()) };
  if (path === "/api/music/library/ids") return { handled: true, data: { ids: [...LIBRARY] } };
  m = /^\/api\/music\/library\/(\d+)$/.exec(path);
  if (m) {
    if (method === "DELETE") LIBRARY.delete(Number(m[1]));
    else LIBRARY.add(Number(m[1]));
    return { handled: true, data: undefined };
  }
  if (path === "/api/music/requests") return { handled: true, data: { votes: 2 } };
  if (path === "/api/music/playlists" && method === "POST") {
    const playlist: Playlist = { id: PLAYLISTS.length + 1, title: body.title || "Жаңа плейлист", track_count: 0, covers: [], share_url: "https://t.me/qazaqcinema_bot?startapp=pl_new12345", is_own: true };
    PLAYLISTS.push({ playlist, ids: [] });
    return { handled: true, data: playlist };
  }
  if (path === "/api/music/playlists") return { handled: true, data: PLAYLISTS.map((e) => ({ ...e.playlist, track_count: e.ids.length })) };
  m = /^\/api\/music\/playlists\/(\d+)\/tracks\/(\d+)$/.exec(path);
  if (m) {
    const entry = PLAYLISTS.find((e) => e.playlist.id === Number(m![1]));
    const id = Number(m[2]);
    if (!entry) return { handled: true, status: 404 };
    if (method === "DELETE") {
      entry.ids = entry.ids.filter((x) => x !== id);
      return { handled: true, data: undefined };
    }
    const status = entry.ids.includes(id) ? "duplicate" : "added";
    if (status === "added") entry.ids.push(id);
    return { handled: true, data: { status } };
  }
  m = /^\/api\/music\/playlists\/(\d+)$/.exec(path);
  if (m) {
    const entry = PLAYLISTS.find((e) => e.playlist.id === Number(m![1]));
    if (!entry) return { handled: true, status: 404 };
    if (method === "PATCH") entry.playlist.title = body.title;
    if (method === "DELETE") PLAYLISTS.splice(PLAYLISTS.indexOf(entry), 1);
    return { handled: true, data: method === "GET" ? detail(entry) : undefined };
  }
  if (/^\/api\/music\/shared\/[^/]+$/.test(path)) return { handled: true, data: { ...detail(PLAYLISTS[0]), is_own: false } };
  if (/^\/api\/music\/shared\/[^/]+\/save$/.test(path)) return { handled: true, data: PLAYLISTS[0].playlist };
  return { handled: false };
}
