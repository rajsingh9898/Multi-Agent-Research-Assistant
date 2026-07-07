"use client"

import React from "react"
import Link from "next/link"
import { motion } from "framer-motion"
import {
  CheckCircle,
  Loader2,
  Clock,
  XCircle,
  FileText,
  Eye,
  RefreshCw,
  Download,
  Trash2,
} from "lucide-react"
import { clsx } from "clsx"

import { type HistoryReport } from "../lib/api"

interface ReportHistoryCardProps {
  report: HistoryReport
  onDelete: (reportId: string, topic: string) => void
  index: number
}

const statusConfig = {
  done: {
    dot: "bg-green-500",
    badge: "bg-green-100 text-green-700 border-green-200",
    label: "Complete",
    icon: <CheckCircle size={12} className="text-green-600" />,
  },
  running: {
    dot: "bg-blue-500 animate-pulse",
    badge: "bg-blue-100 text-blue-700 border-blue-200",
    label: "In Progress",
    icon: <Loader2 size={12} className="animate-spin text-blue-600" />,
  },
  pending: {
    dot: "bg-yellow-500 animate-pulse",
    badge: "bg-yellow-100 text-yellow-700 border-yellow-250",
    label: "Pending",
    icon: <Clock size={12} className="text-yellow-600" />,
  },
  failed: {
    dot: "bg-red-500",
    badge: "bg-red-100 text-red-700 border-red-200",
    label: "Failed",
    icon: <XCircle size={12} className="text-red-600" />,
  },
}

const depthConfig: Record<string, { label: string; icon: string; color: string }> = {
  quick: { label: "Quick", icon: "⚡", color: "text-green-600 font-semibold" },
  deep: { label: "Deep", icon: "🔍", color: "text-blue-600 font-semibold" },
  expert: { label: "Expert", icon: "🎓", color: "text-purple-600 font-semibold" },
}

const langFlags: Record<string, string> = {
  english: "🇬🇧",
  hindi: "🇮🇳",
  spanish: "🇪🇸",
}

