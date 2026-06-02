"use client";

import { useEffect, useState } from "react";
import { getSourceContent, getSourceGuide } from "@/lib/api";
import type { Source, SourceGuide } from "@/lib/types";
import { Markdown } from "./Markdown";
import { IconClose, IconFileText, IconLink, IconSparkle } from "./icons";

export function SourceDrawer({
  source,
  onClose,
  onAsk,
}: {
  source: Source | null;
  onClose: () => void;
  onAsk: (q: string) => void;
}) {
  const [tab, setTab] = useState<"guide" | "content">("guide");
  const [guide, setGuide] = useState<SourceGuide | null>(null);
  const [guideLoading, setGuideLoading] = useState(false);
  const [content, setContent] = useState<string>("");
  const [contentLoading, setContentLoading] = useState(false);

  const open = !!source;

  useEffect(() => {
    if (!source) return;
    setGuide(null);
    setContent("");
    setTab("guide");

    if (source.status !== "ready") return;

    setGuideLoading(true);
    getSourceGuide(source.id)
      .then(setGuide)
      .catch(() => {})
      .finally(() => setGuideLoading(false));

    setContentLoading(true);
    getSourceContent(source.id)
      .then((c) => setContent(c.parsed_markdown))
      .catch(() => {})
      .finally(() => setContentLoading(false));
  }, [source?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  return (
    <>
      <div className={`dn-sd-scrim ${open ? "is-open" : ""}`} onClick={onClose} aria-hidden={!open} />
      <aside className={`dn-sd ${open ? "is-open" : ""}`} aria-hidden={!open}>
        {source && (
          <>
            <header className="dn-sd-head">
              <div className="dn-sd-head-l">
                <div className="dn-sd-kind">
                  {source.kind === "url" ? <IconLink size={12} /> : <IconFileText size={12} />}
                  <span>{source.kind.toUpperCase()}</span>
                  {source.pages && (
                    <><span className="dn-dot" /><span className="dn-mono">{source.pages}p</span></>
                  )}
                </div>
                <h3 className="dn-sd-title">{source.title}</h3>
              </div>
              <button className="dn-icon-btn dn-sd-close" title="Close (Esc)" onClick={onClose}>
                <IconClose size={14} />
              </button>
            </header>

            <div className="dn-sd-tabs">
              <button
                className={`dn-sd-tab ${tab === "guide" ? "is-active" : ""}`}
                onClick={() => setTab("guide")}
              >
                <IconSparkle size={12} /> Source Guide
              </button>
              <button
                className={`dn-sd-tab ${tab === "content" ? "is-active" : ""}`}
                onClick={() => setTab("content")}
              >
                Content
              </button>
            </div>

            <div className="dn-sd-body">
              {tab === "guide" ? (
                <div className="dn-sd-guide">
                  {source.status === "parsing" ? (
                    <p className="dn-sd-note">This source is still processing — check back shortly.</p>
                  ) : source.status === "error" ? (
                    <p className="dn-sd-note is-error">{source.error_msg ?? "This source couldn't be processed."}</p>
                  ) : guideLoading ? (
                    <div className="dn-sd-skel">
                      <div className="dn-skel dn-skel-line" style={{ height: 18 }} />
                      <div className="dn-skel dn-skel-line" style={{ height: 18 }} />
                      <div className="dn-skel dn-skel-line" style={{ height: 18, width: "65%" }} />
                    </div>
                  ) : guide?.summary ? (
                    <>
                      <p className="dn-sd-summary">{guide.summary}</p>
                      {guide.questions.length > 0 && (
                        <div className="dn-sd-questions">
                          <div className="dn-sd-qlabel">Questions to explore</div>
                          <div className="dn-chip-q-row">
                            {guide.questions.map((q) => (
                              <button
                                key={q}
                                className="dn-chip-q"
                                onClick={() => { onAsk(q); onClose(); }}
                              >
                                {q}
                              </button>
                            ))}
                          </div>
                        </div>
                      )}
                    </>
                  ) : (
                    <p className="dn-sd-note">Couldn&apos;t generate a guide for this source.</p>
                  )}
                </div>
              ) : (
                <div className="dn-sd-content">
                  {contentLoading ? (
                    <div className="dn-sd-skel">
                      {Array.from({ length: 6 }).map((_, i) => (
                        <div key={i} className="dn-skel dn-skel-line" style={{ height: 16, width: i % 3 === 2 ? "70%" : "100%" }} />
                      ))}
                    </div>
                  ) : content ? (
                    <Markdown text={content} />
                  ) : (
                    <p className="dn-sd-note">No content available.</p>
                  )}
                </div>
              )}
            </div>
          </>
        )}
      </aside>
    </>
  );
}
