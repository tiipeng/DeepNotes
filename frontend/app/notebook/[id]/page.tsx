"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  addUrlSource,
  createNote,
  deleteNote,
  getMessages,
  getNotebook,
  getNotebookSummary,
  getPassage,
  listNotes,
  listSources,
  listThreads,
  setSourceChecked,
  streamChat,
  uploadSource,
} from "@/lib/api";
import type {
  Citation,
  Message,
  Note,
  Notebook,
  NotebookOverview,
  Passage,
  Source,
  TableResult,
  Thread,
} from "@/lib/types";

const stripMarkers = (s: string) => s.replace(/\s*\[\d+\]/g, "");
// The exact strict-grounding refusal (mirrors backend NOT_FOUND); used to style a
// genuine "not found" differently from a normal conversational/meta reply.
const NOT_FOUND = "I couldn't find an answer to that in your sources.";
// Backend marks a citation whose source was deleted with this title.
const DELETED_SOURCE = "(deleted source)";
const isDeletedCite = (c: Citation) => c.source_title === DELETED_SOURCE;
import { TopBar } from "@/components/TopBar";
import {
  IconAttach,
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
  const [followUps, setFollowUps] = useState<string[]>([]);
  const [openCite, setOpenCite] = useState<Citation | null>(null);
  const [passage, setPassage] = useState<Passage | null>(null);
  const [overview, setOverview] = useState<NotebookOverview | null>(null);
  const [overviewLoading, setOverviewLoading] = useState(false);
  const [notes, setNotes] = useState<Note[]>([]);
  const [toast, setToast] = useState<string | null>(null);
  const [threadId, setThreadId] = useState("default");
  const [threads, setThreads] = useState<Thread[]>([]);

  const flash = useCallback((msg: string) => {
    setToast(msg);
    window.setTimeout(() => setToast(null), 2600);
  }, []);

  const loadSources = useCallback(async () => {
    setSources(await listSources(notebookId));
  }, [notebookId]);
  const loadNotes = useCallback(async () => {
    setNotes(await listNotes(notebookId));
  }, [notebookId]);
  const loadThreads = useCallback(async () => {
    setThreads(await listThreads(notebookId));
  }, [notebookId]);

  useEffect(() => {
    getNotebook(notebookId).then(setNotebook).catch(() => {});
    loadSources().catch(() => {});
    loadNotes().catch(() => {});
    loadThreads().catch(() => {});
  }, [notebookId, loadSources, loadNotes, loadThreads]);

  // Load the active thread's messages whenever the thread changes.
  useEffect(() => {
    getMessages(notebookId, threadId).then(setMessages).catch(() => setMessages([]));
  }, [notebookId, threadId]);

  // While anything is still parsing, poll until it resolves (ready or error).
  const anyParsing = sources.some((s) => s.status === "parsing" && !s.id.startsWith("tmp-"));
  useEffect(() => {
    if (!anyParsing) return;
    const t = window.setInterval(() => loadSources().catch(() => {}), 3000);
    return () => window.clearInterval(t);
  }, [anyParsing, loadSources]);

  const newThread = () => {
    if (streaming !== null) return;
    setChatError(null);
    setMessages([]);
    setThreadId(crypto.randomUUID());
  };
  const switchThread = (tid: string) => {
    if (streaming !== null || tid === threadId) return;
    setChatError(null);
    setThreadId(tid);
  };

  const saveNote = useCallback(
    async (data: { title: string; body: string; tag?: string; source_id?: string }) => {
      try {
        await createNote(notebookId, data);
        await loadNotes();
        flash("Saved to notes");
      } catch {
        flash("Couldn't save note");
      }
    },
    [notebookId, loadNotes, flash],
  );

  const onDeleteNote = useCallback(
    async (id: string) => {
      setNotes((prev) => prev.filter((n) => n.id !== id));
      try {
        await deleteNote(id);
      } catch {
        loadNotes();
      }
    },
    [loadNotes],
  );

  const saveAnswerNote = (m: Message) => {
    const body = stripMarkers(m.text).trim();
    const title = body.split(/(?<=[.?!])\s/)[0].slice(0, 80) || "Answer";
    saveNote({ title, body, tag: "answer" });
  };
  const savePassageNote = (c: Citation) => {
    saveNote({
      title: c.source_title,
      body: stripMarkers(c.snippet).trim(),
      tag: "quote",
      source_id: c.source_id,
    });
  };

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
    const tmpId = `tmp-${Date.now()}`;
    const tmp: Source = {
      id: tmpId, notebook_id: notebookId, kind: "pdf",
      title: file.name, authors: null, venue: null, year: null, pages: null,
      status: "parsing", error_msg: null, checked: true, char_count: 0,
      created_at: new Date().toISOString(),
    };
    setSources((prev) => [...prev, tmp]);
    try {
      await uploadSource(notebookId, file);
      await loadSources();
    } catch (e) {
      setSources((prev) => prev.filter((s) => s.id !== tmpId));
      await loadSources(); // a failed parse may still leave an error row
      flash(e instanceof Error ? e.message : "Upload failed");
    }
  };

  const onAddUrl = async (url: string) => {
    const tmpId = `tmp-${Date.now()}`;
    const tmp: Source = {
      id: tmpId, notebook_id: notebookId, kind: "url",
      title: url, authors: null, venue: null, year: null, pages: null,
      status: "parsing", error_msg: null, checked: true, char_count: 0,
      created_at: new Date().toISOString(),
    };
    setSources((prev) => [...prev, tmp]);
    try {
      await addUrlSource(notebookId, url);
      await loadSources();
    } catch (e) {
      setSources((prev) => prev.filter((s) => s.id !== tmpId));
      await loadSources();
      flash(e instanceof Error ? e.message : "Couldn't add link");
    }
  };

  const ask = async (question: string) => {
    const q = question.trim();
    if (!q || streaming !== null) return;
    setChatError(null);
    setFollowUps([]);
    setStreaming("");
    const userMsg: Message = {
      id: `u-${Date.now()}`, role: "user", text: q,
      created_at: new Date().toISOString(), citations: [], table_result: null,
    };
    setMessages((prev) => [...prev, userMsg]);
    await streamChat(notebookId, q, threadId, {
      onToken: (d) => setStreaming((prev) => (prev ?? "") + d),
      onDone: (done) => {
        const asst: Message = {
          id: done.message_id, role: "assistant", text: done.answer_markdown,
          created_at: new Date().toISOString(),
          citations: done.citations, table_result: done.table_result,
        };
        setMessages((prev) => [...prev, asst]);
        setStreaming(null);
        setFollowUps(done.follow_ups ?? []);
        loadThreads().catch(() => {}); // surface a brand-new thread in the switcher
      },
      onError: (detail) => {
        setChatError(detail);
        setStreaming(null);
      },
    });
  };

  const onCite = async (c: Citation) => {
    if (isDeletedCite(c)) return; // source removed — citation is inert
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
              onAddUrl={onAddUrl}
            />
            <ChatPanel
              messages={messages}
              streaming={streaming}
              chatError={chatError}
              followUps={followUps}
              sourceCount={checkedReady.length}
              overview={overview}
              overviewLoading={overviewLoading}
              threads={threads}
              threadId={threadId}
              onNewThread={newThread}
              onSwitchThread={switchThread}
              openCite={openCite}
              onCite={onCite}
              onAsk={ask}
              onSaveNote={saveAnswerNote}
            />
            <StudioPanel notes={notes} onDeleteNote={onDeleteNote} />
          </div>
        </div>
      </main>

      <CitationDrawer
        cite={openCite}
        passage={passage}
        onSave={savePassageNote}
        onClose={() => {
          setOpenCite(null);
          setPassage(null);
        }}
      />

      {toast && <div className="dn-toast" role="status">{toast}</div>}
    </div>
  );
}

