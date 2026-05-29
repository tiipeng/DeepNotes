"use client";

import { useEffect, useState } from "react";

/** On-brand confirmation dialog (e.g. delete notebook). */
export function ConfirmModal({
  title, body, cta, danger, onConfirm, onClose,
}: {
  title: string;
  body: string;
  cta: string;
  danger?: boolean;
  onConfirm: () => Promise<void> | void;
  onClose: () => void;
}) {
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const confirm = async () => {
    setBusy(true);
    try {
      await onConfirm();
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <div className="dn-modal-scrim" onClick={onClose} aria-hidden />
      <div className="dn-modal dn-modal-sm" role="dialog" aria-label={title}>
        <div className="dn-modal-head">
          <h2 className="dn-modal-title">{title}</h2>
          <button className="dn-icon-btn" onClick={onClose} title="Close">✕</button>
        </div>
        <p className="dn-modal-sub">{body}</p>
        <div className="dn-modal-actions">
          <button className="dn-btn dn-btn-ghost" onClick={onClose}>Cancel</button>
          <button
            className={`dn-btn ${danger ? "dn-btn-danger" : "dn-btn-primary"}`}
            onClick={confirm}
            disabled={busy}
          >
            {busy ? "Working…" : cta}
          </button>
        </div>
      </div>
    </>
  );
}
