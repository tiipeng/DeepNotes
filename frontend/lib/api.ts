import type { Health, Notebook } from "./types";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    cache: "no-store",
    ...init,
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText} on ${path}`);
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const getHealth = () => req<Health>("/health");
export const listNotebooks = () => req<Notebook[]>("/notebooks");
export const createNotebook = (title: string) =>
  req<Notebook>("/notebooks", { method: "POST", body: JSON.stringify({ title }) });
export const deleteNotebook = (id: string) =>
  req<void>(`/notebooks/${id}`, { method: "DELETE" });
