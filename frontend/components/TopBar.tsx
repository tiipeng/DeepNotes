"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { getHealth, getSettings, searchAll, updateSettings } from "@/lib/api";
import type { ChatSettings, Health, SearchHit } from "@/lib/types";

const PROVIDER_LABEL: Record<string, string> = {
  gemini: "Google Gemini",
  openrouter: "OpenRouter (200+ models)",
  openai_compatible: "OpenAI-compatible / your own endpoint",
  ollama: "Ollama (local)",
};
const MODEL_PLACEHOLDER: Record<string, string> = {
  gemini: "gemini-2.5-flash (leave blank for default)",
  openrouter: "e.g. anthropic/claude-3.5-sonnet",
  openai_compatible: "e.g. gpt-4o-mini",
  ollama: "e.g. llama3.1 (leave blank for default)",
};

export function TopBar() {
  const [health, setHealth] = useState<Health | null>(null);
  const [err, setErr] = useState(false);
  const [open, setOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);

  const loadHealth = () => getHealth().then(setHealth).catch(() => setErr(true));
  useEffect(() => {
    loadHealth();
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen(true);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <header className="dn-topbar">
      <Link href="/" className="dn-brand" style={{ textDecoration: "none" }} aria-label="DeepNotes home">
        <span className="dn-brand-mark" aria-hidden>
          <span className="dn-brand-mark-i" />
          <span className="dn-brand-mark-i" />
        </span>
        <span className="dn-brand-word">DeepNotes</span>
      </Link>
      <div className="dn-top-mid">
        <button className="dn-search" onClick={() => setPaletteOpen(true)} aria-label="Search">
          <span className="dn-search-placeholder">Search across all notebooks…</span>
          <span className="dn-kbd">⌘K</span>
        </button>
      </div>
      <div className="dn-top-right">
        <span className="dn-health" title="Active chat model">
          <span className={`dn-health-dot ${err ? "is-down" : health ? "is-ok" : ""}`} />
          {err ? "api offline" : health ? `${health.provider} · ${health.llm_model}` : "connecting…"}
        </span>
        <button className="dn-top-link" onClick={() => setOpen(true)}>Settings</button>
      </div>
      {open && (
        <SettingsModal
          onClose={() => setOpen(false)}
          onSaved={() => {
            loadHealth();
            setOpen(false);
          }}
        />
      )}
      {paletteOpen && <SearchPalette onClose={() => setPaletteOpen(false)} />}
    </header>
  );
}

function SearchPalette({ onClose }: { onClose: () => void }) {
  const router = useRouter();
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<SearchHit[]>([]);
  const [loading, setLoading] = useState(false);
  const timer = useRef<number | null>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  useEffect(() => {
    if (timer.current) window.clearTimeout(timer.current);
    const term = q.trim();
    if (!term) {
      setHits([]);
      return;
    }
    setLoading(true);
    timer.current = window.setTimeout(() => {
      searchAll(term)
        .then(setHits)
        .catch(() => setHits([]))
        .finally(() => setLoading(false));
    }, 180);
    return () => {
      if (timer.current) window.clearTimeout(timer.current);
    };
  }, [q]);

  const go = (hit: SearchHit) => {
    router.push(`/notebook/${hit.notebook_id}`);
    onClose();
  };

  return (
    <>
      <div className="dn-modal-scrim" onClick={onClose} aria-hidden />
      <div className="dn-palette" role="dialog" aria-label="Search">
        <input
          className="dn-palette-input"
          placeholder="Search notebooks and sources…"
          value={q}
          autoFocus
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && hits[0]) go(hits[0]);
          }}
        />
        <div className="dn-palette-results">
          {q.trim() && !loading && hits.length === 0 && (
            <div className="dn-palette-empty">No matches.</div>
          )}
          {hits.map((h, i) => (
            <button key={`${h.notebook_id}-${i}`} className="dn-palette-item" onClick={() => go(h)}>
              <span className="dn-palette-kind">{h.kind === "notebook" ? "Notebook" : h.kind.toUpperCase()}</span>
              <span className="dn-palette-label">{h.label}</span>
              {h.kind !== "notebook" && <span className="dn-palette-in">in {h.notebook_title}</span>}
            </button>
          ))}
        </div>
      </div>
    </>
  );
}

