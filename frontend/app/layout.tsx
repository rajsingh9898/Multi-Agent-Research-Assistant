"use client"

import React, { useState } from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { Toaster } from "react-hot-toast"
import { Menu, X, Microscope } from "lucide-react"

import AuthButton from "../components/AuthButton"
import "./globals.css"

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  const pathname = usePathname()
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

  const navLinks = [
    { name: "Home", href: "/" },
    { name: "History", href: "/history" },
    { name: "Compare", href: "/compare" },
  ]

  return (
    <html lang="en">
      <body className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(15,23,42,0.05),_transparent_40%),linear-gradient(180deg,_#f8fafc_0%,_#f1f5f9_100%)] text-slate-900 antialiased selection:bg-blue-500 selection:text-white">
        <div className="relative flex min-h-screen flex-col">
          {/* Header Banner */}
          <header className="sticky top-0 z-50 w-full border-b border-slate-200/60 bg-white/70 backdrop-blur-xl transition-all duration-200">
            <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-3 sm:px-6 lg:px-8">
              {/* Logo / Brand */}
              <Link href="/" className="group flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-blue-600 text-white shadow-md shadow-blue-500/20 transition-all duration-200 group-hover:scale-105 group-hover:bg-blue-700">
                  <Microscope size={20} />
                </div>
                <div className="leading-tight">
                  <div className="text-sm font-bold tracking-wide text-slate-900 sm:text-base">
                    🔬 Research AI
                  </div>
                  <div className="text-xs text-slate-400 font-medium">
                    Multi-Agent Intelligence
                  </div>
                </div>
              </Link>

              {/* Desktop Nav Links */}
              <nav className="hidden items-center gap-1 text-sm font-medium md:flex">
                {navLinks.map((link) => {
                  const isActive = pathname === link.href
                  return (
                    <Link
                      key={link.href}
                      href={link.href}
                      className={`rounded-lg px-3.5 py-2 transition-all duration-200 ${
                        isActive
                          ? "bg-slate-100 text-slate-900 font-semibold"
                          : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
                      }`}
                    >
                      {link.name}
                    </Link>
                  )
                })}
              </nav>

              {/* Desktop Auth and Mobile Toggle */}
              <div className="flex items-center gap-3">
                <div className="hidden sm:block">
                  <AuthButton />
                </div>

                {/* Mobile Menu Button */}
                <button
                  type="button"
                  onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
                  className="inline-flex items-center justify-center rounded-xl p-2.5 text-slate-500 hover:bg-slate-100 hover:text-slate-700 focus:outline-none focus:ring-2 focus:ring-slate-300 md:hidden"
                  aria-expanded={mobileMenuOpen}
                  aria-label="Toggle navigation menu"
                >
                  {mobileMenuOpen ? <X size={22} /> : <Menu size={22} />}
                </button>
              </div>
            </div>

            {/* Mobile Navigation Dropdown */}
            {mobileMenuOpen && (
              <div className="border-b border-slate-200 bg-white/95 px-4 py-4 shadow-lg backdrop-blur-md md:hidden">
                <nav className="flex flex-col gap-2">
                  {navLinks.map((link) => {
                    const isActive = pathname === link.href
                    return (
                      <Link
                        key={link.href}
                        href={link.href}
                        onClick={() => setMobileMenuOpen(false)}
                        className={`block rounded-xl px-4 py-3 text-sm font-semibold transition-all duration-200 ${
                          isActive
                            ? "bg-blue-50 text-blue-700"
                            : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
                        }`}
                      >
                        {link.name}
                      </Link>
                    )
                  })}
                  <div className="mt-3 pt-3 border-t border-slate-100 sm:hidden">
                    <AuthButton />
                  </div>
                </nav>
              </div>
            )}
          </header>

          {/* Main Layout Area */}
          <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-8 sm:px-6 lg:px-8">
            {children}
          </main>
        </div>

        {/* Global Toaster Messages */}
        <Toaster
          position="top-right"
          toastOptions={{
            style: {
              borderRadius: "12px",
              background: "#0f172a",
              color: "#fff",
              fontSize: "14px",
              padding: "12px 16px",
            },
          }}
        />
      </body>
    </html>
  )
}
