"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { createNotebook, listNotebooks } from "@/lib/api";
import type { Notebook } from "@/lib/types";
import { TopBar } from "@/components/TopBar";
import { NameModal } from "@/components/NameModal";

export default function Dashboard() {
  const router = useRouter();
  const [notebooks, setNotebooks] = useState<Notebook[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [loadError, setLoadError] = useState(false);
  const [showCreate, setShowCreate] = useState(false);

  const refresh = useCallback(async () => {
    try {
      setNotebooks(await listNotebooks());
      setLoadError(false);
    } catch {
      setLoadError(true);
    } finally {
      setLoaded(true);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const onCreate = async (title: string) => {
    const nb = await createNotebook(title.trim() || "Untitled notebook");
    router.push(`/notebook/${nb.id}`); // open the new notebook
  };

  return (
    <div className="dn-app">
      <TopBar />

      <main className="dn-main">
        <div className="dn-screen">
          <div className="dn-dash-head">
            <div>
              <h1 className="dn-display">Your notebooks</h1>
              <p className="dn-subtle">
                {loadError
                  ? "Can't reach the backend"
                  : !loaded
                    ? "Loading…"
                    : notebooks.length === 0
                      ? "No notebooks yet"
                      : `${notebooks.length} in progress`}
              </p>
            </div>
            <button className="dn-btn dn-btn-primary" onClick={() => setShowCreate(true)} disabled={loadError}>
              + New notebook
            </button>
          </div>

          {loadError && (
            <div className="dn-banner" role="alert">
              <span className="dn-banner-dot" />
              <span>
                Can&apos;t reach the DeepNotes backend. Make sure it&apos;s running, then{" "}
                <button className="dn-banner-link" onClick={refresh}>retry</button>.
              </span>
            </div>
          )}

          <div className="dn-grid">
            <button className="dn-card dn-card-new" onClick={() => setShowCreate(true)}>
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

      {showCreate && (
        <NameModal
          title="New notebook"
          label="Notebook title"
          initial="Untitled notebook"
          cta="Create"
          onSubmit={onCreate}
          onClose={() => setShowCreate(false)}
        />
      )}
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
