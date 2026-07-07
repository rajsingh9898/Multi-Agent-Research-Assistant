"use client"

import React from "react"
import { motion } from "framer-motion"
import { AlertCircle, WifiOff, Lock, ServerCrash, FileX, RefreshCw, Home } from "lucide-react"
import { clsx } from "clsx"

interface ErrorStateProps {
  title?: string
  message: string
  onRetry?: () => void
  onGoHome?: () => void
  type?: "not-found" | "server" | "network" | "auth" | "generic"
}

const typeConfigs = {
  "not-found": {
    icon: <FileX size={36} className="text-red-500" />,
    bg: "bg-red-50 border border-red-100",
    defaultTitle: "Report Not Found",
  },
  server: {
    icon: <ServerCrash size={36} className="text-orange-500" />,
    bg: "bg-orange-50 border border-orange-100",
    defaultTitle: "Server Error",
  },
  network: {
    icon: <WifiOff size={36} className="text-slate-500" />,
    bg: "bg-slate-100 border border-slate-200/60",
    defaultTitle: "Connection Failed",
  },
  auth: {
    icon: <Lock size={36} className="text-blue-500" />,
    bg: "bg-blue-50 border border-blue-100",
    defaultTitle: "Sign In Required",
  },
  generic: {
    icon: <AlertCircle size={36} className="text-red-500" />,
    bg: "bg-red-50 border border-red-100",
    defaultTitle: "Something Went Wrong",
  },
}

export default function ErrorState({
  title,
  message,
  onRetry,
  onGoHome,
  type = "generic",
}: ErrorStateProps) {
  const config = typeConfigs[type] || typeConfigs.generic

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex flex-col items-center justify-center py-16 px-4 text-center"
    >
      {/* ICON BACKGROUND */}
      <div className={clsx("w-20 h-20 rounded-full flex items-center justify-center mx-auto mb-6", config.bg)}>
        {config.icon}
      </div>

      {/* TITLE */}
      <h3 className="text-xl font-bold text-slate-800 mb-2">
        {title || config.defaultTitle}
      </h3>

      {/* MESSAGE */}
      <p className="text-slate-500 max-w-sm mb-8 text-sm leading-relaxed font-medium">
        {message}
      </p>

      {/* ACTIONS */}
      <div className="flex gap-3 flex-wrap justify-center">
        {onRetry && (
          <button
            type="button"
            onClick={onRetry}
            className="flex items-center gap-2 px-5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-sm font-semibold transition-colors focus:outline-none shadow-md shadow-blue-500/10"
          >
            <RefreshCw size={14} className="animate-spin-hover" />
            <span>Try Again</span>
          </button>
        )}

        {onGoHome && (
          <button
            type="button"
            onClick={onGoHome}
            className="flex items-center gap-2 px-5 py-2.5 border border-slate-200 hover:bg-slate-50 text-slate-700 rounded-xl text-sm font-semibold transition-colors focus:outline-none bg-white"
          >
            <Home size={14} />
            <span>Go Home</span>
          </button>
        )}
      </div>
    </motion.div>
  )
}
