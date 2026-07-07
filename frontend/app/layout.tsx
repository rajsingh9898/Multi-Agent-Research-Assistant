"use client"

import React, { useState, useEffect } from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { Toaster } from "react-hot-toast"
import { motion, AnimatePresence, useScroll } from "framer-motion"
import { Home, History, GitCompare, Menu, X, Microscope } from "lucide-react"
import { clsx } from "clsx"

import AuthButton from "../components/AuthButton"
import { TOAST_STYLES } from "../components/ui/Toast"
import "./globals.css"

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  const pathname = usePathname()
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

  // Page Scroll Progress Tracker
  const { scrollYProgress } = useScroll()

  // Close mobile drawer when route changes
  useEffect(() => {
    setMobileMenuOpen(false)
  }, [pathname])

  const navLinks = [
    { href: "/", label: "Home", icon: <Home size={16} /> },
    { href: "/history", label: "History", icon: <History size={16} /> },
    { href: "/compare", label: "Compare", icon: <GitCompare size={16} /> },
  ]

  return (
    <html lang="en">
      <body className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(15,23,42,0.03),_transparent_40%),linear-gradient(180deg,_#f8fafc_0%,_#f1f5f9_100%)] text-slate-900 antialiased selection:bg-blue-100 selection:text-blue-900">
        
        {/* Scroll Progress Bar at very top */}
        <motion.div
          className="fixed top-0 left-0 right-0 h-[3px] bg-blue-600 z-[999] origin-left"
          style={{ scaleX: scrollYProgress }}
        />

        <div className="relative flex min-h-screen flex-col">
          {/* Header Navbar banner */}
          <header className="sticky top-0 z-40 w-full border-b border-slate-200/60 bg-white/80 backdrop-blur-xl transition-all duration-200">
            <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-3 sm:px-6 lg:px-8">
              
              {/* Brand Logo */}
              <Link href="/" className="group flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-blue-600 text-white shadow-md shadow-blue-500/20 transition-all duration-200 group-hover:scale-105 group-hover:bg-blue-700">
                  <Microscope size={20} />
                </div>
                <div className="leading-tight">
                  <div className="text-sm font-bold tracking-wide text-slate-900 sm:text-base">
                    🔬 Research AI
                  </div>
                  <div className="text-xs text-slate-400 font-semibold">
                    Multi-Agent Intelligence
                  </div>
                </div>
              </Link>

              {/* Desktop Nav Links */}
              <nav className="hidden items-center gap-1.5 text-sm font-medium md:flex">
                {navLinks.map((link) => {
                  const isActive = pathname === link.href
                  return (
                    <Link
                      key={link.href}
                      href={link.href}
                      className={clsx(
                        "flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs sm:text-sm font-bold transition-all duration-150",
                        isActive
                          ? "bg-blue-50 text-blue-700 border border-blue-100/30"
                          : "text-slate-600 hover:text-slate-900 hover:bg-slate-100"
                      )}
                    >
                      {link.icon}
                      <span>{link.label}</span>
                    </Link>
                  )
                })}
              </nav>

              {/* Desktop Auth Actions & Mobile Menu trigger */}
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

            {/* Mobile Navigation Slide-out Drawer */}
            <AnimatePresence>
              {mobileMenuOpen && (
                <>
                  {/* Backdrop */}
                  <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    onClick={() => setMobileMenuOpen(false)}
                    className="fixed inset-0 bg-black/40 z-40 md:hidden"
                  />

                  {/* Drawer Menu Panel */}
                  <motion.div
                    initial={{ x: "100%" }}
                    animate={{ x: 0 }}
                    exit={{ x: "100%" }}
                    transition={{ type: "spring", stiffness: 300, damping: 30 }}
                    className="fixed top-0 right-0 bottom-0 w-64 bg-white z-50 shadow-2xl md:hidden flex flex-col"
                  >
                    {/* Header close area */}
                    <div className="flex items-center justify-between p-4 border-b border-slate-100">
                      <span className="font-bold text-slate-800 text-sm uppercase tracking-wide">Menu</span>
                      <button
                        type="button"
                        onClick={() => setMobileMenuOpen(false)}
                        className="p-1.5 text-slate-500 hover:bg-slate-100 rounded-lg transition-colors focus:outline-none"
                      >
                        <X size={20} />
                      </button>
                    </div>

                    {/* Nav actions links */}
                    <nav className="p-4 space-y-1.5 flex-1">
                      {navLinks.map((link) => {
                        const isActive = pathname === link.href
                        return (
                          <Link
                            key={link.href}
                            href={link.href}
                            onClick={() => setMobileMenuOpen(false)}
                            className={clsx(
                              "flex items-center gap-2.5 px-4 py-3 rounded-xl text-sm font-bold transition-all duration-150",
                              isActive
                                ? "bg-blue-50 text-blue-700 border border-blue-100/20"
                                : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
                            )}
                          >
                            {link.icon}
                            <span>{link.label}</span>
                          </Link>
                        )
                      })}
                    </nav>

                    {/* Auth button at bottom */}
                    <div className="p-4 border-t border-slate-100 mb-6 flex justify-center">
                      <AuthButton />
                    </div>
                  </motion.div>
                </>
              )}
            </AnimatePresence>
          </header>

          {/* Main Content Layout area */}
          <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-8 sm:px-6 lg:px-8">
            {children}
          </main>
        </div>

        {/* Global Toaster configuration settings */}
        <Toaster
          position="bottom-right"
          gutter={8}
          containerStyle={{
            bottom: 24,
            right: 24,
          }}
          toastOptions={{
            ...TOAST_STYLES.success,
          }}
        />
      </body>
    </html>
  )
}
