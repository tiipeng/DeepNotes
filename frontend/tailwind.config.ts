import type { Config } from "tailwindcss";

// DeepNotes design tokens mirrored into Tailwind so utilities can use them in later
// phases. The ported component classes live in app/globals.css.
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "var(--bg)",
        "bg-2": "var(--bg-2)",
        "bg-3": "var(--bg-3)",
        surface: "var(--surface)",
        "surface-2": "var(--surface-2)",
        border: "var(--border)",
        "border-2": "var(--border-2)",
        "border-3": "var(--border-3)",
        ink: "var(--ink)",
        "ink-2": "var(--ink-2)",
        muted: "var(--muted)",
        "muted-2": "var(--muted-2)",
        faint: "var(--faint)",
        accent: "var(--accent)",
        "accent-ink": "var(--accent-ink)",
        highlight: "var(--highlight)",
      },
      fontFamily: {
        sans: ["var(--font-geist-sans)"],
        serif: ["var(--font-newsreader)"],
        mono: ["var(--font-jetbrains)"],
      },
      borderRadius: { sm: "6px", md: "10px", lg: "14px", xl: "18px" },
      boxShadow: {
        card: "var(--shadow-card)",
        pop: "var(--shadow-pop)",
        drawer: "var(--shadow-drawer)",
      },
    },
  },
  plugins: [],
};
export default config;
