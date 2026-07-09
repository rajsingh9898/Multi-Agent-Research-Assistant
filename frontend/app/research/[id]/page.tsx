"use client"

import React, { useState, useEffect, useRef, useCallback } from "react"
import { useParams, useRouter } from "next/navigation"
import Link from "next/link"
import { motion, AnimatePresence } from "framer-motion"
import { clsx } from "clsx"

import PageTransition from "../../../components/ui/PageTransition"
import { showSuccess, showError, RESEARCH_TOASTS } from "../../../components/ui/Toast"

import {
  Brain,
  CheckCircle,
  Clock,
  Zap,
  FileText,
  Eye,
  Loader2,
  AlertTriangle,
  RefreshCw,
  Activity,
  ArrowLeft,
  XCircle,
} from "lucide-react"

import { onAuthChange } from "../../../lib/firebase"
import { researchAPI } from "../../../lib/api"
import { ResearchWebSocket, type WSEvent } from "../../../lib/websocket"
import AgentCard, { type AgentInfo, type AgentStatus } from "../../../components/AgentCard"
import ThinkingLog, { type ThinkingLogItem } from "../../../components/ThinkingLog"

// --- TYPES DEFINITIONS ---

interface ActivityLogItem {
  id: string
  agent: string
  message: string
  timestamp: number
  type: "info" | "success" | "error" | "thinking"
}

// --- INITIAL CONSTANTS ---

const INITIAL_AGENTS: AgentInfo[] = [
  {
    id: "orchestrator",
    name: "Orchestrator",
    emoji: "🧠",
    description: "Plans research questions",
    status: "waiting",
    message: "",
    startedAt: null,
    completedAt: null,
  },
  {
    id: "search_agent",
    name: "Search Agent",
    emoji: "🔍",
    description: "Finds web sources",
    status: "waiting",
    message: "",
    startedAt: null,
    completedAt: null,
  },
  {
    id: "summary_agent",
    name: "Summary Agent",
    emoji: "📝",
    description: "Reads and summarizes sources",
    status: "waiting",
    message: "",
    startedAt: null,
    completedAt: null,
  },
  {
    id: "factcheck_agent",
    name: "Fact Checker",
    emoji: "✅",
    description: "Verifies every claim",
    status: "waiting",
    message: "",
    startedAt: null,
    completedAt: null,
  },
  {
    id: "writer_agent",
    name: "Writer Agent",
    emoji: "✍️",
    description: "Writes the report",
    status: "waiting",
    message: "",
    startedAt: null,
    completedAt: null,
  },
  {
    id: "followup_agent",
    name: "Follow-Up Agent",
    emoji: "🔮",
    description: "Suggests next questions",
    status: "waiting",
    message: "",
    startedAt: null,
    completedAt: null,
  },
]

// Spinner loader helper component
const Spinner = ({ className = "h-5 w-5" }: { className?: string }) => (
  <div className={`animate-spin rounded-full border-2 border-current border-t-transparent ${className}`} />
)

// --- COMPONENT ROOT ---

