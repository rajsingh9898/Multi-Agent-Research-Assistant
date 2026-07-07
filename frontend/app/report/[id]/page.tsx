"use client"

import React, { useState, useEffect } from "react"
import { useParams, useRouter } from "next/navigation"
import Link from "next/link"
import { motion, AnimatePresence } from "framer-motion"
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
  Printer,
} from "lucide-react"

import { onAuthChange } from "../../../lib/firebase"
import { researchAPI, type FullReport } from "../../../lib/api"
import ConfidenceScore from "../../../components/ConfidenceScore"
import ReportViewer from "../../../components/ReportViewer"
import FollowUpQuestions from "../../../components/FollowUpQuestions"
import PageTransition from "../../../components/ui/PageTransition"
import { showSuccess, showError, showLoading, dismissToast, RESEARCH_TOASTS } from "../../../components/ui/Toast"
import { SkeletonReportHeader, SkeletonReportSection, SkeletonSidebar } from "../../../components/ui/Skeleton"
import ErrorState from "../../../components/ui/ErrorState"

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
        showError(RESEARCH_TOASTS.SIGNIN_REQUIRED)
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
    const toastId = showLoading(RESEARCH_TOASTS.PDF_GENERATING)

    try {
      const result = await researchAPI.exportPdf(reportId)
      if (result && result.pdf_url) {
        setPdfUrl(result.pdf_url)
        window.open(result.pdf_url, "_blank")
        showSuccess(RESEARCH_TOASTS.PDF_READY)
        dismissToast(toastId)
      } else {
        throw new Error("No PDF link returned by the server")
      }
    } catch (err: any) {
      showError(err.message || "PDF generation request failed")
      dismissToast(toastId)
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
      showSuccess(RESEARCH_TOASTS.LINK_COPIED)
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
      <div className="min-h-screen bg-slate-50 space-y-6">
        <SkeletonReportHeader />
        <div className="max-w-6xl mx-auto px-4 py-8">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            <div className="lg:col-span-2 space-y-6">
              <SkeletonReportSection />
              <SkeletonReportSection withFindings={true} />
              <SkeletonReportSection />
            </div>
            <div className="space-y-6">
              <SkeletonSidebar />
            </div>
          </div>
        </div>
      </div>
    )
  }

  // RENDER B: ERROR & NOT FOUND SCREEN
  if (error || !report) {
    const isNotFound = error === "Report not found"
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
        <ErrorState
          type={isNotFound ? "not-found" : "generic"}
          message={error || "An error occurred while loading the report content. Please try again."}
          onRetry={() => window.location.reload()}
          onGoHome={() => router.push("/")}
        />
      </div>
    )
  }

  const reportData = report.report_data

  // RENDER C: REPORT READER VIEW
  return (
    <PageTransition className="min-h-screen bg-slate-50">
      {/* STICKY BAR HEADER CONTROL */}
      <div className="bg-white border-b border-slate-200/60 sticky top-[69px] z-25 transition-all duration-200 print:hidden">
        <div className="max-w-6xl mx-auto px-4 py-3 flex flex-col md:flex-row md:items-center md:justify-between gap-3">
          
          {/* Back Action + Title */}
          <div className="flex items-center gap-3.5 min-w-0 w-full md:w-auto">
            <Link
              href="/history"
              className="p-2 hover:bg-slate-100 rounded-xl transition-colors shrink-0 focus:outline-none flex items-center gap-1.5 text-xs text-slate-500 font-bold uppercase tracking-wide"
              aria-label="Back to history"
            >
              <ArrowLeft size={18} className="text-slate-600" />
              <span className="hidden sm:inline">History</span>
            </Link>

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
          <div className="flex items-center gap-2 w-full md:w-auto justify-end shrink-0">
            {/* Print button */}
            <button
              type="button"
              onClick={() => window.print()}
              className="flex items-center gap-2 px-3 py-2 border border-slate-200 hover:bg-slate-50 rounded-xl text-xs font-semibold text-slate-700 transition-colors"
            >
              <Printer size={14} />
              <span className="hidden md:inline">Print</span>
            </button>

            {/* PDF export button */}
            <button
              type="button"
              onClick={handleDownloadPdf}
              disabled={isPdfLoading}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-xl text-xs font-semibold transition-all duration-200 shadow-md shadow-blue-500/10"
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
              className="flex items-center gap-2 px-4 py-2 border border-slate-200 hover:bg-slate-50 rounded-xl text-xs font-semibold text-slate-700 transition-colors"
            >
              <Share2 size={14} />
              <span className="hidden md:inline">{isCopied ? "Copied!" : "Share Link"}</span>
            </button>

            {/* Create new button */}
            <button
              type="button"
              onClick={() => router.push("/")}
              className="flex items-center gap-2 px-4 py-2 border border-slate-200 hover:bg-slate-50 rounded-xl text-xs font-semibold text-slate-700 transition-colors"
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
            className="space-y-6 print:hidden"
            initial={{ opacity: 0, x: 16 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.5, delay: 0.15 }}
          >
            {/* Confidence score gauge - Large on desktop */}
            <div className="hidden md:block">
              <ConfidenceScore
                score={report.confidence_score || reportData.confidence_score}
                label={reportData.confidence_label}
                emoji={reportData.confidence_emoji}
                size="lg"
              />
            </div>
            {/* Confidence score gauge - Medium on mobile */}
            <div className="block md:hidden">
              <ConfidenceScore
                score={report.confidence_score || reportData.confidence_score}
                label={reportData.confidence_label}
                emoji={reportData.confidence_emoji}
                size="md"
              />
            </div>

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
    </PageTransition>
  )
}
