"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getHealth } from "@/lib/api";
import type { Health } from "@/lib/types";

export function TopBar() {
  const [health, setHealth] = useState<Health | null>(null);
  const [err, setErr] = useState(false);

  useEffect(() => {
    getHealth().then(setHealth).catch(() => setErr(true));
  }, []);

  return (
    <header className="dn-topbar">
      <Link
        href="/"
        className="dn-brand"
        style={{ textDecoration: "none" }}
        aria-label="DeepNotes home"
      >
        <span className="dn-brand-mark" aria-hidden>
          <span className="dn-brand-mark-i" />
          <span className="dn-brand-mark-i" />
        </span>
        <span className="dn-brand-word">DeepNotes</span>
      </Link>
      <div className="dn-top-mid">
        <div className="dn-search">
          <input placeholder="Search across all notebooks…" />
          <span className="dn-kbd">⌘K</span>
        </div>
      </div>
      <div className="dn-top-right">
        <span className="dn-health" title="Backend status">
          <span className={`dn-health-dot ${err ? "is-down" : health ? "is-ok" : ""}`} />
          {err ? "api offline" : health ? `${health.provider} · ${health.llm_model}` : "connecting…"}
        </span>
        <button className="dn-top-link">Settings</button>
      </div>
    </header>
  );
}
