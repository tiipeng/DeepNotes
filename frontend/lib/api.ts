import type {
  ChatResponse,
  Health,
  Message,
  Notebook,
  Passage,
  Source,
} from "./types";

export const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
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
export const getNotebook = (id: string) => req<Notebook>(`/notebooks/${id}`);
export const createNotebook = (title: string) =>
  req<Notebook>("/notebooks", { method: "POST", body: JSON.stringify({ title }) });
export const deleteNotebook = (id: string) =>
  req<void>(`/notebooks/${id}`, { method: "DELETE" });

export const listSources = (notebookId: string) =>
  req<Source[]>(`/notebooks/${notebookId}/sources`);
export const setSourceChecked = (sourceId: string, checked: boolean) =>
  req<Source>(`/sources/${sourceId}`, {
    method: "PATCH",
    body: JSON.stringify({ checked }),
  });

export async function uploadSource(notebookId: string, file: File): Promise<Source> {
  const fd = new FormData();
  fd.append("file", file);
  const res = await fetch(`${API_BASE}/notebooks/${notebookId}/sources`, {
    method: "POST",
    body: fd, // let the browser set multipart boundary
  });
  if (!res.ok) throw new Error(`Upload failed: ${res.status} ${await res.text()}`);
  return res.json();
}

export const getMessages = (notebookId: string) =>
  req<Message[]>(`/notebooks/${notebookId}/messages`);
export const sendChat = (notebookId: string, question: string) =>
  req<ChatResponse>(`/notebooks/${notebookId}/chat`, {
    method: "POST",
    body: JSON.stringify({ question }),
  });

export const getPassage = (sourceId: string, start: number, end: number) =>
  req<Passage>(`/sources/${sourceId}/passage?start=${start}&end=${end}`);
