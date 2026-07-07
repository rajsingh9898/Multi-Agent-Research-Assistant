"use client"

import React, { useState, useEffect } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { motion, AnimatePresence } from "framer-motion"
import { type User } from "firebase/auth"
import {
  History,
  Plus,
  Search,
  Loader2,
  FileX,
  RefreshCw,
  BarChart3,
  TrendingUp,
  BookOpen,
  CheckCircle,
} from "lucide-react"
import { clsx } from "clsx"

import { onAuthChange } from "../../lib/firebase"
import { researchAPI, type HistoryReport, type ReportStatus } from "../../lib/api"
import ReportHistoryCard from "../../components/ReportHistoryCard"
import DeleteConfirmModal from "../../components/DeleteConfirmModal"
import PageTransition from "../../components/ui/PageTransition"
import { showSuccess, showError, RESEARCH_TOASTS } from "../../components/ui/Toast"
import { SkeletonCard } from "../../components/ui/Skeleton"
import ErrorState from "../../components/ui/ErrorState"
import EmptyState from "../../components/ui/EmptyState"

interface DeleteModalState {
  isOpen: boolean
  reportId: string | null
  topic: string
}

export default function HistoryPage() {
  const router = useRouter()

  // State Management
  const [reports, setReports] = useState<HistoryReport[]>([])
  const [filteredReports, setFilteredReports] = useState<HistoryReport[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState("")
  const [statusFilter, setStatusFilter] = useState<"all" | ReportStatus>("all")
  const [isDeleting, setIsDeleting] = useState(false)
  const [user, setUser] = useState<User | null>(null)
  const [limit, setLimit] = useState(20)

  const [deleteModal, setDeleteModal] = useState<DeleteModalState>({
    isOpen: false,
    reportId: null,
    topic: "",
  })

  const [stats, setStats] = useState({
    total: 0,
    done: 0,
    avgConfidence: 0,
    totalWords: 0,
  })

  // 1. Auth synchronization listener
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

  // 2. Fetch history when user is authenticated
  useEffect(() => {
    if (user) {
      fetchHistory()
    }
  }, [user])

  const fetchHistory = async (customLimit?: number) => {
    setIsLoading(true)
    setError(null)
    try {
      const currentLimit = customLimit || limit
      const response = await researchAPI.getHistory(currentLimit)
      const reportsList = response.reports || []
      setReports(reportsList)
      setFilteredReports(reportsList)
      calculateStats(reportsList)
    } catch (err: any) {
      setError(err.message || "Failed to load report history")
      showError("Could not load reports")
    } finally {
      setIsLoading(false)
    }
  }

  const handleLoadMore = () => {
    const newLimit = limit + 20
    setLimit(newLimit)
    fetchHistory(newLimit)
  }

  // 3. Stats calculations
  const calculateStats = (reportsList: HistoryReport[]) => {
    const doneReports = reportsList.filter((r) => r.status === "done")
    const totalWords = doneReports.reduce((sum, r) => sum + (r.word_count || 0), 0)
    const avgConf =
      doneReports.length > 0
        ? Math.round(doneReports.reduce((sum, r) => sum + (r.confidence_score || 0), 0) / doneReports.length)
        : 0

    setStats({
      total: reportsList.length,
      done: doneReports.length,
      avgConfidence: avgConf,
      totalWords,
    })
  }

  // 4. Searching and status filtering observer
  useEffect(() => {
    let filtered = [...reports]

    // Topic query filter
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase()
      filtered = filtered.filter((r) => r.topic.toLowerCase().includes(query))
    }

    // Status filter selection
    if (statusFilter !== "all") {
      filtered = filtered.filter((r) => r.status === statusFilter)
    }

    setFilteredReports(filtered)
  }, [reports, searchQuery, statusFilter])

  // 5. Deletion Handlers
  const handleDeleteClick = (reportId: string, topic: string) => {
    setDeleteModal({
      isOpen: true,
      reportId,
      topic,
    })
  }

  const handleDeleteConfirm = async () => {
    if (!deleteModal.reportId) return

    setIsDeleting(true)
    try {
      await researchAPI.deleteReport(deleteModal.reportId)

      // Filter locally from list to update view immediately
      const remainingReports = reports.filter((r) => r.report_id !== deleteModal.reportId)
      setReports(remainingReports)
      calculateStats(remainingReports)

      showSuccess(RESEARCH_TOASTS.REPORT_DELETED)
      setDeleteModal({ isOpen: false, reportId: null, topic: "" })
    } catch (err: any) {
      showError("Delete failed. Please try again.")
    } finally {
      setIsDeleting(false)
    }
  }

  // --- RENDER SECTIONS ---

  return (
    <PageTransition className="min-h-screen bg-slate-50">
      {/* Pull-to-refresh mobile hint */}
      <div className="block sm:hidden text-center py-1.5 text-[10px] font-bold text-slate-400 bg-slate-100/50 border-b border-slate-200/40 tracking-wider">
        ↻ Pull down to refresh
      </div>

      {/* PAGE HEADER */}
      <div className="bg-white border-b border-slate-200">
        <div className="max-w-5xl mx-auto px-4 py-6">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h1 className="text-2xl font-extrabold text-slate-900 flex items-center gap-2">
                <History size={24} className="text-blue-600 animate-pulse" />
                Research History
              </h1>
              <p className="text-slate-500 text-sm mt-1 font-semibold">
                {stats.total > 0
                  ? `${stats.total} report${stats.total !== 1 ? "s" : ""} total`
                  : "No reports yet"}
              </p>
            </div>

            {/* NEW RESEARCH LINK */}
            <Link
              href="/"
              className="flex items-center gap-2 px-4 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs sm:text-sm font-semibold transition-all shadow-md shadow-blue-500/10"
            >
              <Plus size={16} />
              <span>New Research</span>
            </Link>
          </div>

          {/* TELEMETRY METRIC STATS CARDS */}
          {stats.total > 0 && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
              {[
                {
                  label: "Total Reports",
                  value: stats.total,
                  icon: <BookOpen size={18} className="text-blue-500" />,
                },
                {
                  label: "Completed",
                  value: stats.done,
                  icon: <CheckCircle size={18} className="text-green-500" />,
                },
                {
                  label: "Avg Confidence",
                  value: stats.done > 0 ? `${stats.avgConfidence}%` : "—",
                  icon: <TrendingUp size={18} className="text-purple-500" />,
                },
                {
                  label: "Words Written",
                  value: stats.totalWords > 0 ? stats.totalWords.toLocaleString() : "—",
                  icon: <BarChart3 size={18} className="text-amber-500" />,
                },
              ].map((stat) => (
                <div key={stat.label} className="bg-white rounded-xl border border-slate-200/60 p-4 shadow-sm">
                  <div className="flex items-center gap-2 mb-1">
                    {stat.icon}
                    <span className="text-xs font-semibold text-slate-550 uppercase tracking-wide">
                      {stat.label}
                    </span>
                  </div>
                  <p className="text-2xl font-extrabold text-slate-800">{stat.value}</p>
                </div>
              ))}
            </div>
          )}

          {/* SEARCH & FILTERS BAR */}
          {reports.length > 0 && (
            <div className="flex flex-col sm:flex-row gap-3">
              {/* SEARCH TEXTBOX */}
              <div className="relative flex-1">
                <Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
                <input
                  type="text"
                  placeholder="Search reports..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-10 pr-4 py-2.5 border border-slate-200/80 rounded-xl text-sm focus:outline-none focus:border-blue-400 bg-white placeholder-slate-400 text-slate-800 font-medium transition-colors"
                />
              </div>

              {/* STATUS FILTER ACCORD */}
              <div className="flex gap-2 flex-wrap">
                {(["all", "done", "running", "failed"] as const).map((status) => (
                  <button
                    key={status}
                    type="button"
                    onClick={() => setStatusFilter(status)}
                    className={clsx(
                      "px-4 py-2.5 rounded-xl text-xs font-bold transition-all shadow-sm capitalize border",
                      statusFilter === status
                        ? "bg-blue-600 text-white border-blue-600"
                        : "bg-white border-slate-200 text-slate-600 hover:bg-slate-50"
                    )}
                  >
                    {status === "all" ? "All Statuses" : status}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* MAIN HISTORY BODY */}
      <div className="max-w-5xl mx-auto px-4 py-8">
        {/* LOADING STATE - skeleton cards */}
        {isLoading && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {[1, 2, 3, 4].map((i) => (
              <SkeletonCard key={i} />
            ))}
          </div>
        )}

        {/* ERROR STATE */}
        {!isLoading && error && (
          <ErrorState
            type="server"
            message={error}
            onRetry={() => fetchHistory()}
          />
        )}

        {/* EMPTY STATE */}
        {!isLoading && !error && reports.length === 0 && (
          <EmptyState
            title="No Research Yet"
            description="Start your first AI-powered research, and your generated reports will appear here."
            actionLabel="Start First Research"
            onAction={() => router.push("/")}
          />
        )}

        {/* EMPTY SEARCH RESULTS */}
        {!isLoading && !error && reports.length > 0 && filteredReports.length === 0 && (
          <div className="text-center py-16">
            <Search size={40} className="text-slate-300 mx-auto mb-4 animate-bounce" />
            <h3 className="font-bold text-slate-600 mb-2 text-sm">No reports match your filters</h3>
            <button
              type="button"
              onClick={() => {
                setSearchQuery("")
                setStatusFilter("all")
              }}
              className="text-sm font-semibold text-blue-600 hover:underline"
            >
              Clear filters
            </button>
          </div>
        )}

        {/* REPORT CARDS GRID */}
        {!isLoading && !error && filteredReports.length > 0 && (
          <div className="space-y-8">
            <AnimatePresence mode="popLayout">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {filteredReports.map((report, index) => (
                  <ReportHistoryCard
                    key={report.report_id}
                    report={report}
                    onDelete={handleDeleteClick}
                    index={index}
                  />
                ))}
              </div>
            </AnimatePresence>

            {/* LOAD MORE BUTTON */}
            {reports.length >= limit && (
              <div className="flex justify-center pt-4">
                <button
                  type="button"
                  onClick={handleLoadMore}
                  className="flex items-center gap-2 px-6 py-3 bg-white hover:bg-slate-50 border border-slate-200 text-slate-700 font-semibold rounded-2xl text-sm transition-all shadow-sm"
                >
                  <RefreshCw size={14} className={clsx(isLoading && "animate-spin")} />
                  <span>Load More Reports</span>
                </button>
              </div>
            )}
          </div>
        )}

        {/* RESULTS COUNT FOOTER */}
        {!isLoading && !error && filteredReports.length > 0 && (searchQuery || statusFilter !== "all") && (
          <p className="text-center text-xs font-bold text-slate-400 mt-8 uppercase tracking-wider">
            Showing {filteredReports.length} of {reports.length} reports
          </p>
        )}
      </div>

      {/* DELETE CONFIRMATION MODAL */}
      <DeleteConfirmModal
        isOpen={deleteModal.isOpen}
        topic={deleteModal.topic}
        onConfirm={handleDeleteConfirm}
        onCancel={() => setDeleteModal({ isOpen: false, reportId: null, topic: "" })}
        isDeleting={isDeleting}
      />
    </PageTransition>
  )
}
