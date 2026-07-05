"use client"

import React, { useState, useEffect } from "react"
import { useParams, useRouter } from "next/navigation"
import { motion, AnimatePresence } from "framer-motion"
import { toast } from "react-hot-toast"
import { type User } from "firebase/auth"

import {
  ArrowLeft,
  Download,
  Share2,
  Plus,
  Clock,
  FileText,
  CheckCircle,
  BarChart3,
  Globe,
  BookOpen,
  Loader2,
  AlertCircle,
  RefreshCw,
} from "lucide-react"

import { onAuthChange } from "../../../lib/firebase"
import { researchAPI, type FullReport } from "../../../lib/api"
import ConfidenceScore from "../../../components/ConfidenceScore"
import ReportViewer from "../../../components/ReportViewer"
import FollowUpQuestions from "../../../components/FollowUpQuestions"

// --- COMPONENT ROOT ---

export default function ReportPage() {
  const router = useRouter()
  const params = useParams()
  const reportId = params.id as string

  // State Management
  const [report, setReport] = useState<FullReport | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [isPdfLoading, setIsPdfLoading] = useState(false)
  const [pdfUrl, setPdfUrl] = useState<string | null>(null)
  const [user, setUser] = useState<User | null>(null)
  const [isCopied, setIsCopied] = useState(false)

  // 1. Auth Sync listener
  useEffect(() => {
    const unsubscribe = onAuthChange((currentUser) => {
      setUser(currentUser)
      if (!currentUser) {
        toast.error("Please sign in to access reports")
        router.push("/")
      }
    })
    return () => unsubscribe()
  }, [router])

  // 2. Fetch report details
  useEffect(() => {
    if (!reportId || !user) return

    const fetchReportData = async () => {
      setIsLoading(true)
      setError(null)
      try {
        const response = await researchAPI.getReport(reportId)
        
        if (response.status === "pending" || response.status === "running") {
          // Report still executing, redirect to status tracker
          router.push(`/research/${reportId}`)
          return
        }

        if (response.status === "failed") {
          setError(response.error || "The research pipeline ended in a failure.")
          setIsLoading(false)
          return
        }

        setReport(response)
        if (response.pdf_url) {
          setPdfUrl(response.pdf_url)
        }
      } catch (err: any) {
        if (err.message && err.message.includes("404")) {
          setError("Report not found")
        } else {
          setError(err.message || "Failed to load report data")
        }
      } finally {
        setIsLoading(false)
      }
    }

    fetchReportData()
  }, [reportId, user, router])

  // 3. Action: Download / Generate PDF
  const handleDownloadPdf = async () => {
    if (pdfUrl) {
      window.open(pdfUrl, "_blank")
      return
    }

    setIsPdfLoading(true)
    const toastId = toast.loading("Generating report PDF document...")

    try {
      const result = await researchAPI.exportPdf(reportId)
      if (result && result.pdf_url) {
        setPdfUrl(result.pdf_url)
        window.open(result.pdf_url, "_blank")
        toast.success("PDF exported successfully! 🎉", { id: toastId })
      } else {
        throw new Error("No PDF link returned by the server")
      }
    } catch (err: any) {
      toast.error(err.message || "PDF generation request failed", { id: toastId })
    } finally {
      setIsPdfLoading(false)
    }
  }

  // 4. Action: Copy link to clipboard
  const handleShare = async () => {
    const shareUrl = window.location.href
    try {
      await navigator.clipboard.writeText(shareUrl)
      setIsCopied(true)
      toast.success("Report link copied to clipboard!")
      setTimeout(() => setIsCopied(false), 2000)
    } catch {
      // Fallback
      window.prompt("Copy URL path:", shareUrl)
    }
  }

  // 5. Action: Follow-up query trigger
  const handleFollowUpClick = (question: string) => {
    router.push(`/?topic=${encodeURIComponent(question)}`)
  }

  // Helper date formatter
  const formatDate = (dateString: string | null): string => {
    if (!dateString) return ""
    try {
      const date = new Date(dateString)
      const options: Intl.DateTimeFormatOptions = {
        month: "long",
        day: "numeric",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        hour12: true,
      }
      return date.toLocaleDateString("en-US", options).replace(",", " at")
    } catch {
      return dateString
    }
  }

  // --- RENDERS PATHS ---

  // RENDER A: SKELETON LOADER SCREEN
  if (isLoading) {
    return (
      <div className="min-h-screen bg-slate-50">
        {/* Header Skeleton */}
        <div className="bg-white border-b border-slate-200">
          <div className="max-w-6xl mx-auto px-4 py-4">
            <div className="flex items-center justify-between">
              <div className="h-6 bg-slate-200 rounded-lg w-48 animate-pulse" />
              <div className="flex gap-2">
                <div className="h-10 bg-slate-200 rounded-lg w-32 animate-pulse" />
                <div className="h-10 bg-slate-200 rounded-lg w-24 animate-pulse" />
              </div>
            </div>
          </div>
        </div>

        {/* Content Skeletons */}
        <div className="max-w-6xl mx-auto px-4 py-8">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            <div className="lg:col-span-2 space-y-6">
              {[1, 2, 3].map((i) => (
                <div key={i} className="bg-white rounded-2xl p-6 border border-slate-200/60 shadow-sm">
                  <div className="h-5 bg-slate-200 rounded w-40 animate-pulse mb-4" />
                  <div className="space-y-2.5">
                    <div className="h-4 bg-slate-100 rounded animate-pulse w-full" />
                    <div className="h-4 bg-slate-100 rounded animate-pulse w-[92%]" />
                    <div className="h-4 bg-slate-100 rounded animate-pulse w-[75%]" />
                  </div>
                </div>
              ))}
            </div>
            {/* Sidebar Skeleton */}
            <div className="space-y-6">
              <div className="bg-white rounded-2xl p-6 border border-slate-200/60 shadow-sm">
                <div className="h-24 bg-slate-200 rounded-xl animate-pulse mb-3" />
                <div className="h-4 bg-slate-100 rounded animate-pulse w-3/4" />
              </div>
              <div className="bg-white rounded-2xl p-6 border border-slate-200/60 shadow-sm">
                <div className="h-5 bg-slate-200 rounded w-32 animate-pulse mb-4" />
                {[1, 2, 3].map((i) => (
                  <div key={i} className="h-10 bg-slate-100 rounded-xl animate-pulse mb-2.5" />
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    )
  }

  // RENDER B: ERROR & NOT FOUND SCREEN
  if (error || !report) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
        <div className="bg-white rounded-3xl border border-red-200/60 p-8 max-w-md w-full text-center shadow-lg shadow-red-50/50">
          <div className="w-16 h-16 bg-red-50 text-red-500 rounded-full flex items-center justify-center mx-auto mb-5 border border-red-100">
            <AlertCircle size={30} />
          </div>
          
          <h2 className="text-2xl font-extrabold text-slate-850 mb-2">
            {error === "Report not found" ? "Report Not Found" : "Unable to load report"}
          </h2>
          <p className="text-slate-500 text-sm mb-6 leading-relaxed">
            {error || "An error occurred while loading the report content. Please try again."}
          </p>

          <div className="flex gap-3 justify-center">
            <button
              type="button"
              onClick={() => router.push("/")}
              className="px-5 py-3 bg-blue-600 text-white rounded-2xl text-sm font-semibold hover:bg-blue-700 transition-colors shadow-md shadow-blue-500/10 flex-1"
            >
              Start New Research
            </button>
            <button
              type="button"
              onClick={() => window.location.reload()}
              className="px-5 py-3 border border-slate-200 text-slate-700 rounded-2xl text-sm font-semibold hover:bg-slate-50 transition-colors flex items-center justify-center gap-2 flex-1"
            >
              <RefreshCw size={14} />
              <span>Retry</span>
            </button>
          </div>
        </div>
      </div>
    )
  }

  const reportData = report.report_data

  // RENDER C: REPORT READER VIEW
  return (
    <div className="min-h-screen bg-slate-50">
      {/* STICKY BAR HEADER CONTROL */}
      <div className="bg-white border-b border-slate-200/60 sticky top-[69px] z-20 transition-all duration-200">
        <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between gap-4">
          
          {/* Back Action + Title */}
          <div className="flex items-center gap-3.5 min-w-0">
            <button
              type="button"
              onClick={() => router.push("/")}
              className="p-2 hover:bg-slate-100 rounded-xl transition-colors shrink-0 focus:outline-none"
              aria-label="Back to dashboard"
            >
              <ArrowLeft size={18} className="text-slate-600" />
            </button>

            <div className="min-w-0">
              <h1 className="font-extrabold text-slate-900 text-sm md:text-base truncate leading-snug">
                {reportData.title}
              </h1>
              <p className="text-[10px] sm:text-xs text-slate-400 mt-0.5 flex items-center gap-1 font-semibold uppercase">
                <span>Generated {formatDate(reportData.generated_at)}</span>
              </p>
            </div>
          </div>

          {/* Action buttons list */}
          <div className="flex items-center gap-2 shrink-0">
            {/* PDF export button */}
            <button
              type="button"
              onClick={handleDownloadPdf}
              disabled={isPdfLoading}
              className="flex items-center gap-2 px-4 py-2.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-xl text-xs sm:text-sm font-semibold transition-all duration-200 shadow-md shadow-blue-500/10"
            >
              {isPdfLoading ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <Download size={14} />
              )}
              <span className="hidden md:inline">
                {pdfUrl ? "Open PDF" : "Download PDF"}
              </span>
            </button>

            {/* Share link button */}
            <button
              type="button"
              onClick={handleShare}
              className="flex items-center gap-2 px-4 py-2.5 border border-slate-200 hover:bg-slate-50 rounded-xl text-xs sm:text-sm font-semibold text-slate-700 transition-colors"
            >
              <Share2 size={14} />
              <span className="hidden md:inline">{isCopied ? "Copied!" : "Share Link"}</span>
            </button>

            {/* Create new button */}
            <button
              type="button"
              onClick={() => router.push("/")}
              className="flex items-center gap-2 px-4 py-2.5 border border-slate-200 hover:bg-slate-50 rounded-xl text-xs sm:text-sm font-semibold text-slate-700 transition-colors"
            >
              <Plus size={14} />
              <span className="hidden md:inline">New Research</span>
            </button>
          </div>
        </div>
      </div>

      {/* REPORT CONTENT BODY */}
      <div className="max-w-6xl mx-auto px-4 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          
          {/* Main article body */}
          <motion.div
            className="lg:col-span-2"
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
          >
            <ReportViewer reportData={reportData} />
          </motion.div>

          {/* Sidebar components */}
          <motion.div
            className="space-y-6"
            initial={{ opacity: 0, x: 16 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.5, delay: 0.15 }}
          >
            {/* Visual Gauge gauge */}
            <ConfidenceScore
              score={report.confidence_score || reportData.confidence_score}
              label={reportData.confidence_label}
              emoji={reportData.confidence_emoji}
              size="lg"
            />

            {/* Stats list card */}
            <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm">
              <h3 className="font-bold text-slate-800 text-sm mb-4 flex items-center gap-2.5">
                <BarChart3 size={16} className="text-slate-400" />
                Report Telemetry
              </h3>

              <div className="space-y-3.5">
                {[
                  {
                    label: "Word Count",
                    value: reportData.word_count?.toLocaleString() || "—",
                    icon: <FileText size={14} className="text-slate-400" />,
                  },
                  {
                    label: "Sources Analyzed",
                    value: reportData.total_sources_used || "—",
                    icon: <BookOpen size={14} className="text-slate-400" />,
                  },
                  {
                    label: "Key Findings",
                    value: reportData.key_findings?.length || "—",
                    icon: <CheckCircle size={14} className="text-slate-400" />,
                  },
                  {
                    label: "Language Mode",
                    value: reportData.language?.charAt(0).toUpperCase() + reportData.language?.slice(1) || "English",
                    icon: <Globe size={14} className="text-slate-400" />,
                  },
                  {
                    label: "Date Created",
                    value: formatDate(reportData.generated_at)?.split(" at")[0] || "—",
                    icon: <Clock size={14} className="text-slate-400" />,
                  },
                ].map((stat) => (
                  <div key={stat.label} className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-slate-500 flex items-center gap-2">
                      {stat.icon}
                      {stat.label}
                    </span>
                    <span className="text-xs font-bold text-slate-800">{stat.value}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Sub-questions covered card */}
            {reportData.sub_questions_covered && reportData.sub_questions_covered.length > 0 && (
              <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm">
                <h3 className="font-bold text-slate-800 text-sm mb-3">Sub-Questions Covered</h3>
                <div className="space-y-2.5">
                  {reportData.sub_questions_covered.map((q, idx) => (
                    <div key={idx} className="flex items-start gap-2.5 text-xs text-slate-600 font-medium leading-relaxed">
                      <span className="text-blue-500 font-bold shrink-0">{idx + 1}.</span>
                      <span>{q}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Smart Follow-ups Suggestions */}
            {report.followup_questions && report.followup_questions.length > 0 && (
              <FollowUpQuestions
                questions={report.followup_questions}
                onQuestionClick={handleFollowUpClick}
              />
            )}

            {/* Link back to history view */}
            <div className="text-center pt-2">
              <button
                type="button"
                onClick={() => router.push("/history")}
                className="text-xs font-semibold text-slate-400 hover:text-blue-600 transition-colors uppercase tracking-wider focus:outline-none"
              >
                View all research reports →
              </button>
            </div>
          </motion.div>
        </div>
      </div>
    </div>
  )
}