export default function ReportHistoryCard({
  report,
  onDelete,
  index,
}: ReportHistoryCardProps) {
  function formatDate(dateStr: string | null): string {
    if (!dateStr) return "Unknown date"
    try {
      const date = new Date(dateStr)
      return date.toLocaleDateString("en-IN", {
        day: "numeric",
        month: "short",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        hour12: true,
      })
    } catch {
      return dateStr
    }
  }

  const currentStatus = statusConfig[report.status] || statusConfig.failed

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, x: -100, scale: 0.95 }}
      transition={{ delay: index * 0.05 }}
      layout
      className="bg-white rounded-2xl border border-slate-200/80 p-5 hover:border-slate-300 hover:shadow-md transition-all duration-200 group flex flex-col justify-between"
    >
      <div>
        {/* TOP ROW: Status + Topic */}
        <div className="flex items-start justify-between gap-3 mb-3.5">
          {/* LEFT: Status dot + Topic */}
          <div className="flex items-start gap-2.5 flex-1 min-w-0">
            {/* STATUS DOT */}
            <div
              className={clsx(
                "w-2.5 h-2.5 rounded-full flex-shrink-0 mt-1.5",
                currentStatus.dot
              )}
            />

            {/* TOPIC */}
            <div className="flex-1 min-w-0">
              <h3 className="font-bold text-slate-800 text-sm leading-snug line-clamp-2 group-hover:text-blue-700 transition-colors duration-150">
                {report.topic}
              </h3>

              {/* META: Date */}
              <p className="text-[11px] text-slate-400 font-semibold mt-1">
                {formatDate(report.created_at)}
              </p>
            </div>
          </div>

          {/* STATUS BADGE */}
          <span
            className={clsx(
              "flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold border flex-shrink-0 shadow-sm",
              currentStatus.badge
            )}
          >
            {currentStatus.icon}
            <span>{currentStatus.label}</span>
          </span>
        </div>

        {/* MIDDLE: Stats row */}
        <div className="flex items-center flex-wrap gap-2.5 mb-4 text-xs text-slate-500 font-semibold">
          {/* DEPTH */}
          <span
            className={clsx(
              "flex items-center gap-1",
              depthConfig[report.depth]?.color || "text-slate-500"
            )}
          >
            <span>{depthConfig[report.depth]?.icon}</span>
            <span>{depthConfig[report.depth]?.label || report.depth}</span>
          </span>

          {/* SEPARATOR */}
          <span className="text-slate-300">•</span>

          {/* LANGUAGE */}
          <span className="flex items-center gap-1">
            <span>{langFlags[report.language] || "🌐"}</span>
            <span className="capitalize">{report.language}</span>
          </span>

          {/* WORD COUNT (if done) */}
          {report.word_count && report.word_count > 0 && (
            <>
              <span className="text-slate-300">•</span>
              <span className="text-slate-600 font-bold">
                {report.word_count.toLocaleString()} words
              </span>
            </>
          )}
        </div>

        {/* CONFIDENCE BAR (only for done) */}
        {report.status === "done" && report.confidence_score > 0 && (
          <div className="mb-4 bg-slate-50 border border-slate-100 p-2.5 rounded-xl">
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                Confidence Score
              </span>
              <span
                className={clsx(
                  "text-xs font-extrabold",
                  report.confidence_score >= 80
                    ? "text-green-600"
                    : report.confidence_score >= 60
                    ? "text-yellow-600"
                    : "text-red-650"
                )}
              >
                {report.confidence_score}%
              </span>
            </div>
            <div className="w-full bg-slate-200/50 rounded-full h-1.5 overflow-hidden">
              <motion.div
                className={clsx(
                  "h-1.5 rounded-full",
                  report.confidence_score >= 80
                    ? "bg-green-500"
                    : report.confidence_score >= 60
                    ? "bg-yellow-500"
                    : "bg-red-500"
                )}
                initial={{ width: "0%" }}
                animate={{ width: `${report.confidence_score}%` }}
                transition={{ duration: 0.8, delay: index * 0.05 + 0.2 }}
              />
            </div>
          </div>
        )}

        {/* RUNNING PROGRESS (only for running) */}
        {report.status === "running" && (
          <div className="mb-4 bg-blue-50/50 border border-blue-100/50 p-2.5 rounded-xl">
            <p className="text-[10px] font-bold text-blue-600 mb-1.5 flex items-center gap-1 uppercase tracking-wider">
              <Loader2 size={10} className="animate-spin" />
              Research in progress...
            </p>
            <div className="w-full bg-blue-100 rounded-full h-1.5 overflow-hidden">
              <div className="h-1.5 bg-blue-500 rounded-full animate-pulse w-2/3" />
            </div>
          </div>
        )}
      </div>

      {/* BOTTOM ROW: Action buttons */}
      <div className="flex items-center gap-2 mt-2">
        {/* PRIMARY ACTION */}
        {report.status === "done" && (
          <Link
            href={`/report/${report.report_id}`}
            className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs font-semibold transition-colors duration-150 shadow-md shadow-blue-500/10"
          >
            <FileText size={12} />
            <span>View Report</span>
          </Link>
        )}

        {report.status === "running" && (
          <Link
            href={`/research/${report.report_id}`}
            className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2.5 bg-blue-50 hover:bg-blue-100 text-blue-750 border border-blue-200/50 rounded-xl text-xs font-semibold transition-colors duration-150"
          >
            <Eye size={12} />
            <span>Watch Progress</span>
          </Link>
        )}

        {report.status === "pending" && (
          <Link
            href={`/research/${report.report_id}`}
            className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2.5 bg-yellow-50 hover:bg-yellow-100 text-yellow-750 border border-yellow-200/50 rounded-xl text-xs font-semibold transition-colors duration-150"
          >
            <Clock size={12} />
            <span>View Status</span>
          </Link>
        )}

        {report.status === "failed" && (
          <Link
            href="/"
            className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl text-xs font-semibold transition-colors duration-150"
          >
            <RefreshCw size={12} />
            <span>Retry Research</span>
          </Link>
        )}

        {/* PDF LINK (if available) */}
        {report.pdf_url && (
          <a
            href={report.pdf_url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center justify-center gap-1.5 px-3 py-2.5 border border-slate-200 hover:bg-slate-50 text-slate-600 rounded-xl text-xs font-semibold transition-colors duration-150"
            title="Download PDF"
          >
            <Download size={12} />
            <span>PDF</span>
          </a>
        )}

        {/* DELETE BUTTON */}
        <button
          type="button"
          onClick={(e) => {
            e.preventDefault()
            e.stopPropagation()
            onDelete(report.report_id, report.topic)
          }}
          className="flex items-center justify-center p-2.5 text-slate-450 border border-transparent hover:border-red-100 hover:text-red-500 hover:bg-red-50 rounded-xl transition-colors duration-150"
          title="Delete report"
        >
          <Trash2 size={14} />
        </button>
      </div>
    </motion.div>
  )
}
