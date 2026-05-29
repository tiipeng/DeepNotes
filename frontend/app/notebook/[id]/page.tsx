"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  getMessages,
  getNotebook,
  getNotebookSummary,
  getPassage,
  listSources,
  setSourceChecked,
  streamChat,
  uploadSource,
} from "@/lib/api";
import type {
  Citation,
  Message,
  Notebook,
  NotebookOverview,
  Passage,
  Source,
  TableResult,
} from "@/lib/types";
import { TopBar } from "@/components/TopBar";
import {
  IconAttach,
  IconBookmark,
  IconCheck,
  IconChevronRight,
  IconClose,
  IconCopy,
  IconDownload,
  IconFileText,
  IconLink,
  IconMic,
  IconMore,
  IconNote,
  IconPlay,
  IconPlus,
  IconQuote,
  IconRefresh,
  IconSend,
  IconSparkle,
} from "@/components/icons";

export default function NotebookPage({ params }: { params: { id: string } }) {
  const notebookId = params.id;
  const [notebook, setNotebook] = useState<Notebook | null>(null);
  const [sources, setSources] = useState<Source[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [streaming, setStreaming] = useState<string | null>(null);
  const [chatError, setChatError] = useState<string | null>(null);
  const [openCite, setOpenCite] = useState<Citation | null>(null);
  const [passage, setPassage] = useState<Passage | null>(null);
  const [overview, setOverview] = useState<NotebookOverview | null>(null);
  const [overviewLoading, setOverviewLoading] = useState(false);

  const loadSources = useCallback(async () => {
    setSources(await listSources(notebookId));
  }, [notebookId]);

  useEffect(() => {
    getNotebook(notebookId).then(setNotebook).catch(() => {});
    loadSources().catch(() => {});
    getMessages(notebookId, "default").then(setMessages).catch(() => {});
  }, [notebookId, loadSources]);

  const checkedReady = sources.filter((s) => s.checked && s.status === "ready");
  const readyCount = sources.filter((s) => s.status === "ready").length;

  // Overview regenerates only when the set of ready sources changes (backend caches
  // by fingerprint, so unchanged sets are a cheap no-op).
  useEffect(() => {
    if (readyCount === 0) {
      setOverview({ summary: "", suggested_questions: [], ready: false });
      return;
    }
    setOverviewLoading(true);
    getNotebookSummary(notebookId)
      .then(setOverview)
      .catch(() => setOverview(null))
      .finally(() => setOverviewLoading(false));
  }, [notebookId, readyCount]);

  const onToggle = async (s: Source) => {
    setSources((prev) =>
      prev.map((x) => (x.id === s.id ? { ...x, checked: !x.checked } : x)),
    );
    await setSourceChecked(s.id, !s.checked).catch(loadSources);
  };

  const onUpload = async (file: File) => {
    const tmp: Source = {
      id: `tmp-${Date.now()}`, notebook_id: notebookId, kind: "pdf",
      title: file.name, authors: null, venue: null, year: null, pages: null,
      status: "parsing", checked: true, char_count: 0, created_at: new Date().toISOString(),
    };
    setSources((prev) => [...prev, tmp]);
    try {
      await uploadSource(notebookId, file);
    } finally {
      await loadSources();
    }
  };

  const ask = async (question: string) => {
    const q = question.trim();
    if (!q || streaming !== null) return;
    setChatError(null);
    setStreaming("");
    const userMsg: Message = {
      id: `u-${Date.now()}`, role: "user", text: q,
      created_at: new Date().toISOString(), citations: [], table_result: null,
    };
    setMessages((prev) => [...prev, userMsg]);
    await streamChat(notebookId, q, "default", {
      onToken: (d) => setStreaming((prev) => (prev ?? "") + d),
      onDone: (done) => {
        const asst: Message = {
          id: done.message_id, role: "assistant", text: done.answer_markdown,
          created_at: new Date().toISOString(),
          citations: done.citations, table_result: done.table_result,
        };
        setMessages((prev) => [...prev, asst]);
        setStreaming(null);
      },
      onError: (detail) => {
        setChatError(detail);
        setStreaming(null);
      },
    });
  };

  const onCite = async (c: Citation) => {
    setOpenCite(c);
    setPassage(null);
    try {
      setPassage(await getPassage(c.source_id, c.char_offset_start, c.char_offset_end));
    } catch {
      setPassage(null);
    }
  };

  return (
    <div className="dn-app">
      <TopBar />
      <main className="dn-main">
        <div className="dn-screen dn-notebook">
          <div className="dn-subhead">
            <div className="dn-crumbs">
              <span className="dn-crumb-mute">Notebooks</span>
              <IconChevronRight size={12} />
              <span className="dn-crumb">{notebook?.title ?? "…"}</span>
              <span className="dn-pill">{sources.length} sources</span>
            </div>
            <div className="dn-subhead-actions">
              <span className="dn-subhead-meta">
                {notebook ? `Edited ${new Date(notebook.updated_at).toLocaleDateString()}` : ""}
              </span>
              <button className="dn-icon-btn" title="More"><IconMore size={14} /></button>
            </div>
          </div>

          <div className="dn-three-col">
            <SourcesPanel
              sources={sources}
              checkedCount={checkedReady.length}
              onToggle={onToggle}
              onUpload={onUpload}
            />
            <ChatPanel
              messages={messages}
              streaming={streaming}
              chatError={chatError}
              sourceCount={checkedReady.length}
              overview={overview}
              overviewLoading={overviewLoading}
              openCite={openCite}
              onCite={onCite}
              onAsk={ask}
            />
            <StudioPanel />
          </div>
        </div>
      </main>

      <CitationDrawer
        cite={openCite}
        passage={passage}
        onClose={() => {
          setOpenCite(null);
          setPassage(null);
        }}
      />
    </div>
  );
}

/* ---------------- Sources ---------------- */
function SourcesPanel({
  sources, checkedCount, onToggle, onUpload,
}: {
  sources: Source[];
  checkedCount: number;
  onToggle: (s: Source) => void;
  onUpload: (f: File) => void;
}) {
  const fileRef = useRef<HTMLInputElement>(null);
  return (
    <aside className="dn-col">
      <div className="dn-col-head">
        <div className="dn-col-title">
          Sources <span className="dn-col-count">{sources.length}</span>
        </div>
        <button className="dn-icon-btn" title="More"><IconMore size={14} /></button>
      </div>

      <input
        ref={fileRef}
        type="file"
        hidden
        accept=".pdf,.txt,.md,.docx,.pptx,.xlsx,.html"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) onUpload(f);
          e.target.value = "";
        }}
      />
      <button className="dn-add-source" onClick={() => fileRef.current?.click()}>
        <IconPlus size={14} /> <span>Add source</span>
      </button>

      <div className="dn-source-actions">
        <span>Include in chat</span>
        <span>{checkedCount} of {sources.length} in chat</span>
      </div>

      <ul className="dn-source-list">
        {sources.length === 0 && (
          <li className="dn-studio-empty" style={{ padding: "16px 10px" }}>
            No sources yet. Add a PDF, doc, or text file to start.
          </li>
        )}
        {sources.map((s) => (
          <li key={s.id}>
            <button className="dn-source" onClick={() => onToggle(s)}>
              <span className={`dn-cb ${s.checked ? "is-checked" : ""}`}>
                {s.checked && <IconCheck size={11} />}
              </span>
              <span className="dn-source-icon">
                {s.kind === "url" ? <IconLink size={14} /> : <IconFileText size={14} />}
                <span className="dn-source-kind">{s.kind.toUpperCase()}</span>
              </span>
              <span className="dn-source-body">
                <span className="dn-source-title">{s.title}</span>
                <span className="dn-source-meta">
                  {s.status !== "ready" ? (
                    <span className={`dn-source-status is-${s.status}`}>{s.status}</span>
                  ) : (
                    <>
                      {s.pages ? <span className="dn-mono">{s.pages}p</span> : null}
                      {s.pages ? <span className="dn-dot" /> : null}
                      <span>{(s.char_count / 1000).toFixed(1)}k chars</span>
                    </>
                  )}
                </span>
              </span>
            </button>
          </li>
        ))}
      </ul>

      <div className="dn-col-foot">
        <div className="dn-quota-bar">
          <span style={{ width: `${Math.min(100, (sources.length / 10) * 100)}%` }} />
        </div>
        <div className="dn-quota-label">
          <span>{sources.length} / 10 sources</span>
          <span className="dn-mono">indexed</span>
        </div>
      </div>
    </aside>
  );
}

