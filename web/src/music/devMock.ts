// DEV-ONLY мок музыкальных ручек: раздел открывается в обычном браузере без бэкенда.
// Подключается из lib/devMock (сам он в прод-сборку не попадает).

import type { Collection, MusicHome, Playlist, PlaylistDetail, Track } from "./api";

const raw: [string, string, number][] = [
  ["Ауру", "Қайрат Нұртас", 214],
  ["Қара-Торғай", "Ninety One", 198],
  ["Сен", "Dimash", 241],
  ["Ақ көйлек", "Ирина Кайратовна", 187],
  ["Туған жер", "Мақпал Жүнісова", 263],
  ["Мама", "Jah Khalib", 205],
  ["Ұмытылмас күндер", "Kenshi", 176],
  ["Алматы түні", "Qarakesek", 229],
];

const TRACKS: Track[] = raw.map(([title, performer, duration], index) => ({
  id: index + 1,
  title,
  performer,
  duration_sec: duration,
  play_count: 100 - index * 9,
  saves_count: 20 - index,
}));

const LIBRARY = new Set([1, 2, 4]);
const PLAYLISTS: { playlist: Playlist; ids: number[] }[] = [
  {
    playlist: { id: 1, title: "Жолға", track_count: 4, share_code: "demo1234", share_url: "https://t.me/qazaqcinema_bot?startapp=pl_demo1234", is_own: true, is_public: false, saves_count: 0 },
    ids: [1, 2, 3, 5],
  },
];

const byIds = (ids: number[]) => ids.map((id) => TRACKS.find((t) => t.id === id)).filter((t): t is Track => !!t);

const PUBLIC: Playlist[] = [
  { id: 90, title: "Той әндері", track_count: 5, share_code: "toi12345", share_url: "https://t.me/qazaqcinema_bot?startapp=pl_toi12345", is_own: false, is_public: true, saves_count: 14 },
  { id: 91, title: "Түнгі Алматы", track_count: 4, share_code: "almaty99", share_url: "https://t.me/qazaqcinema_bot?startapp=pl_almaty99", is_own: false, is_public: true, saves_count: 6 },
];
const COLLECTIONS: Collection[] = [
  { key: "week_hits", title: "Аптаның хиттері", subtitle: "Осы аптада ең көп тыңдалғандар", track_count: 6, performers: ["Қайрат Нұртас", "Ninety One", "Dimash"] },
  { key: "new", title: "Жаңа әндер", subtitle: "Тыңдаушылар соңғы қосқандар", track_count: 8, performers: ["Qarakesek", "Kenshi", "Jah Khalib"] },
  { key: "best", title: "Үздіктер", subtitle: "Ең көп сақталған әндер", track_count: 8, performers: ["Қайрат Нұртас", "Ninety One", "Dimash"] },
];

function detail(entry: (typeof PLAYLISTS)[number]): PlaylistDetail {
  return { ...entry.playlist, track_count: entry.ids.length, tracks: byIds(entry.ids) };
}