export default function ResearchActivityPage() {
  const params = useParams()
  const router = useRouter()
  const reportId = params.id as string

  // State Management variables
  const [agents, setAgents] = useState<AgentInfo[]>(INITIAL_AGENTS)
  const [activityLog, setActivityLog] = useState<ActivityLogItem[]>([])
  const [thinkingLogs, setThinkingLogs] = useState<ThinkingLogItem[]>([])
  const [wsStatus, setWsStatus] = useState<"connecting" | "connected" | "disconnected" | "reconnecting">("connecting")
  const [progress, setProgress] = useState(0)
  const [isThinkingOpen, setIsThinkingOpen] = useState(false)
  const [topic, setTopic] = useState("")
  const [reportReady, setReportReady] = useState(false)
  const [elapsedTime, setElapsedTime] = useState(0)
  const [startTime] = useState(Date.now())
  const [authLoading, setAuthLoading] = useState(true)
  const [authError, setAuthError] = useState<string | null>(null)
  
  // Edge cases states variables
  const [reportNotFound, setReportNotFound] = useState(false)
  const [pipelineFailed, setPipelineFailed] = useState(false)
  const [pipelineFailedMessage, setPipelineFailedMessage] = useState("")
  const [apiChecking, setApiChecking] = useState(true)
  const [wsTimeoutError, setWsTimeoutError] = useState(false)
  const [reconnectFailed, setReconnectFailed] = useState(false)

  // Refs configs
  const wsRef = useRef<ResearchWebSocket | null>(null)
  const activityEndRef = useRef<HTMLDivElement>(null)
  const timerRef = useRef<NodeJS.Timeout | null>(null)
  const wsTimerRef = useRef<NodeJS.Timeout | null>(null)
  const isRedirectingRef = useRef(false)

  // --- ACTIONS HELPERS ---

  const addActivityLog = useCallback((agent: string, message: string, type: "info" | "success" | "error" | "thinking") => {
    setActivityLog((prev) => {
      // Deduplicate replayed logs matching exact message and agent
      const isDuplicate = prev.some((log) => log.agent === agent && log.message === message)
      if (isDuplicate) return prev

      return [
        ...prev,
        {
          id: `${Date.now()}-${Math.random()}`,
          agent,
          message,
          timestamp: Date.now(),
          type,
        },
      ]
    })
  }, [])

  const updateAgent = useCallback((agentId: string, updates: Partial<AgentInfo>) => {
    setAgents((prev) =>
      prev.map((a) => (a.id === agentId ? { ...a, ...updates } : a))
    )
  }, [])

  const formatTime = (ms: number): string => {
    const seconds = Math.floor(ms / 1000)
    if (seconds < 60) return `${seconds}s`
    const minutes = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${minutes}m ${secs}s`
  }

  // --- WEB SOCKET EVENT HANDLER ---

  const handleWSEvent = useCallback((event: WSEvent) => {
    // Clear ws connecting timeout
    if (wsTimerRef.current) {
      clearTimeout(wsTimerRef.current)
      setWsTimeoutError(false)
    }

    switch (event.event) {
      case "connected":
        setWsStatus("connected")
        addActivityLog("system", "Connected to research pipeline stream", "info")
        break

      case "research_start":
        addActivityLog("system", event.message, "info")
        if (event.data?.topic) {
          setTopic(event.data.topic)
        }
        break

      case "agent_start":
        updateAgent(event.agent, {
          status: "running",
          message: event.message,
          startedAt: event.timestamp,
        })
        addActivityLog(event.agent, event.message, "info")
        break

      case "agent_update":
        updateAgent(event.agent, {
          message: event.message,
        })
        addActivityLog(event.agent, event.message, "info")
        break

      case "agent_done":
        updateAgent(event.agent, {
          status: "done",
          message: event.message,
          completedAt: event.timestamp,
        })
        addActivityLog(event.agent, event.message, "success")
        
        // Dynamic progress calculation from agent complete states
        setAgents((prev) => {
          const updated = prev.map((a) =>
            a.id === event.agent ? { ...a, status: "done" as AgentStatus, completedAt: event.timestamp } : a
          )
          const doneCount = updated.filter((a) => a.status === "done").length
          setProgress((doneCount / 6) * 100)
          return updated
        })
        break

      case "thinking_log":
        const thought = event.data?.thought || event.message
        setThinkingLogs((prev) => {
          // Avoid duplicate thoughts
          const isDuplicate = prev.some((log) => log.agent === event.agent && log.thought === thought)
          if (isDuplicate) return prev

          return [
            ...prev,
            {
              agent: event.agent,
              thought,
              timestamp: event.timestamp,
            },
          ]
        })
        break

      case "error":
        updateAgent(event.agent, {
          status: "failed",
          message: event.message,
        })
        addActivityLog(event.agent, event.message, "error")
        setPipelineFailed(true)
        setPipelineFailedMessage(event.message)
        showError(`Agent Error: ${event.message}`)
        break

      case "report_ready":
        if (isRedirectingRef.current) return
        isRedirectingRef.current = true

        setProgress(100)
        setReportReady(true)
        addActivityLog("system", "Research report complete! Redirecting...", "success")
        showSuccess(RESEARCH_TOASTS.RESEARCH_COMPLETE)

        // Give the user a little more time to click the new "View Report" button
        setTimeout(() => {
          router.push(`/report/${reportId}`)
        }, 5000)
        break

      default:
        break
    }
  }, [reportId, addActivityLog, updateAgent, router])

  // --- EFFECT: AUTH VALIDATION ---

  useEffect(() => {
    const unsubscribe = onAuthChange((currentUser) => {
      setAuthLoading(false)
      if (!currentUser) {
        setAuthError("Unauthorized user. Redirecting to sign in...")
        showError(RESEARCH_TOASTS.SIGNIN_REQUIRED)
        setTimeout(() => {
          router.push("/")
        }, 2000)
      }
    })
    return () => unsubscribe()
  }, [router])

  // --- EFFECT: API RECOVERY & STATUS CHECKS ---

  useEffect(() => {
    if (authLoading || authError) return

    const verifyReportStatus = async () => {
      try {
        setApiChecking(true)
        const report = await researchAPI.getReport(reportId)
        
        if (report) {
          if (report.topic) {
            setTopic(report.topic)
          }

          // Edge Case 1: Already complete
          if (report.status === "done") {
            setProgress(100)
            setReportReady(true)
            showSuccess("Report is already generated! Redirecting...")
            setTimeout(() => {
              router.push(`/report/${reportId}`)
            }, 1800)
            return
          }

          // Edge Case 3: Already failed
          if (report.status === "failed") {
            setPipelineFailed(true)
            setPipelineFailedMessage("This research pipeline ended with a failure.")
            return
          }
        }
      } catch (err: any) {
        // Edge Case 2: NotFound (404)
        if (err.message && err.message.includes("404")) {
          setReportNotFound(true)
        } else {
          console.warn("API check warning (silently proceeding to ws):", err)
        }
      } finally {
        setApiChecking(false)
      }
    }

    verifyReportStatus()
  }, [reportId, authLoading, authError, router])

  // --- EFFECT: SOCKET CONNECTION SETUP ---

  useEffect(() => {
    // Only connect when auth is confirmed and report checks out
    if (authLoading || authError || apiChecking || reportNotFound || pipelineFailed || reportReady) return

     const ws = new ResearchWebSocket(
      reportId,
      handleWSEvent,
      () => setWsStatus("connected"),
      () => setWsStatus("reconnecting"),
      (err) => {
        setWsStatus("disconnected")
        if (err && (err.includes("closed") || err.includes("Maximum") || err.includes("reconnection"))) {
          setReconnectFailed(true)
        }
        showError(err)
      }
    )

    ws.connect()
    wsRef.current = ws

    // Elapsed timer runner
    timerRef.current = setInterval(() => {
      setElapsedTime(Date.now() - startTime)
    }, 1000)

    // Edge Case 4: WS Timeout threshold (10 seconds connecting fallback)
    wsTimerRef.current = setTimeout(() => {
      if (wsRef.current && !wsRef.current.isConnected()) {
        setWsTimeoutError(true)
        showError("WebSocket connection is taking longer than usual.")
      }
    }, 10000)

    return () => {
      ws.disconnect()
      if (timerRef.current) clearInterval(timerRef.current)
      if (wsTimerRef.current) clearTimeout(wsTimerRef.current)
    }
  }, [reportId, handleWSEvent, startTime, authLoading, authError, apiChecking, reportNotFound, pipelineFailed, reportReady])

  // --- EFFECT: POLLING FALLBACK AFTER 5 WS RECONNECT ATTEMPTS ---
  useEffect(() => {
    if (!reconnectFailed || reportReady || pipelineFailed) return

    const pollInterval = setInterval(async () => {
      try {
        const report = await researchAPI.getReport(reportId)
        if (report) {
          if (report.status === "done") {
            clearInterval(pollInterval)
            setProgress(100)
            setReportReady(true)
            showSuccess("Research completed! (Fetched via backup polling)")
            router.push(`/report/${reportId}`)
          } else if (report.status === "failed") {
            clearInterval(pollInterval)
            setPipelineFailed(true)
            setPipelineFailedMessage("The research pipeline failed.")
          }
        }
      } catch (err) {
        console.warn("Polling fallback failed:", err)
      }
    }, 10000)

    return () => clearInterval(pollInterval)
  }, [reconnectFailed, reportId, reportReady, pipelineFailed, router])

  // --- EFFECT: LOCALSTORAGE PERSISTENCE (ACTIVE TAB SENDS STATUS) ---
  useEffect(() => {
    if (wsStatus !== "connected" || apiChecking || reportNotFound || !reportId) return
    const stateData = {
      agents,
      activityLog,
      thinkingLogs,
      progress,
      topic,
      reportReady,
      pipelineFailed,
      pipelineFailedMessage
    }
    localStorage.setItem(`research_state_${reportId}`, JSON.stringify(stateData))
  }, [reportId, wsStatus, agents, activityLog, thinkingLogs, progress, topic, reportReady, pipelineFailed, pipelineFailedMessage, apiChecking, reportNotFound])

  // --- EFFECT: LOCALSTORAGE SYNC (INACTIVE TAB RECEIVES STATUS) ---
  useEffect(() => {
    if (!reportId || wsStatus === "connected") return

    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === `research_state_${reportId}` && e.newValue) {
        try {
          const parsed = JSON.parse(e.newValue)
          setAgents(parsed.agents)
          setActivityLog(parsed.activityLog)
          setThinkingLogs(parsed.thinkingLogs)
          setProgress(parsed.progress)
          setTopic(parsed.topic)
          setReportReady(parsed.reportReady)
          setPipelineFailed(parsed.pipelineFailed)
          setPipelineFailedMessage(parsed.pipelineFailedMessage)
        } catch (err) {
          console.error("Error parsing synced state from storage:", err)
        }
      }
    }

    window.addEventListener("storage", handleStorageChange)
    
    // Also load initial state from localstorage on mount/reconnect lost
    const existingState = localStorage.getItem(`research_state_${reportId}`)
    if (existingState) {
      try {
        const parsed = JSON.parse(existingState)
        setAgents(parsed.agents)
        setActivityLog(parsed.activityLog)
        setThinkingLogs(parsed.thinkingLogs)
        setProgress(parsed.progress)
        setTopic(parsed.topic)
        setReportReady(parsed.reportReady)
        setPipelineFailed(parsed.pipelineFailed)
        setPipelineFailedMessage(parsed.pipelineFailedMessage)
      } catch (err) {
        // Ignore parsing errors
      }
    }

    return () => window.removeEventListener("storage", handleStorageChange)
  }, [reportId, wsStatus])


  // --- EFFECT: AUTO-SCROLL LOGS ---

  useEffect(() => {
    activityEndRef.current?.scrollIntoView({
      behavior: "smooth",
    })
  }, [activityLog])

  // --- RENDERS PATHS ---

  // RENDER A: AUTHENTICATION ENFORCED REDIRECTS
  if (authLoading || authError) {
    return (
      <PageTransition className="min-h-screen bg-slate-50 flex flex-col items-center justify-center p-6 text-center">
        <Spinner className="h-8 w-8 text-blue-600 mb-4" />
        <p className="text-sm font-semibold text-slate-500">
          {authError || "Validating secure session credentials..."}
        </p>
      </PageTransition>
    )
  }

  // RENDER B: LOADING INITIAL REPORT STATUS
  if (apiChecking) {
    return (
      <PageTransition className="min-h-screen bg-slate-50 flex flex-col items-center justify-center p-6 text-center">
        <Spinner className="h-8 w-8 text-blue-600 mb-4" />
        <p className="text-sm font-semibold text-slate-500">Checking research progress state...</p>
      </PageTransition>
    )
  }

  // RENDER C: REPORT NOT FOUND (404)
  if (reportNotFound) {
    return (
      <PageTransition className="min-h-screen bg-slate-50 flex flex-col items-center justify-center p-6 text-center max-w-md mx-auto">
        <div className="h-16 w-16 bg-red-50 text-red-500 rounded-3xl flex items-center justify-center mb-6 border border-red-100 shadow-sm">
          <AlertTriangle size={30} />
        </div>
        <h2 className="text-2xl font-bold text-slate-900 mb-2">Research Report Not Found</h2>
        <p className="text-slate-500 text-sm mb-8 leading-relaxed">
          The requested report ID is invalid or does not exist in your research archives database.
        </p>
        <button
          type="button"
          onClick={() => router.push("/")}
          className="flex items-center justify-center gap-2 bg-slate-900 hover:bg-slate-800 text-white rounded-2xl px-6 py-3.5 font-semibold transition-all duration-200 w-full"
        >
          <ArrowLeft size={16} />
          <span>Return to Dashboard</span>
        </button>
      </PageTransition>
    )
  }

  // RENDER D: PIPELINE FAILURE (CRASH STATE)
  if (pipelineFailed) {
    return (
      <PageTransition className="min-h-screen bg-slate-50 flex flex-col items-center justify-center p-6 text-center max-w-md mx-auto">
        <div className="h-16 w-16 bg-red-50 text-red-500 rounded-3xl flex items-center justify-center mb-6 border border-red-100 shadow-sm animate-bounce">
          <XCircle size={30} />
        </div>
        <h2 className="text-2xl font-bold text-slate-900 mb-2">Research Pipeline Failed</h2>
        <p className="text-slate-500 text-sm mb-6 leading-relaxed">
          The multi-agent execution was interrupted due to an error. Reason:
        </p>
        <div className="bg-red-50/50 border border-red-200/50 rounded-2xl p-4 text-xs font-mono text-red-800 text-left mb-8 max-h-40 overflow-y-auto break-words leading-relaxed w-full">
          {pipelineFailedMessage || "Unexpected crash inside summary aggregator module."}
        </div>
        <button
          type="button"
          onClick={() => router.push("/")}
          className="flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-700 text-white rounded-2xl px-6 py-3.5 font-semibold transition-all duration-200 w-full shadow-md shadow-blue-500/10"
        >
          <RefreshCw size={16} />
          <span>Create New Report</span>
        </button>
      </PageTransition>
    )
  }

  // RENDER E: ACTIVE REAL-TIME MONITOR DASHBOARD
  return (
    <PageTransition className="min-h-screen bg-slate-50 flex flex-col">
      {/* Sticky dashboard header info */}
      <header className="bg-white border-b border-slate-200/60 sticky top-[69px] z-30 transition-all duration-200">
        <div className="max-w-4xl mx-auto px-4 py-4 flex items-center justify-between gap-4">
          {/* Topic header details */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2.5">
              <div className="h-6 w-6 rounded-lg bg-blue-50 border border-blue-100 text-blue-600 flex items-center justify-center flex-shrink-0 animate-pulse">
                <Activity size={13} />
              </div>
              <h1 className="font-extrabold text-slate-900 text-sm sm:text-base truncate leading-snug">
                {topic || "Initializing pipeline agents..."}
              </h1>
            </div>
            <p className="text-[10px] text-slate-400 font-bold tracking-wider mt-0.5 uppercase hidden md:block">
              ID: {reportId}
            </p>
          </div>

          {/* Time & Telemetry Status badges */}
          <div className="flex items-center gap-3 flex-shrink-0">
            <span className="text-xs sm:text-sm font-bold text-slate-500 bg-slate-100/80 px-2.5 py-1 rounded-lg border border-slate-200/40">
              ⏱️ {formatTime(elapsedTime)}
            </span>

            {/* Socket connection badge */}
            <div
              className={clsx(
                "flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold border transition-all duration-200",
                wsStatus === "connected"
                  ? "bg-green-50 border-green-200 text-green-700"
                  : wsStatus === "reconnecting"
                  ? "bg-amber-50 border-amber-200 text-amber-700"
                  : "bg-red-50 border-red-200 text-red-700"
              )}
            >
              <span
                className={clsx(
                  "w-1.5 h-1.5 rounded-full shrink-0",
                  wsStatus === "connected"
                    ? "bg-green-500 animate-pulse"
                    : wsStatus === "reconnecting"
                    ? "bg-amber-500 animate-pulse"
                    : "bg-red-500"
                )}
              />
              <span className="hidden sm:inline">
                {wsStatus === "connected" && "Live Connection"}
                {wsStatus === "reconnecting" && "Reconnecting..."}
                {wsStatus === "disconnected" && "Disconnected"}
                {wsStatus === "connecting" && "Connecting..."}
              </span>
              <span className="sm:hidden capitalize">{wsStatus}</span>
            </div>
          </div>
        </div>
      </header>

      {/* Main dashboard content */}
      <div className="max-w-4xl mx-auto w-full px-4 py-8 flex-1 flex flex-col gap-6">
        
        {/* WS CONNECTION TIMEOUT Edge Case alert */}
        <AnimatePresence>
          {wsTimeoutError && wsStatus === "connecting" && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="flex items-start gap-3 bg-amber-50 border border-amber-200 rounded-2xl p-4 text-amber-800 text-xs leading-normal shadow-sm"
            >
              <AlertTriangle className="text-amber-500 h-5 w-5 mt-0.5 shrink-0 animate-bounce" />
              <div>
                <span className="font-bold block mb-0.5">Slow connection detected</span>
                <span>The system is still trying to bind WebSocket channels. You can wait or attempt to reload the dashboard manually.</span>
                <button
                  type="button"
                  onClick={() => window.location.reload()}
                  className="mt-2.5 flex items-center gap-1.5 bg-amber-600 hover:bg-amber-700 text-white rounded-lg px-3 py-1.5 font-bold transition-all duration-200"
                >
                  <RefreshCw size={12} />
                  <span>Reload Page</span>
                </button>
              </div>
            </motion.div>
          )}

          {reconnectFailed && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="flex items-start gap-3 bg-red-50 border border-red-200 rounded-2xl p-4 text-red-800 text-xs leading-normal shadow-sm"
            >
              <AlertTriangle className="text-red-500 h-5 w-5 mt-0.5 shrink-0 animate-bounce" />
              <div>
                <span className="font-bold block mb-0.5">Connection lost. Refresh to retry.</span>
                <span>The real-time connection to the research agents was lost after multiple attempts.</span>
                <button
                  type="button"
                  onClick={() => window.location.reload()}
                  className="mt-2.5 flex items-center gap-1.5 bg-red-600 hover:bg-red-700 text-white rounded-lg px-3 py-1.5 font-bold transition-all duration-200"
                >
                  <RefreshCw size={12} />
                  <span>Refresh Connection</span>
                </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* PROGRESS BAR CARD */}
        <div className="bg-white rounded-3xl border border-slate-200/80 p-6 shadow-sm shadow-slate-100/50">
          <div className="flex items-center justify-between mb-3.5">
            <span className="text-sm font-bold text-slate-700">Multi-Agent Aggregation Progress</span>
            <span className="text-base font-extrabold text-slate-900">{Math.round(progress)}%</span>
          </div>

          <div className="w-full bg-slate-100 rounded-full h-3.5 overflow-hidden">
            <motion.div
              className={clsx(
                "h-full rounded-full transition-all duration-500",
                progress < 34 ? "bg-orange-500" : progress < 67 ? "bg-amber-500" : progress < 100 ? "bg-blue-500" : "bg-green-500"
              )}
              initial={{ width: "0%" }}
              animate={{ width: `${progress}%` }}
              transition={{ duration: 0.8, ease: "easeOut" }}
            />
          </div>

          <div className="flex justify-between mt-3 text-xs font-bold text-slate-400">
            <span>Query Started</span>
            <span className="text-slate-500">
              {agents.filter((a) => a.status === "done").length} / 6 agents completed
            </span>
            <span>Report Written</span>
          </div>
        </div>

        {/* AGENTS GRID */}
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
          {agents.map((agent) => (
            <AgentCard key={agent.id} agent={agent} isActive={agent.status === "running"} />
          ))}
        </div>

        {/* REPORT READY REDIRECT SCREEN */}
        <AnimatePresence>
          {reportReady && (
            <motion.div
              initial={{ opacity: 0, scale: 0.96 }}
              animate={{ opacity: 1, scale: 1 }}
              className="bg-green-600 text-white rounded-3xl p-6 sm:p-8 text-center shadow-xl shadow-green-100 border border-green-500"
            >
              <CheckCircle size={44} className="mx-auto mb-3.5 animate-pulse" />
              <h2 className="text-2xl font-extrabold mb-1">Research Completed!</h2>
              <p className="text-green-100 text-sm font-semibold mb-6">
                Creating file compilation. Redirecting to your reader page...
              </p>
              <div className="flex justify-center items-center gap-3">
                <Link
                  href={`/report/${reportId}`}
                  className="px-5 py-3 bg-white text-green-700 hover:bg-green-50 rounded-xl text-xs sm:text-sm font-bold transition-all shadow-md focus:outline-none"
                >
                  View Report
                </Link>
                <div className="flex items-center justify-center bg-white/20 p-2.5 rounded-full shrink-0">
                  <Spinner className="h-6 w-6" />
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* ACTIVITY LOG TERMINAL VIEW */}
        <div className="bg-white rounded-3xl border border-slate-200/80 shadow-sm shadow-slate-100/50 overflow-hidden">
          {/* Log header */}
          <div className="flex items-center gap-2.5 px-5 py-4 border-b border-slate-100 bg-slate-50/50">
            <FileText size={16} className="text-slate-400" />
            <h3 className="text-sm font-bold text-slate-700">Live Process Activity Feed</h3>
            <span className="text-[10px] bg-slate-200 text-slate-500 px-2 py-0.5 rounded-full font-bold border border-slate-300/20 ml-auto">
              {activityLog.length} logs
            </span>
          </div>

          {/* Logs feed list */}
          <div className="max-h-72 overflow-y-auto p-5 space-y-3 font-mono text-[11px] sm:text-xs">
            {activityLog.length === 0 ? (
              <div className="text-center py-12">
                <Loader2 size={24} className="animate-spin text-slate-300 mx-auto mb-3.5" />
                <p className="text-xs text-slate-400 font-semibold font-sans">
                  Booting background orchestrator pipeline...
                </p>
              </div>
            ) : (
              activityLog.map((item) => (
                <motion.div
                  key={item.id}
                  initial={{ opacity: 0, x: -6 }}
                  animate={{ opacity: 1, x: 0 }}
                  className="flex items-start gap-3"
                >
                  {/* Timestamp */}
                  <span className="text-[10px] sm:text-xs text-slate-400 font-semibold font-mono shrink-0 mt-0.5">
                    {new Date(item.timestamp).toLocaleTimeString("en", {
                      hour: "2-digit",
                      minute: "2-digit",
                      second: "2-digit",
                      hour12: false,
                    })}
                  </span>

                  {/* Log dot status */}
                  <div
                    className={clsx(
                      "w-1.5 h-1.5 rounded-full shrink-0 mt-1.5 shadow-sm",
                      item.type === "success"
                        ? "bg-green-500 shadow-green-200"
                        : item.type === "error"
                        ? "bg-red-500 shadow-red-200"
                        : item.type === "thinking"
                        ? "bg-purple-500 shadow-purple-200 animate-pulse"
                        : "bg-blue-400 shadow-blue-200"
                    )}
                  />

                  {/* Msg display */}
                  <div className="flex-1 min-w-0 leading-relaxed text-slate-700 font-sans">
                    <span className="font-bold text-slate-500 mr-1.5">
                      {item.agent !== "system" ? `[${item.agent.replace("_agent", "").replace("_", " ")}]` : "[system]"}
                    </span>
                    <span>{item.message}</span>
                  </div>
                </motion.div>
              ))
            )}
            {/* End anchor point */}
            <div ref={activityEndRef} />
          </div>
        </div>

        {/* THINKING LOG PANEL (Feature 4) */}
        <ThinkingLog
          thoughts={thinkingLogs}
          isOpen={isThinkingOpen}
          onToggle={() => setIsThinkingOpen((prev) => !prev)}
        />

        {/* Dashboard Footer info */}
        <p className="text-center text-xs text-slate-400 mt-4 leading-normal font-semibold">
          Don&apos;t close this page. The multi-agent pipeline is active. You can safely return later from your History dashboard.
        </p>
      </div>
    </PageTransition>
  )
}
