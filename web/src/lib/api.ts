// Клиент бэкенда. initData уходит в заголовке Authorization (валидируется на бэке).

import { getInitData } from "./telegram";

const BASE_URL = import.meta.env.VITE_API_URL ?? "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: {
      Authorization: getInitData(),
      ...(init?.headers ?? {}),
    },
  });
  if (!response.ok) {
    throw new Error(`API ${response.status}: ${path}`);
  }
  return (await response.json()) as T;
}

export interface Tariff {
  slug: string;
  title_ru: string;
  title_kk: string;
  price_kzt: number;
  days: number;
  recurring: boolean;
}

export const api = {
  tariffs: () => request<Tariff[]>("/api/payments/tariffs"),
  // PLAN (фронтенд): auth(), movies(), searchMovies(), initiatePayment(), submitProof()
};
