// Lightweight icon set ported from the DeepNotes design (1.5px stroke, currentColor).
import type { CSSProperties, ReactNode } from "react";

function Icon({
  children,
  size = 16,
  style,
}: {
  children: ReactNode;
  size?: number;
  style?: CSSProperties;
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      style={style}
      aria-hidden="true"
    >
      {children}
    </svg>
  );
}

type P = { size?: number; style?: CSSProperties };

export const IconSearch = (p: P) => (
  <Icon {...p}><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></Icon>
);
export const IconPlus = (p: P) => (
  <Icon {...p}><path d="M12 5v14M5 12h14" /></Icon>
);
export const IconSparkle = (p: P) => (
  <Icon {...p}><path d="M12 3v4M12 17v4M3 12h4M17 12h4M5.6 5.6l2.8 2.8M15.6 15.6l2.8 2.8M5.6 18.4l2.8-2.8M15.6 8.4l2.8-2.8" /></Icon>
);
export const IconFileText = (p: P) => (
  <Icon {...p}><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" /><path d="M14 3v5h5M9 13h6M9 17h4" /></Icon>
);
export const IconLink = (p: P) => (
  <Icon {...p}><path d="M10 14a5 5 0 0 0 7 0l3-3a5 5 0 0 0-7-7l-1 1" /><path d="M14 10a5 5 0 0 0-7 0l-3 3a5 5 0 0 0 7 7l1-1" /></Icon>
);
export const IconMic = (p: P) => (
  <Icon {...p}><rect x="9" y="3" width="6" height="12" rx="3" /><path d="M5 11a7 7 0 0 0 14 0M12 18v3" /></Icon>
);
export const IconNote = (p: P) => (
  <Icon {...p}><path d="M5 4h10l4 4v12H5z" /><path d="M15 4v4h4M9 12h6M9 16h4" /></Icon>
);
export const IconPlay = (p: P) => (
  <Icon {...p}><path d="M7 4.5v15l13-7.5z" fill="currentColor" /></Icon>
);
export const IconSend = (p: P) => (
  <Icon {...p}><path d="M4 12 20 4l-3 16-5-6-8-2z" /></Icon>
);
export const IconAttach = (p: P) => (
  <Icon {...p}><path d="M21 11.5 12.5 20a5 5 0 0 1-7-7L13 5.5a3.5 3.5 0 0 1 5 5L10.5 18a2 2 0 0 1-3-3L15 7.5" /></Icon>
);
export const IconClose = (p: P) => (
  <Icon {...p}><path d="M6 6l12 12M18 6 6 18" /></Icon>
);
export const IconChevronRight = (p: P) => (
  <Icon {...p}><path d="m9 6 6 6-6 6" /></Icon>
);
export const IconMore = (p: P) => (
  <Icon {...p}><circle cx="5" cy="12" r="1" fill="currentColor" /><circle cx="12" cy="12" r="1" fill="currentColor" /><circle cx="19" cy="12" r="1" fill="currentColor" /></Icon>
);
export const IconDownload = (p: P) => (
  <Icon {...p}><path d="M12 4v12m0 0-4-4m4 4 4-4M5 20h14" /></Icon>
);
export const IconCheck = (p: P) => (
  <Icon {...p}><path d="m5 12 5 5L20 7" /></Icon>
);
export const IconRefresh = (p: P) => (
  <Icon {...p}><path d="M4 12a8 8 0 0 1 14-5.3L20 9M20 4v5h-5M20 12a8 8 0 0 1-14 5.3L4 15M4 20v-5h5" /></Icon>
);
export const IconBookmark = (p: P) => (
  <Icon {...p}><path d="M6 4h12v17l-6-4-6 4z" /></Icon>
);
export const IconCopy = (p: P) => (
  <Icon {...p}><rect x="8" y="8" width="12" height="12" rx="2" /><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2" /></Icon>
);
export const IconQuote = (p: P) => (
  <Icon {...p}><path d="M6 17c0-4 2-7 5-8M14 17c0-4 2-7 5-8" /><path d="M4 11h5v6H4zM12 11h5v6h-5z" /></Icon>
);