export function mockMusic(path: string, url: URL, init?: RequestInit): { handled: boolean; data?: unknown; status?: number } {
  const method = init?.method ?? "GET";
  const body = init?.body ? (JSON.parse(String(init.body)) as Record<string, unknown>) : {};
  if (path === "/api/music/home") {
    const home: MusicHome = {
      recent: [...TRACKS].reverse(),
      popular: [...TRACKS].sort((a, b) => b.play_count - a.play_count),
      requests: [{ query: "Скриптонит — Вечеринка", votes: 7 }, { query: "Ұлытау — Сарыарқа", votes: 3 }],
    };
    return { handled: true, data: home };
  }
  if (path === "/api/music/tracks") {
    const q = (url.searchParams.get("q") ?? "").toLowerCase();
    return { handled: true, data: TRACKS.filter((t) => `${t.performer} ${t.title}`.toLowerCase().includes(q)) };
  }
  let m: RegExpExecArray | null = /^\/api\/music\/tracks\/(\d+)\/details$/.exec(path);
  if (m) {
    const track = byIds([Number(m[1])])[0];
    if (!track) return { handled: true, status: 404 };
    const slug = track.performer.toLowerCase().replace(/\s+/g, "-");
    return {
      handled: true,
      data: {
        track,
        artist_slug: slug,
        listeners: 37,
        playlists_count: 5,
        saves: LIBRARY.has(track.id) ? 12 : 11,
        by_artist: [],
        similar: TRACKS.filter((t) => t.id !== track.id).slice(0, 4),
        playlists: PUBLIC,
      },
    };
  }
  m = /^\/api\/music\/artists\/([^/]+)$/.exec(path);
  if (m) {
    const slug = decodeURIComponent(m[1]);
    const tracks = TRACKS.filter((t) => t.performer.toLowerCase().replace(/\s+/g, "-") === slug);
    return tracks.length ? { handled: true, data: { name: tracks[0].performer, slug, tracks } } : { handled: true, status: 404 };
  }
  m = /^\/api\/music\/tracks\/(\d+)$/.exec(path);
  if (m) return { handled: true, data: byIds([Number(m[1])])[0] };
  if (path === "/api/music/send") return { handled: true, data: { status: "sent", count: (body.track_ids as unknown as number[]).length } };
  if (path === "/api/music/collections") return { handled: true, data: COLLECTIONS };
  m = /^\/api\/music\/collections\/([a-z_]+)$/.exec(path);
  if (m) {
    const found = COLLECTIONS.find((c) => c.key === m![1]);
    return found ? { handled: true, data: { ...found, tracks: byIds([1, 2, 3, 4, 5, 6, 7, 8].slice(0, found.track_count)) } } : { handled: true, status: 404 };
  }
  if (path === "/api/music/playlists/public") return { handled: true, data: PUBLIC };
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
    const ids = (body.track_ids as unknown as number[] | undefined) ?? [];
    const playlist: Playlist = { id: PLAYLISTS.length + 1, title: (body.title as string) || "Жаңа плейлист", track_count: ids.length, share_code: "new12345", share_url: "https://t.me/qazaqcinema_bot?startapp=pl_new12345", is_own: true, is_public: false, saves_count: 0 };
    PLAYLISTS.push({ playlist, ids: [...ids] });
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
  m = /^\/api\/music\/playlists\/(\d+)\/order$/.exec(path);
  if (m) {
    const entry = PLAYLISTS.find((e) => e.playlist.id === Number(m![1]));
    if (entry) entry.ids = [...(body.track_ids as unknown as number[])];
    return { handled: true, data: undefined };
  }
  m = /^\/api\/music\/playlists\/(\d+)$/.exec(path);
  if (m) {
    const entry = PLAYLISTS.find((e) => e.playlist.id === Number(m![1]));
    if (!entry) return { handled: true, status: 404 };
    if (method === "PATCH" && body.title !== undefined) entry.playlist.title = body.title as string;
    if (method === "PATCH" && body.is_public !== undefined) entry.playlist.is_public = Boolean(body.is_public);
    if (method === "DELETE") PLAYLISTS.splice(PLAYLISTS.indexOf(entry), 1);
    return { handled: true, data: method === "GET" ? detail(entry) : undefined };
  }
  m = /^\/api\/music\/shared\/([^/]+)$/.exec(path);
  if (m) {
    const pub = PUBLIC.find((p) => p.share_code === m![1]);
    const data = pub ? { ...pub, tracks: byIds([2, 4, 1, 6, 8]).slice(0, pub.track_count) } : { ...detail(PLAYLISTS[0]), is_own: false };
    return { handled: true, data };
  }
  if (/^\/api\/music\/shared\/[^/]+\/save$/.test(path)) return { handled: true, data: PLAYLISTS[0].playlist };
  return { handled: false };
}
