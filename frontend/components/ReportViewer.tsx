"use client"

import React from "react"
import ReactMarkdown from "react-markdown"
import { motion } from "framer-motion"
import { FileText, ListChecks, BookOpen, AlertTriangle, Flag, Link, ExternalLink } from "lucide-react"
import { clsx } from "clsx"

import SourceCard, { type Source } from "./SourceCard"

export interface KeyFinding {
  point: string
  citation: string
  status: "verified" | "uncertain"
}

export interface ReportData {
  title: string
  language: string
  executive_summary: string
  key_findings: KeyFinding[]
  detailed_analysis: string
  limitations: string
  conclusion: string
  sources: Source[]
  word_count: number
  confidence_score: number
  confidence_label: string
  confidence_emoji: string
  sub_questions_covered: string[]
  total_sources_used: number
  generated_at: string
  report_id: string
}

interface ReportViewerProps {
  reportData: ReportData
}

// --- SUB-COMPONENTS ---

function SectionHeader({
  icon,
  title,
  color,
  dark = false,
}: {
  icon: React.ReactNode
  title: string
  color: string
  dark?: boolean
}) {
  const underlineColor = {
    blue: "bg-blue-500",
    emerald: "bg-emerald-500",
    amber: "bg-amber-500",
    slate: "bg-slate-400",
    white: "bg-white",
  }[color] || "bg-slate-400"

  return (
    <div className="mb-5">
      <div className="flex items-center gap-2.5 mb-2">
        <div className="shrink-0">{icon}</div>
        <h2 className={clsx("text-lg font-bold tracking-tight", dark ? "text-white" : "text-slate-900")}>
          {title}
        </h2>
      </div>
      <div className={clsx("h-1 w-12 rounded-full", underlineColor)} />
    </div>
  )
}

function ExecutiveSummary({ content }: { content: string }) {
  return (
    <div className="bg-blue-50/40 rounded-2xl border border-blue-100 border-l-4 border-l-blue-500 p-5 sm:p-6 mb-8 shadow-sm">
      <SectionHeader
        icon={<FileText className="text-blue-600" size={18} />}
        title="Executive Summary"
        color="blue"
      />
      <div className="text-slate-700 leading-relaxed text-sm sm:text-base prose prose-slate max-w-none">
        <ReactMarkdown>{content}</ReactMarkdown>
      </div>
    </div>
  )
}

function KeyFindings({ findings }: { findings: KeyFinding[] }) {
  const getHostname = (urlStr: string): string => {
    try {
      if (!urlStr) return ""
      const url = new URL(urlStr)
      return url.hostname.replace("www.", "")
    } catch {
      return urlStr
    }
  }

  return (
    <div className="mb-8 bg-white border border-slate-200/60 p-5 sm:p-6 rounded-2xl shadow-sm">
      <SectionHeader
        icon={<ListChecks className="text-emerald-600" size={18} />}
        title="Key Research Findings"
        color="emerald"
      />
      
      <div className="space-y-3.5">
        {findings.map((finding, index) => {
          const isVerified = finding.status === "verified"
          return (
            <motion.div
              key={index}
              initial={{ opacity: 0, x: -16 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: index * 0.1 }}
              className={clsx(
                "flex gap-4 p-4 rounded-xl border border-l-4 transition-all duration-200",
                isVerified
                  ? "bg-green-50/30 border-green-200 border-l-green-500 hover:border-green-300"
                  : "bg-yellow-50/30 border-yellow-200 border-l-yellow-500 hover:border-yellow-300"
              )}
            >
              {/* Number tag badge */}
              <span className={clsx(
                "flex-shrink-0 w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold shadow-sm",
                isVerified
                  ? "bg-green-100 text-green-800 border border-green-200"
                  : "bg-yellow-100 text-yellow-800 border border-yellow-200"
              )}>
                {index + 1}
              </span>

              <div className="flex-1 min-w-0">
                {/* Finding text */}
                <p className="text-slate-800 font-semibold text-xs sm:text-sm leading-relaxed">
                  {finding.point}
                </p>

                {/* Citations block */}
                <div className="flex items-center flex-wrap gap-2.5 mt-3">
                  {finding.citation && (
                    <a
                      href={finding.citation}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-[11px] font-bold text-blue-600 hover:underline inline-flex items-center gap-1 bg-white border border-slate-200/50 px-2 py-0.5 rounded-lg shadow-sm"
                    >
                      <ExternalLink size={10} />
                      <span>{getHostname(finding.citation)}</span>
                    </a>
                  )}

                  <span className={clsx(
                    "text-[10px] font-extrabold uppercase px-2 py-0.5 rounded-full border tracking-wide shadow-sm",
                    isVerified
                      ? "bg-green-100/50 border-green-200 text-green-800"
                      : "bg-yellow-100/50 border-yellow-200 text-yellow-800"
                  )}>
                    {isVerified ? "Verified claim" : "Uncertain claim"}
                  </span>
                </div>
              </div>
            </motion.div>
          )
        })}
      </div>
    </div>
  )
}