function SettingsModal({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const [s, setS] = useState<ChatSettings | null>(null);
  const [provider, setProvider] = useState("gemini");
  const [model, setModel] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getSettings()
      .then((data) => {
        setS(data);
        setProvider(data.chat_provider);
        setModel(data.chat_model);
        setBaseUrl(
          data.chat_provider === "ollama"
            ? data.ollama_base_url
            : data.chat_provider === "openai_compatible"
              ? data.openai_compatible_base_url
              : "",
        );
      })
      .catch(() => setError("Couldn't load settings — is the backend running?"));
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const keySaved =
    (provider === "openrouter" && s?.has_openrouter_key) ||
    (provider === "openai_compatible" && s?.has_openai_compatible_key) ||
    (provider === "gemini" && s?.has_gemini_key);

  const save = async () => {
    setSaving(true);
    setError(null);
    const patch: Record<string, string> = { chat_provider: provider, chat_model: model.trim() };
    if (provider === "openrouter" && apiKey.trim()) patch.openrouter_api_key = apiKey.trim();
    if (provider === "openai_compatible") {
      patch.openai_compatible_base_url = baseUrl.trim();
      if (apiKey.trim()) patch.openai_compatible_api_key = apiKey.trim();
    }
    if (provider === "ollama") patch.ollama_base_url = baseUrl.trim();
    try {
      await updateSettings(patch);
      onSaved();
    } catch {
      setError("Couldn't save settings.");
      setSaving(false);
    }
  };

  return (
    <>
      <div className="dn-modal-scrim" onClick={onClose} aria-hidden />
      <div className="dn-modal" role="dialog" aria-label="Settings">
        <div className="dn-modal-head">
          <h2 className="dn-modal-title">Chat model</h2>
          <button className="dn-icon-btn" onClick={onClose} title="Close">✕</button>
        </div>
        <p className="dn-modal-sub">
          Choose the model that generates answers — bring your own key. Embeddings stay pinned to{" "}
          <strong>{s?.embedding_provider ?? "gemini"}</strong>, so changing this never affects your
          existing sources or citations.
        </p>

        <label className="dn-field">
          <span className="dn-field-label">Provider</span>
          <select
            className="dn-input"
            value={provider}
            onChange={(e) => {
              setProvider(e.target.value);
              setApiKey("");
              setBaseUrl(e.target.value === "ollama" && s ? s.ollama_base_url : "");
            }}
          >
            {(s?.providers ?? ["gemini", "openrouter", "openai_compatible", "ollama"]).map((p) => (
              <option key={p} value={p}>{PROVIDER_LABEL[p] ?? p}</option>
            ))}
          </select>
        </label>

        <label className="dn-field">
          <span className="dn-field-label">Model</span>
          <input
            className="dn-input"
            placeholder={MODEL_PLACEHOLDER[provider] ?? "model name"}
            value={model}
            onChange={(e) => setModel(e.target.value)}
          />
        </label>

        {provider === "openai_compatible" && (
          <label className="dn-field">
            <span className="dn-field-label">Base URL</span>
            <input
              className="dn-input"
              placeholder="https://api.openai.com/v1"
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
            />
          </label>
        )}
        {provider === "ollama" && (
          <label className="dn-field">
            <span className="dn-field-label">Ollama URL</span>
            <input
              className="dn-input"
              placeholder="http://localhost:11434"
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
            />
          </label>
        )}

        {(provider === "openrouter" || provider === "openai_compatible") && (
          <label className="dn-field">
            <span className="dn-field-label">
              API key {keySaved && <span className="dn-field-hint">✓ saved — leave blank to keep</span>}
            </span>
            <input
              className="dn-input"
              type="password"
              placeholder={keySaved ? "•••••••• (stored)" : "paste your key"}
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              autoComplete="off"
            />
          </label>
        )}

        <p className="dn-modal-note">
          Keys are stored on the server (single-user) and never sent back to the browser.
        </p>
        {error && <p className="dn-modal-error">{error}</p>}

        <div className="dn-modal-actions">
          <button className="dn-btn dn-btn-ghost" onClick={onClose}>Cancel</button>
          <button className="dn-btn dn-btn-primary" onClick={save} disabled={saving || !s}>
            {saving ? "Saving…" : "Save"}
          </button>
        </div>
      </div>
    </>
  );
}
