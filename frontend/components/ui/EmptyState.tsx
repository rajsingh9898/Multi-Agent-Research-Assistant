"use client"

import React, { type ReactNode } from "react"
import Link from "next/link"
import { motion } from "framer-motion"

interface EmptyStateProps {
  icon?: ReactNode
  title: string
  description: string
  actionLabel?: string
  actionHref?: string
  onAction?: () => void
  secondaryLabel?: string
  onSecondaryAction?: () => void
}

export default function EmptyState({
  icon,
  title,
  description,
  actionLabel,
  actionHref,
  onAction,
  secondaryLabel,
  onSecondaryAction,
}: EmptyStateProps) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.4 }}
      className="flex flex-col items-center justify-center py-20 px-4 text-center"
    >
      {/* ILLUSTRATION */}
      {icon && (
        <div className="w-24 h-24 bg-slate-100/80 border border-slate-200/20 rounded-full flex items-center justify-center mx-auto mb-6 text-slate-400 shadow-inner">
          {icon}
        </div>
      )}

      {/* TITLE */}
      <h3 className="text-xl font-bold text-slate-800 mb-2">
        {title}
      </h3>

      {/* DESCRIPTION */}
      <p className="text-slate-400 max-w-xs mb-8 text-sm font-semibold leading-relaxed">
        {description}
      </p>

      {/* PRIMARY ACTION */}
      {actionLabel && actionHref && (
        <Link
          href={actionHref}
          className="inline-flex items-center gap-2 px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-xl font-bold text-sm transition-all duration-200 shadow-md shadow-blue-500/10 mb-3 focus:outline-none"
        >
          {actionLabel}
        </Link>
      )}

      {actionLabel && onAction && !actionHref && (
        <button
          type="button"
          onClick={onAction}
          className="inline-flex items-center gap-2 px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-xl font-bold text-sm transition-all duration-200 shadow-md shadow-blue-500/10 mb-3 focus:outline-none"
        >
          {actionLabel}
        </button>
      )}

      {/* SECONDARY ACTION */}
      {secondaryLabel && onSecondaryAction && (
        <button
          type="button"
          onClick={onSecondaryAction}
          className="text-sm font-semibold text-slate-500 hover:text-blue-600 transition-colors focus:outline-none mt-2"
        >
          {secondaryLabel}
        </button>
      )}
    </motion.div>
  )
}