function DetailedAnalysis({ content }: { content: string }) {
  return (
    <div className="mb-8 bg-white border border-slate-200/60 p-5 sm:p-6 rounded-2xl shadow-sm">
      <SectionHeader
        icon={<BookOpen className="text-blue-600" size={18} />}
        title="Detailed Analytical Breakdown"
        color="blue"
      />
      
      <div className="prose prose-slate max-w-none text-slate-700 leading-relaxed text-sm sm:text-base">
        <ReactMarkdown
          components={{
            p: ({ children }) => <p className="mb-4 leading-7 text-slate-600 font-medium">{children}</p>,
            strong: ({ children }) => <strong className="font-bold text-slate-900">{children}</strong>,
            h3: ({ children }) => <h3 className="text-sm font-extrabold text-slate-800 uppercase tracking-wider mt-6 mb-2 block">{children}</h3>,
            ul: ({ children }) => <ul className="list-disc pl-5 mb-4 space-y-1.5 text-slate-600 font-medium">{children}</ul>,
            li: ({ children }) => <li className="pl-0.5">{children}</li>,
          }}
        >
          {content}
        </ReactMarkdown>
      </div>
    </div>
  )
}

function Limitations({ content }: { content: string }) {
  return (
    <div className="bg-amber-50/40 rounded-2xl border border-amber-100 border-l-4 border-l-amber-400 p-5 sm:p-6 mb-8 shadow-sm">
      <SectionHeader
        icon={<AlertTriangle className="text-amber-600" size={18} />}
        title="Limitations & Uncertainties"
        color="amber"
      />
      <div className="text-slate-700 leading-relaxed text-sm sm:text-base prose prose-slate max-w-none">
        <ReactMarkdown>{content}</ReactMarkdown>
      </div>
    </div>
  )
}

function Conclusion({ content }: { content: string }) {
  return (
    <div className="bg-slate-900 rounded-2xl border border-slate-800 p-5 sm:p-6 mb-8 shadow-md">
      <SectionHeader
        icon={<Flag className="text-white" size={18} />}
        title="Conclusion"
        color="white"
        dark={true}
      />
      <div className="text-slate-300 leading-relaxed text-sm sm:text-base prose prose-invert max-w-none">
        <ReactMarkdown>{content}</ReactMarkdown>
      </div>
    </div>
  )
}

function SourcesList({ sources }: { sources: Source[] }) {
  return (
    <div className="mb-8">
      <SectionHeader
        icon={<Link className="text-slate-600" size={18} />}
        title="Verified Research Sources"
        color="slate"
      />
      <div className="grid grid-cols-1 gap-2.5">
        {sources.map((source, index) => (
          <SourceCard key={index} source={source} index={index} />
        ))}
      </div>
    </div>
  )
}

// --- MAIN WRAPPER ---

export default function ReportViewer({ reportData }: ReportViewerProps) {
  return (
    <div className="space-y-6">
      <ExecutiveSummary content={reportData.executive_summary} />
      
      {reportData.key_findings && reportData.key_findings.length > 0 && (
        <KeyFindings findings={reportData.key_findings} />
      )}

      <DetailedAnalysis content={reportData.detailed_analysis} />
      
      {reportData.limitations && (
        <Limitations content={reportData.limitations} />
      )}

      {reportData.conclusion && (
        <Conclusion content={reportData.conclusion} />
      )}

      {reportData.sources && reportData.sources.length > 0 && (
        <SourcesList sources={reportData.sources} />
      )}
    </div>
  )
}
