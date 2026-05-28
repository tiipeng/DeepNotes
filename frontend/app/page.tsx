"use client";

import { useCallback, useEffect, useState } from "react";
import { createNotebook, getHealth, listNotebooks } from "@/lib/api";
import type { Health, Notebook } from "@/lib/types";

export default function Dashboard() {
  const [notebooks, setNotebooks] = useState<Notebook[]>([]);
  const [health, setHealth] = useState<Health | null>(null);
  const [healthError, setHealthError] = useState(false);
  const [creating, setCreating] = useState(false);

  const refresh = useCallback(async () => {
    try {
      setNotebooks(await listNotebooks());
    } catch {
      /* backend may be starting */
    }
  }, []);

  useEffect(() => {
    getHealth().then(setHealth).catch(() => setHealthError(true));
    refresh();
  }, [refresh]);

  const onCreate = useCallback(async () => {
    const title = window.prompt("Notebook title", "Untitled notebook");
    if (title === null) return;
    setCreating(true);
    try {
      await createNotebook(title.trim() || "Untitled notebook");
      await refresh();
    } finally {
      setCreating(false);
    }
  }, [refresh]);

  return (
    <div className="dn-app">
      <header className="dn-topbar">
        <div className="dn-brand">
          <span className="dn-brand-mark" aria-hidden>
            <span className="dn-brand-mark-i" />
            <span className="dn-brand-mark-i" />
          </span>
          <span className="dn-brand-word">DeepNotes</span>
        </div>
        <div className="dn-top-mid">
          <div className="dn-search">
            <input placeholder="Search across all notebooks…" />
            <span className="dn-kbd">⌘K</span>
          </div>
        </div>
        <div className="dn-top-right">
          <span className="dn-health" title="Backend status">
            <span
              className={`dn-health-dot ${
                healthError ? "is-down" : health ? "is-ok" : ""
              }`}
            />
            {healthError
              ? "api offline"
              : health
                ? `${health.provider} · ${health.llm_model}`
                : "connecting…"}
          </span>
          <button className="dn-top-link">Settings</button>
        </div>
      </header>

      <main className="dn-main">
        <div className="dn-screen">
          <div className="dn-dash-head">
            <div>
              <h1 className="dn-display">Your notebooks</h1>
              <p className="dn-subtle">
                {notebooks.length === 0
                  ? "No notebooks yet"
                  : `${notebooks.length} in progress`}
              </p>
            </div>
            <button className="dn-btn dn-btn-primary" onClick={onCreate} disabled={creating}>
              {creating ? "Creating…" : "+ New notebook"}
            </button>
          </div>

          <div className="dn-grid">
            <button className="dn-card dn-card-new" onClick={onCreate} disabled={creating}>
              <div className="dn-card-new-mark">+</div>
              <div className="dn-card-new-label">New notebook</div>
              <div className="dn-card-new-sub">Start from sources or a blank canvas</div>
            </button>

            {notebooks.map((nb) => (
              <NotebookCard key={nb.id} nb={nb} />
            ))}
          </div>
        </div>
      </main>
    </div>
  );
}

function NotebookCard({ nb }: { nb: Notebook }) {
  const bg = `linear-gradient(135deg, oklch(0.82 0.06 ${nb.cover_hue_a}) 0%, oklch(0.72 0.09 ${nb.cover_hue_b}) 100%)`;
  return (
    <a className="dn-card" href={`/notebook/${nb.id}`}>
      <div className="dn-cover" style={{ background: bg }}>
        <span className="dn-cover-glyph">{nb.cover_glyph}</span>
        <span className="dn-cover-marks" aria-hidden>
          <span />
          <span />
          <span />
        </span>
      </div>
      <div className="dn-card-body">
        <div className="dn-card-title">{nb.title}</div>
        <div className="dn-card-snippet">
          {nb.snippet || "No sources yet — add PDFs or links to start."}
        </div>
        <div className="dn-card-meta">
          <span>{nb.source_count} sources</span>
          <span className="dn-dot" />
          <span>Edited {new Date(nb.updated_at).toLocaleDateString()}</span>
        </div>
      </div>
    </a>
  );
}