/* ---------------- Sources ---------------- */
function SourcesPanel({
  sources, checkedCount, onToggle, onUpload, onAddUrl,
}: {
  sources: Source[];
  checkedCount: number;
  onToggle: (s: Source) => void;
  onUpload: (f: File) => void;
  onAddUrl: (url: string) => void;
}) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [showLink, setShowLink] = useState(false);
  const [urlVal, setUrlVal] = useState("");

  const submitUrl = () => {
    const u = urlVal.trim();
    if (!/^https?:\/\//i.test(u)) return;
    onAddUrl(u);
    setUrlVal("");
    setShowLink(false);
  };

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
        accept=".pdf,.txt,.md,.docx,.pptx,.xlsx,.html,.mp3,.wav,.m4a"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) onUpload(f);
          e.target.value = "";
        }}
      />
      <button className="dn-add-source" onClick={() => fileRef.current?.click()}>
        <IconPlus size={14} /> <span>Add source</span>
      </button>

      <button className="dn-add-link" onClick={() => setShowLink((v) => !v)}>
        <IconLink size={13} /> <span>Add a web page or YouTube link</span>
      </button>
      {showLink && (
        <div className="dn-link-row">
          <input
            className="dn-link-input"
            placeholder="https://…"
            value={urlVal}
            autoFocus
            onChange={(e) => setUrlVal(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && submitUrl()}
          />
          <button className="dn-btn dn-btn-primary dn-btn-tight" onClick={submitUrl} disabled={!/^https?:\/\//i.test(urlVal.trim())}>
            Add
          </button>
        </div>
      )}

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
                  {s.status === "parsing" ? (
                    <span className="dn-source-status is-parsing">
                      <span className="dn-spin" aria-hidden /> processing…
                    </span>
                  ) : s.status === "error" ? (
                    <span className="dn-source-status is-error" title={s.error_msg ?? undefined}>
                      couldn&apos;t process
                    </span>
                  ) : (
                    <>
                      {s.pages ? <span className="dn-mono">{s.pages}p</span> : null}
                      {s.pages ? <span className="dn-dot" /> : null}
                      <span>{(s.char_count / 1000).toFixed(1)}k chars</span>
                    </>
                  )}
                </span>
                {s.status === "error" && s.error_msg && (
                  <span className="dn-source-errmsg">{s.error_msg}</span>
                )}
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
  messages, streaming, chatError, sourceCount, overview, overviewLoading,
  threads, threadId, onNewThread, onSwitchThread, openCite, onCite, onAsk, onSaveNote, followUps,
}: {
  messages: Message[];
  streaming: string | null;
  chatError: string | null;
  followUps: string[];
  sourceCount: number;
  overview: NotebookOverview | null;
  overviewLoading: boolean;
  threads: Thread[];
  threadId: string;
  onNewThread: () => void;
  onSwitchThread: (tid: string) => void;
  openCite: Citation | null;
  onCite: (c: Citation) => void;
  onAsk: (q: string) => void;
  onSaveNote: (m: Message) => void;
}) {
  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const busy = streaming !== null;

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, streaming, chatError, followUps]);

  const submit = () => {
    onAsk(input);
    setInput("");
  };

  const empty = messages.length === 0 && !busy && !chatError;

  return (
    <section className="dn-col dn-col-chat">
      <div className="dn-col-head">
        <ThreadBar
          threads={threads}
          threadId={threadId}
          busy={busy}
          onSwitch={onSwitchThread}
          onNew={onNewThread}
        />
      </div>

      <OverviewBlock
        overview={overview}
        overviewLoading={overviewLoading}
        sourceCount={sourceCount}
        onAsk={onAsk}
      />

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
                <p className="dn-empty-sub">
                  Every claim links back to the exact passage it came from. Try a suggested
                  question above, or ask your own below.
                </p>
              </>
            ) : overviewLoading ? (
              <>
                <h2 className="dn-empty-title">Reading your sources…</h2>
                <p className="dn-empty-sub">
                  Building an overview and a few good questions to get you started.
                </p>
              </>
            ) : (
              <>
                <h2 className="dn-empty-title">Add a source to begin.</h2>
                <p className="dn-empty-sub">
                  Upload a PDF, document, spreadsheet, web page, video, or audio file on the
                  left. Once it&apos;s indexed, you&apos;ll get a grounded overview and can ask
                  anything — with every claim linked to the exact passage it came from.
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
                <AssistantMessage key={m.id} m={m} openCite={openCite} onCite={onCite} onSaveNote={onSaveNote} />
              ),
            )}
            {busy && <StreamingMessage text={streaming ?? ""} />}
            {!busy && followUps.length > 0 && (
              <div className="dn-followups">
                <div className="dn-followups-label">Suggested follow-ups</div>
                <div className="dn-chip-q-row">
                  {followUps.map((q) => (
                    <button key={q} className="dn-chip-q" onClick={() => onAsk(q)}>
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            )}
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

function ThreadBar({
  threads, threadId, busy, onSwitch, onNew,
}: {
  threads: Thread[];
  threadId: string;
  busy: boolean;
  onSwitch: (tid: string) => void;
  onNew: () => void;
}) {
  const [open, setOpen] = useState(false);
  const current = threads.find((t) => t.thread_id === threadId);
  const label = current ? current.title : "New thread";
  return (
    <>
      <div className="dn-threadbar">
        <div className="dn-thread-select">
          <button
            className="dn-thread-current"
            onClick={() => setOpen((v) => !v)}
            title="Switch thread"
          >
            <IconNote size={13} />
            <span className="dn-thread-current-label">{label}</span>
            <span className={`dn-thread-caret ${open ? "is-open" : ""}`}><IconChevronRight size={12} /></span>
          </button>
          {open && (
            <div className="dn-thread-menu">
              {threads.length === 0 && (
                <div className="dn-thread-empty">No threads yet</div>
              )}
              {threads.map((t) => (
                <button
                  key={t.thread_id}
                  className={`dn-thread-item ${t.thread_id === threadId ? "is-active" : ""}`}
                  onClick={() => { onSwitch(t.thread_id); setOpen(false); }}
                >
                  <span className="dn-thread-item-title">{t.title}</span>
                  <span className="dn-thread-item-count">{t.message_count}</span>
                </button>
              ))}
            </div>
          )}
        </div>
        <button className="dn-btn dn-btn-ghost dn-btn-tight" onClick={onNew} disabled={busy}>
          <IconPlus size={12} /> New thread
        </button>
      </div>
      {open && <div className="dn-thread-scrim" onClick={() => setOpen(false)} aria-hidden />}
    </>
  );
}

function OverviewBlock({
  overview, overviewLoading, sourceCount, onAsk,
}: {
  overview: NotebookOverview | null;
  overviewLoading: boolean;
  sourceCount: number;
  onAsk: (q: string) => void;
}) {
  const [open, setOpen] = useState(true);
  const ready = overview?.ready;
  if (!ready && !overviewLoading) return null; // nothing to show until sources exist

  return (
    <div className="dn-overview">
      <button className="dn-overview-head" onClick={() => setOpen((v) => !v)}>
        <span className="dn-overview-title">
          <IconSparkle size={13} /> Overview
        </span>
        <span className={`dn-overview-caret ${open ? "is-open" : ""}`}>
          <IconChevronRight size={13} />
        </span>
      </button>
      {open && (
        <div className="dn-overview-body">
          {ready ? (
            <>
              {overview!.summary && <p className="dn-overview-summary">{overview!.summary}</p>}
              {overview!.suggested_questions.length > 0 && (
                <div className="dn-chip-q-row">
                  {overview!.suggested_questions.map((q) => (
                    <button
                      key={q}
                      className="dn-chip-q"
                      onClick={() => onAsk(q)}
                      disabled={sourceCount === 0}
                    >
                      {q}
                    </button>
                  ))}
                </div>
              )}
            </>
          ) : (
            <div className="dn-skel dn-skel-line" style={{ height: 36 }} />
          )}
        </div>
      )}
    </div>
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
  m, openCite, onCite, onSaveNote,
}: {
  m: Message;
  openCite: Citation | null;
  onCite: (c: Citation) => void;
  onSaveNote: (m: Message) => void;
}) {
  const byId = new Map(m.citations.map((c) => [c.display_index, c]));
  const grounded = m.citations.length > 0;
  const table = m.table_result;
  const isRefusal = m.text.trim() === NOT_FOUND;

  const byline = table
    ? `Computed from ${table.source_title}`
    : grounded
      ? `Grounded in ${new Set(m.citations.map((c) => c.source_id)).size} source(s)`
      : isRefusal
        ? "Not found in your sources"
        : "DeepNotes";

  return (
    <div className="dn-msg-assistant">
      <div className="dn-msg-byline">
        <span className="dn-assistant-mark" aria-hidden><IconSparkle size={12} /></span>
        <span className="dn-msg-byline-text">{byline}</span>
      </div>

      <div className={`dn-answer ${isRefusal ? "dn-answer-notfound" : ""}`}>
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
                className={`dn-cited-card ${openCite?.display_index === c.display_index ? "is-active" : ""} ${isDeletedCite(c) ? "is-deleted" : ""}`}
                onClick={() => onCite(c)}
                disabled={isDeletedCite(c)}
              >
                <span className="dn-cited-n">{c.display_index}</span>
                <span className="dn-cited-body">
                  <span className="dn-cited-title">{c.source_title}</span>
                  <span className="dn-cited-meta">
                    {isDeletedCite(c)
                      ? "source removed"
                      : `${c.section ?? c.source_venue ?? c.source_kind.toUpperCase()}${c.page ? ` · p. ${c.page}` : ""}`}
                  </span>
                </span>
              </button>
            ))}
          </div>
        </div>
      )}

      {(grounded || table) && (
        <div className="dn-msg-tools">
          <button
            className="dn-tool"
            onClick={() => navigator.clipboard?.writeText(stripMarkers(m.text))}
          >
            <IconCopy size={13} /> Copy
          </button>
          <button className="dn-tool" onClick={() => onSaveNote(m)}>
            <IconQuote size={13} /> Save as note
          </button>
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
        if (isDeletedCite(c)) {
          return (
            <span key={i} className="dn-cite dn-cite-dead" title="Source removed from this notebook">
              <span className="dn-cite-bracket">⟦</span>
              <span className="dn-cite-n">{n}</span>
              <span className="dn-cite-bracket">⟧</span>
            </span>
          );
        }
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
function StudioPanel({
  notes, onDeleteNote,
}: {
  notes: Note[];
  onDeleteNote: (id: string) => void;
}) {
  return (
    <aside className="dn-col">
      <div className="dn-col-head">
        <div className="dn-col-title">
          Studio <span className="dn-col-count">{notes.length}</span>
        </div>
      </div>
      <div className="dn-studio-section">
        <div className="dn-studio-h"><IconMic size={13} /> <span>Audio overview</span></div>
        <div className="dn-audio-cta is-soon" aria-disabled>
          <span className="dn-audio-cta-mark"><IconSparkle size={15} /></span>
          <span className="dn-audio-cta-body">
            <span className="dn-audio-cta-title">
              Audio overview <span className="dn-soon-badge">Soon</span>
            </span>
            <span className="dn-audio-cta-sub">A two-host conversation through your sources</span>
          </span>
        </div>
      </div>
      <div className="dn-studio-section dn-studio-notes">
        <div className="dn-studio-h"><IconNote size={13} /> <span>Notes</span></div>
        {notes.length === 0 ? (
          <div className="dn-studio-empty">
            Save an answer or a cited passage and it&apos;ll be kept here.
          </div>
        ) : (
          <div className="dn-notes">
            {notes.map((n) => (
              <NoteCard key={n.id} note={n} onDelete={() => onDeleteNote(n.id)} />
            ))}
          </div>
        )}
      </div>
    </aside>
  );
}

function NoteCard({ note, onDelete }: { note: Note; onDelete: () => void }) {
  const [open, setOpen] = useState(false);
  const date = new Date(note.created_at).toLocaleDateString(undefined, { month: "short", day: "numeric" });
  return (
    <div className="dn-note">
      {note.tag && <span className="dn-note-tag">{note.tag}</span>}
      <button className="dn-note-title-btn" onClick={() => setOpen((v) => !v)}>
        <span className="dn-note-title">{note.title}</span>
      </button>
      <p className={`dn-note-body ${open ? "" : "dn-note-body-clamp"}`}>{note.body}</p>
      <div className="dn-note-foot">
        <span>{date}</span>
        <button className="dn-note-del" onClick={onDelete} title="Delete note">
          <IconClose size={12} /> Delete
        </button>
      </div>
    </div>
  );
}

/* ---------------- Citation drawer ---------------- */
function cleanLine(s: string) {
  return s.replace(/^#{1,6}\s+/gm, "");
}

function CitationDrawer({
  cite, passage, onSave, onClose,
}: {
  cite: Citation | null;
  passage: Passage | null;
  onSave: (c: Citation) => void;
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

  // Esc closes the drawer.
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
                <button
                  className="dn-icon-btn"
                  title="Copy passage"
                  onClick={() => navigator.clipboard?.writeText(cleanLine(cite.snippet))}
                >
                  <IconCopy size={14} />
                </button>
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
                <span className="dn-cd-esc-hint"><span className="dn-mono">Esc</span> to close</span>
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
                <span>Keep this passage in your notebook&apos;s notes</span>
              </div>
              <button className="dn-btn dn-btn-primary dn-btn-tight" onClick={() => onSave(cite)}>
                <IconQuote size={13} /> Save as note
              </button>
            </footer>
          </>
        )}
      </aside>
    </>
  );
}
