// Клиент музыкальных ручек (`/api/music`). Общий транспорт и авторизация — из lib/api.

import { request } from "../lib/api";

export interface Track {
  id: number;
  title: string;
  performer: string;
  duration_sec: number;
  cover_url: string | null;
  // null — файл тяжелее предела Bot API: такой трек слушают только в чате с ботом.
  stream_url: string | null;
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
  covers: string[];
  share_url: string;
  is_own: boolean;
}

export interface PlaylistDetail extends Playlist {
  tracks: Track[];
}

export type PlaylistAddStatus = "added" | "duplicate" | "full";

const BASE = "/api/music";
const json = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
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
  sendTrack: (id: number) => request<{ status: "sent"; count: number }>(`${BASE}/tracks/${id}/send`, { method: "POST" }),
  played: (id: number) => request<void>(`${BASE}/tracks/${id}/played`, { method: "POST" }),
  requestTrack: (query: string) => request<{ votes: number }>(`${BASE}/requests`, json({ query })),

  library: () => request<Track[]>(`${BASE}/library?limit=200`),
  libraryIds: () => request<{ ids: number[] }>(`${BASE}/library/ids`),
  save: (id: number) => request<void>(`${BASE}/library/${id}`, { method: "PUT" }),
  unsave: (id: number) => request<void>(`${BASE}/library/${id}`, { method: "DELETE" }),
  sendLibrary: () => request<{ status: "sent"; count: number }>(`${BASE}/library/send`, { method: "POST" }),

  playlists: () => request<Playlist[]>(`${BASE}/playlists`),
  createPlaylist: (title: string) => request<Playlist>(`${BASE}/playlists`, json({ title })),
  playlist: (id: number) => request<PlaylistDetail>(`${BASE}/playlists/${id}`),
  renamePlaylist: (id: number, title: string) =>
    request<void>(`${BASE}/playlists/${id}`, { ...json({ title }), method: "PATCH" }),
  deletePlaylist: (id: number) => request<void>(`${BASE}/playlists/${id}`, { method: "DELETE" }),
  addToPlaylist: (id: number, trackId: number) =>
    request<{ status: PlaylistAddStatus }>(`${BASE}/playlists/${id}/tracks/${trackId}`, { method: "PUT" }),
  removeFromPlaylist: (id: number, trackId: number) =>
    request<void>(`${BASE}/playlists/${id}/tracks/${trackId}`, { method: "DELETE" }),
  sendPlaylist: (id: number) =>
    request<{ status: "sent"; count: number }>(`${BASE}/playlists/${id}/send`, { method: "POST" }),

  shared: (code: string) => request<PlaylistDetail>(`${BASE}/shared/${encodeURIComponent(code)}`),
  saveShared: (code: string) =>
    request<Playlist>(`${BASE}/shared/${encodeURIComponent(code)}/save`, { method: "POST" }),
  sendShared: (code: string) =>
    request<{ status: "sent"; count: number }>(`${BASE}/shared/${encodeURIComponent(code)}/send`, { method: "POST" }),
};
