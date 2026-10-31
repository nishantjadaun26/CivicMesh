import type { Metadata } from "next";
import Link from "next/link";
import { Network } from "lucide-react";
import "./globals.css";
export const metadata: Metadata = {
  title: "CivicMesh",
  description: "Shared evidence for a better neighbourhood.",
};
export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <a href="#main" className="sr-only focus:not-sr-only">
          Skip to content
        </a>
        <header className="border-b border-teal-900/15">
          <nav
            aria-label="Main"
            className="max-w-6xl mx-auto px-6 py-5 flex flex-wrap items-center gap-6"
          >
            <Link
              href="/"
              className="font-bold text-xl flex items-center gap-2 mr-auto"
            >
              <Network aria-hidden="true" /> CivicMesh
            </Link>
            <Link href="/reports">Report an issue</Link>
            <Link href="/incidents">Incidents</Link>
            <Link href="/auth">Sign in</Link>
          </nav>
        </header>
        <main id="main" className="max-w-6xl mx-auto px-6 py-10 md:py-16">
          {children}
        </main>
        <footer className="max-w-6xl mx-auto px-6 py-8 text-sm text-teal-900/70 border-t border-teal-900/15">
          Citizen evidence. Clear provenance. Authority updates kept separate.
        </footer>
      </body>
    </html>
  );
}