/* ---------------- Chat ---------------- */
function ChatPanel({
  messages, streaming, chatError, sourceCount, overview, overviewLoading, openCite, onCite, onAsk,
}: {
  messages: Message[];
  streaming: string | null;
  chatError: string | null;
  sourceCount: number;
  overview: NotebookOverview | null;
  overviewLoading: boolean;
  openCite: Citation | null;
  onCite: (c: Citation) => void;
  onAsk: (q: string) => void;
}) {
  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const busy = streaming !== null;

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, streaming, chatError]);

  const submit = () => {
    onAsk(input);
    setInput("");
  };

  const empty = messages.length === 0 && !busy && !chatError;

  return (
    <section className="dn-col dn-col-chat">
      <div className="dn-col-head">
        <div className="dn-col-title">
          Chat <span className="dn-col-count">{messages.filter((m) => m.role === "user").length}</span>
        </div>
        <div className="dn-chat-head-actions">
          <button className="dn-btn dn-btn-ghost dn-btn-tight">
            <IconRefresh size={12} /> New thread
          </button>
        </div>
      </div>

      <div className="dn-chat-scroll" ref={scrollRef}>
        {empty ? (
          <div className="dn-chat-empty">
            <div className="dn-empty-mark" aria-hidden>
              <span className="dn-empty-stripe" />
              <span className="dn-empty-stripe" />
              <span className="dn-empty-stripe" />
            </div>
            {overview?.ready ? (
              <>
                <h2 className="dn-empty-title">Ask anything across your sources.</h2>
                {overview.summary && <p className="dn-empty-sub">{overview.summary}</p>}
                {overview.suggested_questions.length > 0 && (
                  <div className="dn-suggest">
                    <div className="dn-suggest-label">Suggested questions</div>
                    <div className="dn-suggest-list">
                      {overview.suggested_questions.map((q) => (
                        <button
                          key={q}
                          className="dn-suggest-item"
                          onClick={() => onAsk(q)}
                          disabled={sourceCount === 0}
                        >
                          <span className="dn-suggest-q">{q}</span>
                          <IconChevronRight size={14} />
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </>
            ) : overviewLoading ? (
              <>
                <h2 className="dn-empty-title">Reading your sources…</h2>
                <p className="dn-empty-sub">
                  Building an overview and a few good questions to get you started.
                </p>
                <div className="dn-suggest-list" aria-hidden>
                  <div className="dn-skel dn-skel-line" />
                  <div className="dn-skel dn-skel-line" />
                  <div className="dn-skel dn-skel-line" style={{ width: "70%" }} />
                </div>
              </>
            ) : (
              <>
                <h2 className="dn-empty-title">Add a source to begin.</h2>
                <p className="dn-empty-sub">
                  Upload a PDF, document, or spreadsheet on the left. Once it&apos;s indexed,
                  you&apos;ll get a grounded overview and can ask anything — with every claim
                  linked to the exact passage it came from.
                </p>
              </>
            )}
          </div>
        ) : (
          <div className="dn-thread">
            {messages.map((m) =>
              m.role === "user" ? (
                <div key={m.id} className="dn-msg-user">
                  <div className="dn-msg-bubble">{m.text}</div>
                </div>
              ) : (
                <AssistantMessage key={m.id} m={m} openCite={openCite} onCite={onCite} />
              ),
            )}
            {busy && <StreamingMessage text={streaming ?? ""} />}
            {chatError && (
              <div className="dn-chat-error" role="alert">
                <IconClose size={13} />
                <span>{chatError}</span>
              </div>
            )}
          </div>
        )}
      </div>

      <div className="dn-composer">
        <div className="dn-composer-inner">
          <button className="dn-composer-attach" title="Attach"><IconAttach size={15} /></button>
          <input
            className="dn-composer-input"
            placeholder={
              sourceCount === 0
                ? "Add a source to start asking…"
                : busy
                  ? "Answering…"
                  : "Ask a question about your sources…"
            }
            value={input}
            disabled={busy || sourceCount === 0}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && submit()}
          />
          <div className="dn-composer-r">
            <span className="dn-composer-scope">{sourceCount} sources</span>
            <button
              className="dn-composer-send"
              title="Send"
              onClick={submit}
              disabled={!input.trim() || busy || sourceCount === 0}
            >
              <IconSend size={14} />
            </button>
          </div>
        </div>
        <div className="dn-composer-foot">
          <span>Answers are grounded in your sources. Verify before citing externally.</span>
        </div>
      </div>
    </section>
  );
}

function StreamingMessage({ text }: { text: string }) {
  return (
    <div className="dn-msg-assistant">
      <div className="dn-msg-byline">
        <span className="dn-assistant-mark" aria-hidden><IconSparkle size={12} /></span>
        <span className="dn-msg-byline-text">
          {text ? "Answering from your sources" : "Searching your sources…"}
        </span>
      </div>
      {text ? (
        <div className="dn-answer">
          {text}
          <span className="dn-stream-cursor" aria-hidden />
        </div>
      ) : (
        <span className="dn-thinking">
          <span className="dn-stream-dots"><i /><i /><i /></span>
        </span>
      )}
    </div>
  );
}

function AssistantMessage({
  m, openCite, onCite,
}: {
  m: Message;
  openCite: Citation | null;
  onCite: (c: Citation) => void;
}) {
  const byId = new Map(m.citations.map((c) => [c.display_index, c]));
  const grounded = m.citations.length > 0;
  const table = m.table_result;

  const byline = table
    ? `Computed from ${table.source_title}`
    : grounded
      ? `Grounded in ${new Set(m.citations.map((c) => c.source_id)).size} source(s)`
      : "No grounded answer";

  return (
    <div className="dn-msg-assistant">
      <div className="dn-msg-byline">
        <span className="dn-assistant-mark" aria-hidden><IconSparkle size={12} /></span>
        <span className="dn-msg-byline-text">{byline}</span>
      </div>

      <div className={`dn-answer ${grounded || table ? "" : "dn-answer-notfound"}`}>
        {renderAnswer(m.text, byId, openCite, onCite)}
      </div>

      {table && <TableCard table={table} />}

      {grounded && (
        <div className="dn-cited-row">
          <div className="dn-cited-label">Sources</div>
          <div className="dn-cited-list">
            {m.citations.map((c) => (
              <button
                key={c.display_index}
                className={`dn-cited-card ${openCite?.display_index === c.display_index ? "is-active" : ""}`}
                onClick={() => onCite(c)}
              >
                <span className="dn-cited-n">{c.display_index}</span>
                <span className="dn-cited-body">
                  <span className="dn-cited-title">{c.source_title}</span>
                  <span className="dn-cited-meta">
                    {c.section ?? c.source_venue ?? c.source_kind.toUpperCase()}
                    {c.page ? ` · p. ${c.page}` : ""}
                  </span>
                </span>
              </button>
            ))}
          </div>
        </div>
      )}

      {(grounded || table) && (
        <div className="dn-msg-tools">
          <button className="dn-tool"><IconCopy size={13} /> Copy</button>
          <button className="dn-tool"><IconQuote size={13} /> Save as note</button>
          <button className="dn-tool"><IconBookmark size={13} /> Pin</button>
          <button className="dn-tool dn-tool-r"><IconRefresh size={13} /> Rerun</button>
        </div>
      )}
    </div>
  );
}

function renderAnswer(
  text: string,
  byId: Map<number, Citation>,
  openCite: Citation | null,
  onCite: (c: Citation) => void,
) {
  const parts = text.split(/(\[\d+\])/g);
  return parts.map((part, i) => {
    const m = part.match(/^\[(\d+)\]$/);
    if (m) {
      const n = Number(m[1]);
      const c = byId.get(n);
      if (c) {
        return (
          <button
            key={i}
            className={`dn-cite ${openCite?.display_index === n ? "is-active" : ""}`}
            onClick={() => onCite(c)}
            title="Open cited passage"
          >
            <span className="dn-cite-bracket">⟦</span>
            <span className="dn-cite-n">{n}</span>
            <span className="dn-cite-bracket">⟧</span>
          </button>
        );
      }
    }
    return <span key={i}>{part}</span>;
  });
}

function TableCard({ table }: { table: TableResult }) {
  const fmt = (v: string | number | boolean | null) =>
    v === null ? "" : typeof v === "number" ? v.toLocaleString("en-US") : String(v);
  return (
    <div className="dn-table-card">
      <div className="dn-table-label">Computed from spreadsheet · {table.source_title}</div>
      <div className="dn-table-scroll">
        <table className="dn-data-table">
          <thead>
            <tr>{table.columns.map((c) => <th key={c}>{c}</th>)}</tr>
          </thead>
          <tbody>
            {table.rows.map((r, i) => (
              <tr key={i}>{r.map((c, j) => <td key={j}>{fmt(c)}</td>)}</tr>
            ))}
          </tbody>
        </table>
      </div>
      {table.truncated && <div className="dn-table-more">…more rows not shown</div>}
      <details className="dn-sql">
        <summary>Query</summary>
        <pre>{table.sql}</pre>
      </details>
    </div>
  );
}

/* ---------------- Studio ---------------- */
function StudioPanel() {
  return (
    <aside className="dn-col">
      <div className="dn-col-head">
        <div className="dn-col-title">Studio</div>
        <button className="dn-icon-btn"><IconMore size={14} /></button>
      </div>
      <div className="dn-studio-section">
        <div className="dn-studio-h"><IconMic size={13} /> <span>Audio overview</span></div>
        <button className="dn-audio-cta">
          <span className="dn-audio-cta-mark"><IconSparkle size={15} /></span>
          <span className="dn-audio-cta-body">
            <span className="dn-audio-cta-title">Generate audio overview</span>
            <span className="dn-audio-cta-sub">A two-host conversation through your sources · ~12 min</span>
          </span>
        </button>
      </div>
      <div className="dn-studio-section">
        <div className="dn-studio-h">
          <IconNote size={13} /> <span>Notes</span>
          <button className="dn-studio-h-add"><IconPlus size={12} /></button>
        </div>
        <div className="dn-studio-empty">
          Saved snippets and answers will appear here.
        </div>
      </div>
    </aside>
  );
}

/* ---------------- Citation drawer ---------------- */
function cleanLine(s: string) {
  return s.replace(/^#{1,6}\s+/gm, "");
}

function CitationDrawer({
  cite, passage, onClose,
}: {
  cite: Citation | null;
  passage: Passage | null;
  onClose: () => void;
}) {
  const open = !!cite;
  const highlightRef = useRef<HTMLElement>(null);

  // Center the highlight as soon as the drawer opens (the highlight text comes from
  // cite.snippet, so it's present immediately), and again once pre/post context
  // loads and shifts its position.
  useEffect(() => {
    if (cite && highlightRef.current) {
      highlightRef.current.scrollIntoView({ block: "center", behavior: "auto" });
    }
  }, [cite, passage]);

  return (
    <>
      <div className={`dn-cd-scrim ${open ? "is-open" : ""}`} onClick={onClose} aria-hidden={!open} />
      <aside className={`dn-cd ${open ? "is-open" : ""}`} aria-hidden={!open}>
        {cite && (
          <>
            <header className="dn-cd-head">
              <div className="dn-cd-head-l">
                <span className="dn-cited-n dn-cd-n">{cite.display_index}</span>
                <div className="dn-cd-titles">
                  <div className="dn-cd-kind">
                    {cite.source_kind === "url" ? <IconLink size={12} /> : <IconFileText size={12} />}
                    <span>{cite.source_kind.toUpperCase()}</span>
                    {(passage?.venue ?? cite.source_venue) && (
                      <><span className="dn-dot" /><span>{passage?.venue ?? cite.source_venue}</span></>
                    )}
                    {cite.page && (
                      <><span className="dn-dot" /><span className="dn-mono">p. {cite.page}</span></>
                    )}
                  </div>
                  <h3 className="dn-cd-title">{passage?.title ?? cite.source_title}</h3>
                  {(passage?.authors ?? cite.source_authors) && (
                    <div className="dn-cd-authors">{passage?.authors ?? cite.source_authors}</div>
                  )}
                </div>
              </div>
              <div className="dn-cd-head-r">
                <button className="dn-icon-btn" title="Copy passage"><IconCopy size={14} /></button>
                <button className="dn-icon-btn dn-cd-close" title="Close" onClick={onClose}>
                  <IconClose size={14} />
                </button>
              </div>
            </header>

            <div className="dn-cd-toolbar">
              <div className="dn-cd-section">
                <span className="dn-mono dn-cd-section-mono">§</span>
                <span>{cite.section ?? passage?.section ?? "Cited passage"}</span>
              </div>
              <div className="dn-cd-tools">
                <button className="dn-chip-sm">Open original</button>
              </div>
            </div>

            <div className="dn-cd-pages">
              <div className="dn-cd-page is-current">
                <div className="dn-cd-gutter">
                  <span className="dn-mono">{cite.page ?? "—"}</span>
                  <span className="dn-cd-gutter-mark" aria-hidden />
                </div>
                <div className="dn-cd-prose">
                  {cite.section && <h4 className="dn-cd-h">{cite.section}</h4>}
                  {/* Context loads async; the highlight is shown instantly from cite.snippet. */}
                  {passage?.pre && <p className="dn-cd-faint">…{cleanLine(passage.pre)}</p>}
                  <p>
                    <mark className="dn-cd-highlight" ref={highlightRef}>
                      {cleanLine(cite.snippet)}
                    </mark>
                  </p>
                  {passage?.post && <p className="dn-cd-faint">{cleanLine(passage.post)}…</p>}
                </div>
              </div>
            </div>

            <footer className="dn-cd-foot">
              <div className="dn-cd-foot-l">
                <span className="dn-mono">⌘ ↵</span>
                <span>Insert passage as quoted note</span>
              </div>
              <button className="dn-btn dn-btn-primary dn-btn-tight">
                <IconQuote size={13} /> Save as note
              </button>
            </footer>
          </>
        )}
      </aside>
    </>
  );
}
