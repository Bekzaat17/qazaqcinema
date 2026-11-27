// Клиент музыкальных ручек (`/api/music`). Общий транспорт и авторизация — из lib/api.
//
// Как у фильмов, файлов сервер не отдаёт: «тыңдау» — это отправка треков в чат с ботом,
// где их по порядку играет плеер Telegram.

import { request } from "../lib/api";

export interface Track {
  id: number;
  title: string;
  performer: string;
  duration_sec: number;
  play_count: number;
  saves_count: number;
}

export interface MusicRequest {
  query: string;
  votes: number;
}

export interface MusicHome {
  recent: Track[];
  popular: Track[];
  requests: MusicRequest[];
}

export interface Playlist {
  id: number;
  title: string;
  track_count: number;
  share_code: string;
  share_url: string;
  is_own: boolean;
  is_public: boolean;
  saves_count: number;
}

export interface PlaylistDetail extends Playlist {
  tracks: Track[];
}

export interface Collection {
  key: string;
  title: string;
  subtitle: string;
  track_count: number;
  performers: string[];
}

export interface CollectionDetail extends Collection {
  tracks: Track[];
}

export interface TrackDetail {
  track: Track;
  artist_slug: string;
  listeners: number;
  playlists_count: number;
  saves: number;
  by_artist: Track[];
  similar: Track[];
  playlists: Playlist[];
}

export interface Artist {
  name: string;
  slug: string;
  tracks: Track[];
}

export type PlaylistAddStatus = "added" | "duplicate" | "full";

// Сколько треков уходит в чат одним нажатием (зеркало `SEND_MAX` бэкенда).
export const SEND_MAX = 50;

const BASE = "/api/music";
const body = (method: string, data: unknown): RequestInit => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(data),
});

export const musicApi = {
  home: () => request<MusicHome>(`${BASE}/home`),
  tracks: (params: { q?: string; sort?: "new" | "popular"; offset?: number; limit?: number }) => {
    const query = new URLSearchParams();
    if (params.q) query.set("q", params.q);
    if (params.sort) query.set("sort", params.sort);
    query.set("offset", String(params.offset ?? 0));
    query.set("limit", String(params.limit ?? 30));
    return request<Track[]>(`${BASE}/tracks?${query}`);
  },
  track: (id: number) => request<Track>(`${BASE}/tracks/${id}`),
  trackDetails: (id: number) => request<TrackDetail>(`${BASE}/tracks/${id}/details`),
  artist: (slug: string) => request<Artist>(`${BASE}/artists/${encodeURIComponent(slug)}`),
  /** Треки в чат В ЭТОМ ПОРЯДКЕ — так их и сыграет Telegram. */
  send: (trackIds: number[]) =>
    request<{ status: "sent"; count: number }>(`${BASE}/send`, body("POST", { track_ids: trackIds.slice(0, SEND_MAX) })),
  requestTrack: (query: string) => request<{ votes: number }>(`${BASE}/requests`, body("POST", { query })),

  collections: () => request<Collection[]>(`${BASE}/collections`),
  collection: (key: string) => request<CollectionDetail>(`${BASE}/collections/${encodeURIComponent(key)}`),

  me: () => request<{ uploaded: number }>(`${BASE}/me`),
  library: () => request<Track[]>(`${BASE}/library?limit=200`),
  libraryIds: () => request<{ ids: number[] }>(`${BASE}/library/ids`),
  save: (id: number) => request<void>(`${BASE}/library/${id}`, { method: "PUT" }),
  unsave: (id: number) => request<void>(`${BASE}/library/${id}`, { method: "DELETE" }),

  playlists: () => request<Playlist[]>(`${BASE}/playlists`),
  publicPlaylists: () => request<Playlist[]>(`${BASE}/playlists/public`),
  createPlaylist: (title: string, trackIds: number[] = []) =>
    request<Playlist>(`${BASE}/playlists`, body("POST", { title, track_ids: trackIds })),
  playlist: (id: number) => request<PlaylistDetail>(`${BASE}/playlists/${id}`),
  updatePlaylist: (id: number, patch: { title?: string; is_public?: boolean }) =>
    request<void>(`${BASE}/playlists/${id}`, body("PATCH", patch)),
  reorderPlaylist: (id: number, trackIds: number[]) =>
    request<void>(`${BASE}/playlists/${id}/order`, body("PUT", { track_ids: trackIds })),
  deletePlaylist: (id: number) => request<void>(`${BASE}/playlists/${id}`, { method: "DELETE" }),
  addToPlaylist: (id: number, trackId: number) =>
    request<{ status: PlaylistAddStatus }>(`${BASE}/playlists/${id}/tracks/${trackId}`, { method: "PUT" }),
  removeFromPlaylist: (id: number, trackId: number) =>
    request<void>(`${BASE}/playlists/${id}/tracks/${trackId}`, { method: "DELETE" }),

  shared: (code: string) => request<PlaylistDetail>(`${BASE}/shared/${encodeURIComponent(code)}`),
  saveShared: (code: string) =>
    request<Playlist>(`${BASE}/shared/${encodeURIComponent(code)}/save`, { method: "POST" }),
};
