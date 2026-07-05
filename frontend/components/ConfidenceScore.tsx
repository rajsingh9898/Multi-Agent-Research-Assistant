"use client"

import React from "react"
import { motion } from "framer-motion"
import { clsx } from "clsx"

interface ConfidenceScoreProps {
  score: number
  label: string
  emoji: string
  size?: "sm" | "md" | "lg"
}

// Map score to respective theme properties
const getScoreTheme = (score: number) => {
  if (score >= 80) {
    return {
      bg: "bg-green-50 border-green-200 text-green-700",
      stroke: "stroke-green-500",
      text: "text-green-700",
      bar: "bg-green-500",
      badge: "bg-green-100 text-green-800 border-green-200",
      description: "Well-supported by multiple verified sources",
    }
  }
  if (score >= 60) {
    return {
      bg: "bg-yellow-50 border-yellow-200 text-yellow-700",
      stroke: "stroke-yellow-500",
      text: "text-yellow-700",
      bar: "bg-yellow-500",
      badge: "bg-yellow-100 text-yellow-800 border-yellow-200",
      description: "Reasonably supported, some uncertainty",
    }
  }
  if (score >= 40) {
    return {
      bg: "bg-orange-50 border-orange-200 text-orange-700",
      stroke: "stroke-orange-500",
      text: "text-orange-700",
      bar: "bg-orange-500",
      badge: "bg-orange-100 text-orange-800 border-orange-200",
      description: "Limited sources, treat with caution",
    }
  }
  return {
    bg: "bg-red-50 border-red-200 text-red-700",
    stroke: "stroke-red-500",
    text: "text-red-700",
    bar: "bg-red-500",
    badge: "bg-red-100 text-red-800 border-red-200",
    description: "Very few sources found",
  }
}

export default function ConfidenceScore({
  score,
  label,
  emoji,
  size = "md",
}: ConfidenceScoreProps) {
  const theme = getScoreTheme(score)

  // size="sm" (Compact tag badge)
  if (size === "sm") {
    return (
      <span className={clsx(
        "inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold border",
        theme.badge
      )}>
        <span>{emoji}</span>
        <span>{score}%</span>
        <span>{label}</span>
      </span>
    )
  }

  // size="md" (Standard card display)
  if (size === "md") {
    return (
      <div className={clsx("rounded-xl border p-4 flex items-center justify-between gap-3", theme.bg)}>
        <div className="flex items-center gap-2.5 min-w-0">
          <span className="text-xl shrink-0">{emoji}</span>
          <div className="min-w-0">
            <span className="text-xs font-bold uppercase tracking-wider block text-slate-400">Confidence</span>
            <span className="font-bold text-sm text-slate-800 leading-snug truncate block">{label}</span>
          </div>
        </div>
        <div className="shrink-0 flex items-center justify-center h-10 w-10 rounded-lg bg-white/80 border border-slate-200/40 text-sm font-extrabold text-slate-800">
          {score}%
        </div>
      </div>
    )
  }

  // size="lg" (Full details circular indicator display on report page)
  return (
    <div className={clsx("bg-white rounded-2xl border-2 p-6 shadow-sm", theme.bg)}>
      {/* SCORE CIRCLE AND METADATA ROW */}
      <div className="flex items-center gap-4 mb-4">
        <div className="relative w-20 h-20 shrink-0">
          {/* SVG Progress Circle */}
          <svg viewBox="0 0 36 36" className="w-20 h-20 -rotate-90">
            <circle
              cx="18"
              cy="18"
              r="15.9"
              fill="none"
              strokeWidth="3"
              className="stroke-slate-100"
            />
            <motion.circle
              cx="18"
              cy="18"
              r="15.9"
              fill="none"
              strokeWidth="3"
              strokeDasharray={`${score}, 100`}
              strokeLinecap="round"
              className={clsx("transition-all duration-300", theme.stroke)}
              initial={{ strokeDasharray: "0, 100" }}
              animate={{ strokeDasharray: `${score}, 100` }}
              transition={{ duration: 1.5, ease: "easeOut" }}
            />
          </svg>
          
          {/* Score percentage text in center */}
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="text-xl font-extrabold text-slate-800">{score}%</span>
          </div>
        </div>

        <div className="min-w-0">
          <p className="text-2xl mb-1 filter drop-shadow-sm leading-none">{emoji}</p>
          <p className={clsx("font-extrabold text-lg leading-tight truncate", theme.text)}>
            {label}
          </p>
          <p className="text-xs font-bold text-slate-400 uppercase tracking-wider mt-0.5">
            Validation Level
          </p>
        </div>
      </div>

      {/* HORIZONTAL SCORE BAR */}
      <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
        <motion.div
          className={clsx("h-2 rounded-full", theme.bar)}
          initial={{ width: "0%" }}
          animate={{ width: `${score}%` }}
          transition={{ duration: 1.2, delay: 0.3, ease: "easeOut" }}
        />
      </div>

      {/* DESCRIPTION */}
      <p className="text-xs text-slate-500 mt-3 font-semibold leading-relaxed">
        {theme.description}
      </p>
    </div>
  )
}
