"use client";

import { useEffect, useState } from "react";

/** Reusable name dialog (create / rename) — replaces native window.prompt. */
export function NameModal({
  title, label, initial, cta, onSubmit, onClose,
}: {
  title: string;
  label: string;
  initial: string;
  cta: string;
  onSubmit: (value: string) => Promise<void> | void;
  onClose: () => void;
}) {
  const [value, setValue] = useState(initial);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const submit = async () => {
    if (!value.trim() || busy) return;
    setBusy(true);
    try {
      await onSubmit(value.trim());
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
        <label className="dn-field">
          <span className="dn-field-label">{label}</span>
          <input
            className="dn-input"
            value={value}
            autoFocus
            onFocus={(e) => e.target.select()}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && submit()}
          />
        </label>
        <div className="dn-modal-actions">
          <button className="dn-btn dn-btn-ghost" onClick={onClose}>Cancel</button>
          <button className="dn-btn dn-btn-primary" onClick={submit} disabled={busy || !value.trim()}>
            {busy ? "Working…" : cta}
          </button>
        </div>
      </div>
    </>
  );
}
