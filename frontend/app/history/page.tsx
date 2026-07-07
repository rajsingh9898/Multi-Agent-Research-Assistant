"use client"

import React, { useState, useEffect } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { motion, AnimatePresence } from "framer-motion"
import { toast } from "react-hot-toast"
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
        toast.error("Please sign in to view history")
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

  const fetchHistory = async () => {
    setIsLoading(true)
    setError(null)
    try {
      const response = await researchAPI.getHistory()
      const reportsList = response.reports || []
      setReports(reportsList)
      setFilteredReports(reportsList)
      calculateStats(reportsList)
    } catch (err: any) {
      setError(err.message || "Failed to load report history")
      toast.error("Could not load reports")
    } finally {
      setIsLoading(false)
    }
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

      toast.success("Report deleted successfully")
      setDeleteModal({ isOpen: false, reportId: null, topic: "" })
    } catch (err: any) {
      toast.error("Delete failed. Please try again.")
    } finally {
      setIsDeleting(false)
    }
  }

  // --- RENDER SECTIONS ---

  return (
    <div className="min-h-screen bg-slate-50">
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
              <div key={i} className="bg-white rounded-xl border border-slate-200 p-5">
                <div className="flex gap-3 mb-3">
                  <div className="w-2.5 h-2.5 rounded-full bg-slate-200 animate-pulse mt-1.5" />
                  <div className="flex-1">
                    <div className="h-4 bg-slate-200 rounded animate-pulse mb-2 w-3/4" />
                    <div className="h-3 bg-slate-100 rounded animate-pulse w-1/3" />
                  </div>
                </div>
                <div className="h-1.5 bg-slate-100 rounded-full animate-pulse mb-4" />
                <div className="flex gap-2">
                  <div className="h-8 bg-slate-100 rounded-lg animate-pulse flex-1" />
                  <div className="h-8 w-8 bg-slate-100 rounded-lg animate-pulse" />
                </div>
              </div>
            ))}
          </div>
        )}

        {/* ERROR STATE */}
        {!isLoading && error && (
          <div className="text-center py-16">
            <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4 border border-red-200">
              <FileX size={32} className="text-red-400" />
            </div>
            <h3 className="text-lg font-bold text-slate-700 mb-2">Could Not Load History</h3>
            <p className="text-slate-500 text-sm mb-6 leading-relaxed max-w-sm mx-auto">{error}</p>
            <button
              type="button"
              onClick={fetchHistory}
              className="flex items-center gap-2 mx-auto px-5 py-3 bg-blue-600 text-white rounded-2xl text-sm font-semibold hover:bg-blue-700 transition-colors shadow-md shadow-blue-500/10"
            >
              <RefreshCw size={14} />
              <span>Try Again</span>
            </button>
          </div>
        )}

        {/* EMPTY STATE */}
        {!isLoading && !error && reports.length === 0 && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="text-center py-16"
          >
            <div className="w-24 h-24 bg-blue-50 rounded-full flex items-center justify-center mx-auto mb-6 border border-blue-100">
              <History size={48} className="text-blue-400" />
            </div>
            <h3 className="text-xl font-extrabold text-slate-800 mb-2">No Research Yet</h3>
            <p className="text-slate-500 mb-8 max-w-xs mx-auto text-sm leading-relaxed font-semibold">
              Start your first AI-powered research, and your generated reports will appear here.
            </p>
            <Link
              href="/"
              className="inline-flex items-center gap-2 px-6 py-3.5 bg-blue-600 hover:bg-blue-700 text-white rounded-2xl text-sm font-semibold transition-all shadow-md shadow-blue-500/10"
            >
              <Plus size={18} />
              <span>Start First Research</span>
            </Link>
          </motion.div>
        )}

        {/* EMPTY SEARCH RESULTS */}
        {!isLoading && !error && reports.length > 0 && filteredReports.length === 0 && (
          <div className="text-center py-16">
            <Search size={40} className="text-slate-300 mx-auto mb-4" />
            <h3 className="font-bold text-slate-650 mb-2 text-sm">No reports match your filters</h3>
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
    </div>
  )
}
