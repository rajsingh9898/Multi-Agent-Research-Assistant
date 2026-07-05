"use client"

import React from "react"
import { motion } from "framer-motion"
import { ExternalLink, GraduationCap, Building2, Newspaper, PenLine, HelpCircle } from "lucide-react"
import { clsx } from "clsx"

export interface Source {
  url: string
  title: string
  credibility: string
  credibility_icon: string
}

interface SourceCardProps {
  source: Source
  index: number
}

const credibilityThemes: Record<string, { badge: string; icon: React.ReactNode }> = {
  academic: {
    badge: "bg-green-50 text-green-700 border-green-200",
    icon: <GraduationCap size={12} className="text-green-500" />,
  },
  government: {
    badge: "bg-blue-50 text-blue-700 border-blue-200",
    icon: <Building2 size={12} className="text-blue-500" />,
  },
  news: {
    badge: "bg-yellow-50 text-yellow-700 border-yellow-200",
    icon: <Newspaper size={12} className="text-yellow-600" />,
  },
  blog: {
    badge: "bg-slate-50 text-slate-700 border-slate-200",
    icon: <PenLine size={12} className="text-slate-500" />,
  },
  unknown: {
    badge: "bg-slate-50 text-slate-600 border-slate-200",
    icon: <HelpCircle size={12} className="text-slate-400" />,
  },
}

export default function SourceCard({ source, index }: SourceCardProps) {
  const normalizedCred = (source.credibility || "unknown").toLowerCase()
  const theme = credibilityThemes[normalizedCred] || credibilityThemes.unknown

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05 }}
      className="flex items-start gap-3.5 p-4 rounded-xl border border-slate-200/60 bg-white hover:border-slate-300 hover:bg-slate-50 hover:shadow-sm transition-all duration-200 group"
    >
      {/* Index Number */}
      <span className="text-xs font-mono font-bold text-slate-400 mt-0.5 flex-shrink-0 w-5">
        {index + 1}.
      </span>

      {/* Content area */}
      <div className="flex-1 min-w-0">
        {/* Title */}
        <p className="text-sm font-semibold text-slate-800 leading-snug line-clamp-1 group-hover:text-blue-700 transition-colors duration-150">
          {source.title || "Untitled Source"}
        </p>

        {/* URL Link */}
        <a
          href={source.url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs text-blue-600 hover:underline block truncate mt-1"
          title={source.url}
        >
          {source.url}
        </a>

        {/* Credibility Level Badge */}
        <div className="mt-2.5 flex items-center gap-1">
          <span className={clsx(
            "inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold border capitalize",
            theme.badge
          )}>
            <span className="shrink-0">{source.credibility_icon || theme.icon}</span>
            <span>{source.credibility}</span>
          </span>
        </div>
      </div>

      {/* External Link Redirect icon */}
      <ExternalLink
        size={14}
        className="text-slate-300 group-hover:text-blue-500 flex-shrink-0 mt-1.5 transition-colors duration-150"
      />
    </motion.div>
  )
}
