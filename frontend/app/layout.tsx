import type { Metadata } from "next"
import Link from "next/link"
import { Toaster } from "react-hot-toast"

import AuthButton from "../components/AuthButton"

import "./globals.css"

/**
 * Application metadata used by Next.js and browser previews.
 */
export const metadata: Metadata = {
  title: "Multi-Agent Research Assistant",
  description: "A Firebase-authenticated multi-agent research platform with verified reports.",
}

/**
 * Root layout for the entire application.
 */
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(15,23,42,0.08),_transparent_30%),linear-gradient(180deg,_#f8fafc_0%,_#eef2ff_100%)] text-slate-900 antialiased">
        <div className="relative flex min-h-screen flex-col">
          <header className="sticky top-0 z-50 border-b border-slate-200/70 bg-white/80 backdrop-blur-xl">
            <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-3 sm:px-6 lg:px-8">
              <Link href="/" className="group flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-slate-950 text-sm font-bold text-white shadow-lg shadow-slate-950/10 transition group-hover:scale-105">
                  MR
                </div>
                <div className="leading-tight">
                  <div className="text-sm font-semibold tracking-wide text-slate-900">Multi-Agent Research Assistant</div>
                  <div className="text-xs text-slate-500">FastAPI + Next.js + Firebase</div>
                </div>
              </Link>

              <nav className="hidden items-center gap-6 text-sm text-slate-600 md:flex">
                <Link href="/" className="transition hover:text-slate-900">Home</Link>
                <Link href="/compare" className="transition hover:text-slate-900">Compare</Link>
                <Link href="/history" className="transition hover:text-slate-900">History</Link>
              </nav>

              <AuthButton />
            </div>
          </header>

          <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-8 sm:px-6 lg:px-8">{children}</main>
        </div>
        <Toaster
          position="top-right"
          toastOptions={{
            style: {
              borderRadius: "16px",
              background: "#0f172a",
              color: "#fff",
            },
          }}
        />
      </body>
    </html>
  )
}
