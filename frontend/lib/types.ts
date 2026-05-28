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

export interface Health {
  status: string;
  provider: string;
  llm_model: string;
  embed_model: string;
  provider_ready: boolean;
}
