import type { Metadata } from "next";
import { Newsreader, JetBrains_Mono } from "next/font/google";
import { GeistSans } from "geist/font/sans";
import "./globals.css";

const serif = Newsreader({
  subsets: ["latin"],
  variable: "--font-newsreader",
  display: "swap",
  style: ["normal", "italic"],
  axes: ["opsz"], // optical sizing — matches the original's Newsreader:opsz,wght@6..72
  adjustFontFallback: false, // Newsreader has no metrics in next/font's DB; skip (silences warning)
  fallback: ["Source Serif 4", "Georgia", "serif"],
});
const mono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-jetbrains",
  display: "swap",
});

export const metadata: Metadata = {
  title: "DeepNotes",
  description: "Chat with your sources — grounded answers with verifiable citations.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={`${GeistSans.variable} ${serif.variable} ${mono.variable}`}>
        {children}
      </body>
    </html>
  );
}
