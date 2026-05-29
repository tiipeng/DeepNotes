import type {
  ChatResponse,
  ChatSettings,
  Citation,
  Health,
  Message,
  Note,
  Notebook,
  NotebookOverview,
  Passage,
  Source,
  TableResult,
  Thread,
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
export const getSettings = () => req<ChatSettings>("/settings");
export const updateSettings = (patch: Record<string, string>) =>
  req<ChatSettings>("/settings", { method: "PUT", body: JSON.stringify(patch) });
export const listNotebooks = () => req<Notebook[]>("/notebooks");
export const getNotebook = (id: string) => req<Notebook>(`/notebooks/${id}`);
export const getNotebookSummary = (id: string) =>
  req<NotebookOverview>(`/notebooks/${id}/summary`);
export const createNotebook = (title: string) =>
  req<Notebook>("/notebooks", { method: "POST", body: JSON.stringify({ title }) });
export const deleteNotebook = (id: string) =>
  req<void>(`/notebooks/${id}`, { method: "DELETE" });
export const updateNotebook = (id: string, patch: { title?: string; snippet?: string }) =>
  req<Notebook>(`/notebooks/${id}`, { method: "PATCH", body: JSON.stringify(patch) });

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
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/notebooks/${notebookId}/sources`, {
      method: "POST",
      body: fd, // let the browser set multipart boundary
    });
  } catch {
    throw new Error("Can't reach the backend. Check your connection and try again.");
  }
  if (!res.ok) {
    let detail = `Upload failed (${res.status}).`;
    try {
      const body = await res.json();
      if (body?.detail) detail = body.detail;
    } catch {
      /* non-JSON error body */
    }
    throw new Error(detail);
  }
  return res.json();
}

export const listThreads = (notebookId: string) =>
  req<Thread[]>(`/notebooks/${notebookId}/threads`);
export async function addUrlSource(notebookId: string, url: string): Promise<Source> {
  const fd = new FormData();
  fd.append("url", url);
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/notebooks/${notebookId}/sources`, { method: "POST", body: fd });
  } catch {
    throw new Error("Can't reach the backend. Check your connection and try again.");
  }
  if (!res.ok) {
    let detail = `Couldn't add link (${res.status}).`;
    try {
      const body = await res.json();
      if (body?.detail) detail = body.detail;
    } catch {
      /* non-JSON */
    }
    throw new Error(detail);
  }
  return res.json();
}

export const getMessages = (notebookId: string, threadId?: string) =>
  req<Message[]>(
    `/notebooks/${notebookId}/messages${threadId ? `?thread_id=${encodeURIComponent(threadId)}` : ""}`,
  );
export const sendChat = (notebookId: string, question: string, threadId = "default") =>
  req<ChatResponse>(`/notebooks/${notebookId}/chat`, {
    method: "POST",
    body: JSON.stringify({ question, thread_id: threadId }),
  });

export interface StreamDone {
  message_id: string;
  answer_markdown: string;
  grounded: boolean;
  citations: Citation[];
  table_result: TableResult | null;
  intent?: string;
  follow_ups?: string[];
}

/** POST a question and stream the answer over SSE. Calls onToken as prose
 * arrives, onDone once the answer + resolved citations are ready. */
export async function streamChat(
  notebookId: string,
  question: string,
  threadId: string,
  handlers: {
    onToken: (delta: string) => void;
    onDone: (d: StreamDone) => void;
    onError: (detail: string) => void;
  },
  signal?: AbortSignal,
): Promise<void> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/notebooks/${notebookId}/chat/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, thread_id: threadId }),
      signal,
    });
  } catch {
    handlers.onError("Can't reach the backend. Check your connection and try again.");
    return;
  }
  if (!res.ok || !res.body) {
    handlers.onError(`The server returned an error (${res.status}). Please try again.`);
    return;
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      const events = buf.split("\n\n");
      buf = events.pop() ?? "";
      for (const ev of events) {
        const line = ev.split("\n").find((l) => l.startsWith("data: "));
        if (!line) continue;
        const obj = JSON.parse(line.slice(6));
        if (obj.type === "token") handlers.onToken(obj.delta as string);
        else if (obj.type === "done") handlers.onDone(obj as StreamDone);
        else if (obj.type === "error") handlers.onError(obj.detail as string);
      }
    }
  } catch {
    handlers.onError("The answer stream was interrupted. Please try again.");
  }
}

export const getPassage = (sourceId: string, start: number, end: number) =>
  req<Passage>(`/sources/${sourceId}/passage?start=${start}&end=${end}`);

export const listNotes = (notebookId: string) =>
  req<Note[]>(`/notebooks/${notebookId}/notes`);
export const createNote = (
  notebookId: string,
  data: { title: string; body: string; tag?: string; source_id?: string },
) =>
  req<Note>(`/notebooks/${notebookId}/notes`, {
    method: "POST",
    body: JSON.stringify(data),
  });
export const deleteNote = (noteId: string) =>
  req<void>(`/notes/${noteId}`, { method: "DELETE" });
