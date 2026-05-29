"use client";

import type { ReactNode } from "react";
import type { Citation } from "@/lib/types";

const DELETED_SOURCE = "(deleted source)";

/** Lightweight markdown renderer used for BOTH the streaming bubble and the final answer,
 * so prose formatting is identical and doesn't "snap" when citations attach. When a
 * citation map is supplied, inline [n] markers render as clickable chips. */
export function Markdown({
  text, byId, openCite, onCite,
}: {
  text: string;
  byId?: Map<number, Citation>;
  openCite?: Citation | null;
  onCite?: (c: Citation) => void;
}) {
  return <>{renderBlocks(text, byId, openCite ?? null, onCite)}</>;
}

const _INLINE = /(\[\d+\])|(\*\*[^*]+\*\*)|(`[^`]+`)|(\*[^*\n]+\*)|(_[^_\n]+_)/g;

function inline(
  text: string,
  byId?: Map<number, Citation>,
  openCite?: Citation | null,
  onCite?: (c: Citation) => void,
): ReactNode[] {
  const out: ReactNode[] = [];
  let last = 0;
  let m: RegExpExecArray | null;
  let k = 0;
  _INLINE.lastIndex = 0;
  while ((m = _INLINE.exec(text)) !== null) {
    if (m.index > last) out.push(text.slice(last, m.index));
    const tok = m[0];
    if (m[1]) {
      const n = Number(tok.slice(1, -1));
      const c = byId?.get(n);
      if (c) {
        const dead = c.source_title === DELETED_SOURCE;
        out.push(
          dead ? (
            <span key={k} className="dn-cite dn-cite-dead" title="Source removed from this notebook">
              <span className="dn-cite-bracket">⟦</span>
              <span className="dn-cite-n">{n}</span>
              <span className="dn-cite-bracket">⟧</span>
            </span>
          ) : (
            <button
              key={k}
              className={`dn-cite ${openCite?.display_index === n ? "is-active" : ""}`}
              onClick={() => onCite?.(c)}
              title="Open cited passage"
            >
              <span className="dn-cite-bracket">⟦</span>
              <span className="dn-cite-n">{n}</span>
              <span className="dn-cite-bracket">⟧</span>
            </button>
          ),
        );
      } else {
        out.push(tok);
      }
    } else if (tok.startsWith("**")) {
      out.push(<strong key={k}>{tok.slice(2, -2)}</strong>);
    } else if (tok.startsWith("`")) {
      out.push(<code key={k} className="dn-md-code">{tok.slice(1, -1)}</code>);
    } else {
      out.push(<em key={k}>{tok.slice(1, -1)}</em>);
    }
    last = _INLINE.lastIndex;
    k++;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

function renderBlocks(
  text: string,
  byId?: Map<number, Citation>,
  openCite?: Citation | null,
  onCite?: (c: Citation) => void,
): ReactNode[] {
  const lines = (text ?? "").replace(/\r/g, "").split("\n");
  const blocks: ReactNode[] = [];
  let para: string[] = [];
  let list: { ordered: boolean; items: string[] } | null = null;
  let key = 0;

  const flushPara = () => {
    if (para.length) {
      blocks.push(<p key={key++}>{inline(para.join(" "), byId, openCite, onCite)}</p>);
      para = [];
    }
  };
  const flushList = () => {
    if (list) {
      const items = list.items.map((it, i) => (
        <li key={i}>{inline(it, byId, openCite, onCite)}</li>
      ));
      blocks.push(list.ordered ? <ol key={key++}>{items}</ol> : <ul key={key++}>{items}</ul>);
      list = null;
    }
  };

  for (const raw of lines) {
    const line = raw.trimEnd();
    if (!line.trim()) {
      flushPara();
      flushList();
      continue;
    }
    const heading = line.match(/^(#{1,6})\s+(.*)$/);
    const bullet = line.match(/^\s*[-*]\s+(.*)$/);
    const numbered = line.match(/^\s*\d+\.\s+(.*)$/);
    if (heading) {
      flushPara();
      flushList();
      blocks.push(<p key={key++} className="dn-md-h">{inline(heading[2], byId, openCite, onCite)}</p>);
    } else if (bullet || numbered) {
      flushPara();
      const ordered = !!numbered;
      const itemText = (bullet ? bullet[1] : numbered![1]);
      if (!list || list.ordered !== ordered) {
        flushList();
        list = { ordered, items: [] };
      }
      list.items.push(itemText);
    } else {
      flushList();
      para.push(line);
    }
  }
  flushPara();
  flushList();
  return blocks;
}
