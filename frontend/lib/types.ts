// Mirrors the backend API contract (ULTRAPLAN §5).

export interface Notebook {
  id: string;
  title: string;
  snippet: string;
  cover_hue_a: number;
  cover_hue_b: number;
  cover_glyph: string;
  source_count: number;
  created_at: string;
  updated_at: string;
}

export interface Source {
  id: string;
  notebook_id: string;
  kind: string;
  title: string;
  authors: string | null;
  venue: string | null;
  year: number | null;
  pages: number | null;
  status: string;
  checked: boolean;
  char_count: number;
  created_at: string;
}

export interface Citation {
  display_index: number;
  source_id: string;
  chunk_id: string | null;
  source_title: string;
  source_authors: string | null;
  source_venue: string | null;
  source_kind: string;
  page: number | null;
  section: string | null;
  char_offset_start: number;
  char_offset_end: number;
  snippet: string;
}

export interface Message {
  id: string;
  role: "user" | "assistant";
  text: string;
  created_at: string;
  citations: Citation[];
}

export interface ChatResponse {
  message_id: string;
  answer_markdown: string;
  grounded: boolean;
  citations: Citation[];
}

export interface Passage {
  source_id: string;
  title: string;
  kind: string;
  authors: string | null;
  venue: string | null;
  page: number | null;
  section: string | null;
  pre: string;
  highlight: string;
  post: string;
}

export interface Health {
  status: string;
  provider: string;
  llm_model: string;
  embed_model: string;
  provider_ready: boolean;
}
