"use client"

import React, { useState, useEffect, Suspense } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { motion, AnimatePresence } from "framer-motion"
import { type User } from "firebase/auth"
import { clsx } from "clsx"

import PageTransition from "../components/ui/PageTransition"
import { showSuccess, showError, RESEARCH_TOASTS } from "../components/ui/Toast"

import {
  Search,
  Zap,
  BookOpen,
  Globe,
  ArrowRight,
  Clock,
  FileText,
  CheckCircle,
  Brain,
  Shield,
  Languages,
  ChevronRight,
  Sparkles,
  History,
  AlertCircle,
} from "lucide-react"

import { onAuthChange, signInWithGoogle } from "../lib/firebase"
import { researchAPI, type HistoryItem } from "../lib/api"
import LanguageSelector from "../components/LanguageSelector"

// --- CONSTANTS ---

const depths = [
  {
    key: "quick",
    label: "Quick",
    icon: "⚡",
    questions: "3 questions",
    time: "~25 seconds",
    sources: "8-10 sources",
    description: "Fast overview",
    color: "green",
  },
  {
    key: "deep",
    label: "Deep",
    icon: "🔍",
    questions: "4 questions",
    time: "~45 seconds",
    sources: "12-16 sources",
    description: "Comprehensive",
    color: "blue",
  },
  {
    key: "expert",
    label: "Expert",
    icon: "🎓",
    questions: "6 questions",
    time: "~80 seconds",
    sources: "18-24 sources",
    description: "In-depth analysis",
    color: "purple",
  },
]

const exampleTopics = [
  "Impact of AI on Healthcare",
  "Climate change solutions 2025",
  "Future of electric vehicles",
  "Blockchain in finance",
  "Benefits of meditation",
]

// --- SUB-COMPONENTS ---

interface DepthCardProps {
  depth: "quick" | "deep" | "expert"
  label: string
  icon: string
  questions: string
  time: string
  sources: string
  description: string
  color: string
  selected: boolean
  onClick: () => void
}

function DepthCard({
  depth,
  label,
  icon,
  questions,
  time,
  sources,
  description,
  color,
  selected,
  onClick,
}: DepthCardProps) {
  // Border & bg classes based on color and selection state
  const selectedClasses = {
    green: "border-green-500 bg-green-50/30 text-green-950 shadow-green-100",
    blue: "border-blue-500 bg-blue-50/30 text-blue-950 shadow-blue-100",
    purple: "border-purple-500 bg-purple-50/30 text-purple-950 shadow-purple-100",
  }[color]

  const hoverBorderClasses = {
    green: "hover:border-green-300",
    blue: "hover:border-blue-300",
    purple: "hover:border-purple-300",
  }[color]

  return (
    <motion.button
      type="button"
      onClick={onClick}
      whileHover={{ scale: 1.02, y: -2 }}
      whileTap={{ scale: 0.98 }}
      className={`flex flex-col items-start p-3 sm:p-4 rounded-xl border-2 text-left transition-all duration-200 shadow-sm outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-blue-500 ${
        selected
          ? `${selectedClasses} ring-2 ring-offset-1 ring-opacity-50`
          : `border-slate-200 bg-white text-slate-800 ${hoverBorderClasses}`
      }`}
    >
      <div className="flex items-center justify-between w-full mb-1">
        <span className="text-xl">{icon}</span>
        <span
          className={`text-xs font-semibold px-2 py-0.5 rounded-full ${
            selected
              ? {
                  green: "bg-green-100/70 text-green-800",
                  blue: "bg-blue-100/70 text-blue-800",
                  purple: "bg-purple-100/70 text-purple-800",
                }[color]
              : "bg-slate-100 text-slate-500"
          }`}
        >
          {label}
        </span>
      </div>
      <span className="font-bold text-sm leading-snug truncate w-full">{description}</span>
      <span className="text-xs text-slate-500 mt-2 flex items-center gap-1">
        <Clock size={10} /> {time}
      </span>
      <span className="text-[11px] text-slate-400 mt-0.5 font-medium">
        {questions} • {sources}
      </span>
    </motion.button>
  )
}

function FeatureCard({
  icon,
  title,
  description,
}: {
  icon: React.ReactNode
  title: string
  description: string
}) {
  return (
    <motion.div
      whileHover={{ y: -4, boxShadow: "0 10px 15px -3px rgba(0, 0, 0, 0.05)" }}
      className="flex flex-col items-center p-5 rounded-2xl border border-slate-200/60 bg-white text-center shadow-sm transition-all duration-300"
    >
      <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-slate-50 shadow-inner">
        {icon}
      </div>
      <h4 className="font-bold text-slate-800 text-sm mb-1">{title}</h4>
      <p className="text-xs text-slate-500 leading-relaxed">{description}</p>
    </motion.div>
  )
}

function ExampleTopicChip({ topic, onClick }: { topic: string; onClick: (t: string) => void }) {
  return (
    <button
      type="button"
      onClick={() => onClick(topic)}
      className="inline-flex items-center rounded-lg bg-slate-100 hover:bg-blue-50 hover:text-blue-700 px-3 py-1.5 text-xs font-semibold text-slate-600 transition-all duration-200 border border-transparent hover:border-blue-100"
    >
      {topic}
    </button>
  )
}

const Spinner = ({ className = "h-5 w-5" }: { className?: string }) => (
  <div className={`animate-spin rounded-full border-2 border-current border-t-transparent ${className}`} />
)

// --- MAIN HOME COMPONENT ---

function Home() {
  const router = useRouter()
  const searchParams = useSearchParams()

  // State Management
  const [topic, setTopic] = useState("")
  const [depth, setDepth] = useState<string>("deep")
  const [language, setLanguage] = useState<string>("english")
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [user, setUser] = useState<User | null>(null)
  const [authLoading, setAuthLoading] = useState(true)
  const [charCount, setCharCount] = useState(0)
  const [recentReports, setRecentReports] = useState<HistoryItem[]>([])

  // Load topic from URL search param if present
  useEffect(() => {
    const topicParam = searchParams.get("topic")
    if (topicParam) {
      setTopic(decodeURIComponent(topicParam))
    }
  }, [searchParams])

  // Auth synchronization listener
  useEffect(() => {
    const unsubscribe = onAuthChange((currentUser) => {
      setUser(currentUser)
      setAuthLoading(false)
      if (currentUser) {
        fetchRecentReports()
      } else {
        setRecentReports([])
      }
    })
    return () => unsubscribe()
  }, [])

  // Character counter observer
  useEffect(() => {
    setCharCount(topic.length)
  }, [topic])

  const fetchRecentReports = async () => {
    try {
      const response = await researchAPI.getHistory()
      if (response && response.reports) {
        setRecentReports(response.reports.slice(0, 3))
      }
    } catch (err) {
      console.error("Silently bypassing failed reports fetch:", err)
    }
  }

  const handleTopicChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    if (e.target.value.length <= 500) {
      setTopic(e.target.value)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
      e.preventDefault()
      handleSubmit(e)
    }
  }

  const handleSubmit = async (e: React.SyntheticEvent) => {
    e.preventDefault()

    // Offline Guard
    if (typeof window !== "undefined" && !navigator.onLine) {
      showError(RESEARCH_TOASTS.ERROR_NETWORK)
      return
    }

    // 1. Validations
    if (!topic.trim()) {
      showError("Please enter a research topic")
      return
    }
    if (topic.trim().length < 3) {
      showError("Topic query is too short (min 3 chars)")
      return
    }
    if (topic.length > 500) {
      showError("Topic too long (max 500 characters)")
      return
    }
    if (!user) {
      showError(RESEARCH_TOASTS.SIGNIN_REQUIRED)
      return
    }

    // 2. Submit pipeline trigger
    setIsLoading(true)
    setError(null)

    try {
      const result = await researchAPI.start(topic.trim(), depth, language)
      if (result && result.report_id) {
        showSuccess(RESEARCH_TOASTS.RESEARCH_STARTED)
        router.push(`/research/${result.report_id}`)
      } else {
        throw new Error("No report ID was returned by the server")
      }
    } catch (err: any) {
      const msg = err.message || RESEARCH_TOASTS.ERROR_GENERIC
      setError(msg)
      showError(msg)
    } finally {
      setIsLoading(false)
    }
  }

  // Formatting timestamp dates helper
  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return ""
    try {
      const date = new Date(dateStr)
      return date.toLocaleDateString(undefined, {
        month: "short",
        day: "numeric",
        year: "numeric",
      })
    } catch {
      return ""
    }
  }

  // --- ANIMATIONS CONFIGS ---

  const heroVariants: any = {
    hidden: { opacity: 0, y: -24 },
    visible: {
      opacity: 1,
      y: 0,
      transition: { duration: 0.6, ease: "easeOut" },
    },
  }

  const cardVariants: any = {
    hidden: { opacity: 0, y: 30, scale: 0.98 },
    visible: {
      opacity: 1,
      y: 0,
      scale: 1,
      transition: { duration: 0.5, delay: 0.15, ease: "easeOut" },
    },
  }

  const featuresContainerVariants: any = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: {
        staggerChildren: 0.1,
        delayChildren: 0.35,
      },
    },
  }

  const featureItemVariants: any = {
    hidden: { opacity: 0, y: 16 },
    visible: {
      opacity: 1,
      y: 0,
      transition: { duration: 0.4 },
    },
  }

  return (
    <PageTransition className="min-h-full py-8 md:py-12">
      {/* Hero Section */}
      <section className="text-center px-4 max-w-3xl mx-auto mb-10 md:mb-14">
        <motion.div initial="hidden" animate="visible" variants={heroVariants}>
          <div className="inline-flex items-center gap-2 bg-blue-50 text-blue-700 px-4 py-2 rounded-full text-xs font-semibold mb-5 border border-blue-200/50 shadow-sm">
            <Sparkles size={13} className="text-blue-600 animate-pulse" />
            <span>AI-Powered Multi-Agent Pipeline</span>
          </div>

          <h1 className="text-3xl sm:text-5xl md:text-6xl font-extrabold tracking-tight text-slate-900 mb-4 leading-tight">
            Research Any Topic
            <span className="bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-transparent block mt-1">
              In Under 60 Seconds
            </span>
          </h1>

          <p className="text-base sm:text-lg text-slate-500 max-w-xl mx-auto leading-relaxed">
            6 autonomous AI agents collaborate in real-time to query Tavily, verify claims, rate sources, and write a comprehensive research report.
          </p>
        </motion.div>
      </section>

      {/* Main Research Form Card */}
      <section className="max-w-2xl mx-auto px-4 pb-12">
        <motion.div
          initial="hidden"
          animate="visible"
          variants={cardVariants}
          className="bg-white rounded-3xl shadow-xl shadow-slate-100 border border-slate-200/80 p-6 sm:p-8 md:p-10"
        >
          {/* STATE 1: AUTH LOADING */}
          {authLoading && (
            <div className="py-20 flex flex-col items-center justify-center gap-4">
              <Spinner className="h-8 w-8 text-blue-600" />
              <p className="text-xs font-semibold text-slate-400">Synchronizing secure session...</p>
            </div>
          )}

          {/* STATE 2: NOT AUTHENTICATED */}
          {!authLoading && !user && (
            <div className="text-center py-10">
              <div className="h-16 w-16 bg-blue-50 text-blue-600 rounded-3xl flex items-center justify-center mx-auto mb-6 shadow-inner">
                <Brain size={32} className="animate-pulse" />
              </div>
              <h2 className="text-2xl font-bold text-slate-900 mb-2">Sign In to Start Researching</h2>
              <p className="text-slate-500 text-sm max-w-sm mx-auto mb-8">
                Gain access to confidence score indicators, source credibility check ratings, and full multi-agent workspaces.
              </p>
              <button
                type="button"
                onClick={signInWithGoogle}
                className="flex items-center justify-center gap-3.5 mx-auto bg-slate-900 hover:bg-slate-800 text-white rounded-2xl px-6 py-4 font-semibold shadow-md shadow-slate-950/15 transition-all duration-200 hover:scale-[1.01] active:scale-[0.99] w-full max-w-xs focus:ring-2 focus:ring-offset-2 focus:ring-slate-900"
              >
                <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
                  <path
                    d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                    fill="#4285F4"
                  />
                  <path
                    d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                    fill="#34A853"
                  />
                  <path
                    d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
                    fill="#FBBC05"
                  />
                  <path
                    d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
                    fill="#EA4335"
                  />
                </svg>
                <span>Continue with Google</span>
              </button>
            </div>
          )}

          {/* STATE 3, 4, 5, 6, 7: LOGGED IN STATES */}
          {!authLoading && user && (
            <form onSubmit={handleSubmit} className={clsx("space-y-6 md:space-y-8", isLoading && "pointer-events-none")}>
              {/* Profile Greeting */}
              <div className="flex items-center gap-3 pb-3 border-b border-slate-100">
                {user.photoURL ? (
                  <img
                    src={user.photoURL}
                    alt={user.displayName || "User profile photo"}
                    className="w-9 h-9 rounded-full ring-2 ring-slate-100 shadow-sm"
                  />
                ) : (
                  <div className="w-9 h-9 bg-slate-100 rounded-full flex items-center justify-center text-sm font-bold text-slate-600">
                    {user.displayName ? user.displayName[0].toUpperCase() : "U"}
                  </div>
                )}
                <div className="text-slate-600 text-sm">
                  Welcome, <span className="font-bold text-slate-800">{user.displayName?.split(" ")[0]}</span>! Let&apos;s research something.
                </div>
              </div>

              {/* Research Topic Textarea */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <label htmlFor="topic" className="block text-sm font-semibold text-slate-700">
                    Research Query Topic
                  </label>
                  <span
                    className={clsx(
                      "text-xs font-semibold",
                      charCount >= 450 ? "text-amber-500 font-bold animate-pulse" : "text-slate-400"
                    )}
                  >
                    {charCount}/500
                  </span>
                </div>
                <div className="relative">
                  <textarea
                    id="topic"
                    disabled={isLoading}
                    value={topic}
                    onChange={handleTopicChange}
                    onKeyDown={handleKeyDown}
                    placeholder="Describe your research question in detail (e.g., 'What are the main causes and effects of ocean acidification by 2026?')"
                    rows={3}
                    className="w-full px-4 py-3 border-2 border-slate-200 rounded-2xl text-slate-900 placeholder-slate-400 focus:border-blue-500 focus:outline-none transition-colors duration-200 text-sm sm:text-base disabled:bg-slate-50 disabled:cursor-not-allowed leading-relaxed"
                  />
                </div>

                {/* Example Topics Chips */}
                <div className="mt-2.5">
                  <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block mb-2">
                    Try an example:
                  </span>
                  <div className="flex flex-wrap gap-2">
                    {exampleTopics.map((example) => (
                      <ExampleTopicChip key={example} topic={example} onClick={setTopic} />
                    ))}
                  </div>
                </div>
              </div>

              {/* Depth Selector Cards */}
              <div className="space-y-3">
                <label className="block text-sm font-semibold text-slate-700">Research Depth level</label>
                <div className="grid grid-cols-3 gap-2 sm:gap-3">
                  {depths.map((d) => (
                    <DepthCard
                      key={d.key}
                      depth={d.key as "quick" | "deep" | "expert"}
                      selected={depth === d.key}
                      onClick={() => !isLoading && setDepth(d.key)}
                      label={d.label}
                      icon={d.icon}
                      questions={d.questions}
                      time={d.time}
                      sources={d.sources}
                      description={d.description}
                      color={d.color}
                    />
                  ))}
                </div>
              </div>

              {/* Language Selector */}
              <div className="space-y-3">
                <label className="text-sm font-semibold text-slate-700 flex items-center gap-1.5">
                  <Languages size={15} className="text-slate-400" />
                  Report Output Language
                </label>
                <LanguageSelector selected={language} onChange={setLanguage} compact={true} />
              </div>

              {/* Error Alert Box */}
              <AnimatePresence>
                {error && (
                  <motion.div
                    initial={{ opacity: 0, y: -8 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -8 }}
                    className="flex items-start gap-2.5 bg-red-50 text-red-700 border border-red-200/50 rounded-xl p-3.5 text-xs sm:text-sm font-medium shadow-sm"
                  >
                    <AlertCircle size={16} className="text-red-500 mt-0.5 shrink-0" />
                    <div className="flex-1 leading-normal">{error}</div>
                  </motion.div>
                )}
              </AnimatePresence>

              {/* Submit Action Button */}
              <div className="space-y-2 pt-2">
                <motion.button
                  type="submit"
                  disabled={isLoading || !topic.trim() || topic.length > 500}
                  whileHover={{ scale: 1.01 }}
                  whileTap={{ scale: 0.99 }}
                  className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-slate-200 disabled:text-slate-400 disabled:cursor-not-allowed text-white font-semibold py-4 px-6 rounded-2xl flex items-center justify-center gap-2.5 transition-all duration-200 hover:shadow-lg shadow-blue-500/10 text-base"
                >
                  {isLoading ? (
                    <>
                      <Spinner className="h-5 w-5 border-t-transparent" />
                      <span>Starting Research Pipeline...</span>
                    </>
                  ) : (
                    <>
                      <Search size={18} />
                      <span>Generate Full Report</span>
                      <ArrowRight size={18} />
                    </>
                  )}
                </motion.button>
                <p className="text-center text-xs text-slate-400">
                  Press <kbd className="font-semibold">Ctrl + Enter</kbd> to launch report instantly
                </p>
              </div>
            </form>
          )}
        </motion.div>

        {/* Recent Reports Feeds */}
        {!authLoading && user && recentReports.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.3 }}
            className="mt-6 bg-white border border-slate-200/80 rounded-3xl p-6 shadow-sm shadow-slate-50"
          >
            <div className="flex items-center justify-between mb-4 pb-2 border-b border-slate-50">
              <h3 className="font-bold text-slate-800 text-sm flex items-center gap-2">
                <History size={16} className="text-slate-400" />
                Recent Research History
              </h3>
              <a href="/history" className="text-xs font-semibold text-blue-600 hover:text-blue-700 transition-colors">
                View all history →
              </a>
            </div>

            <div className="space-y-1">
              {recentReports.map((report) => {
                // Determine status indicator color dot
                const statusDotColor = {
                  done: "bg-green-500 shadow-green-200",
                  failed: "bg-red-500 shadow-red-200",
                  pending: "bg-amber-500 shadow-amber-200 animate-pulse",
                  running: "bg-blue-500 shadow-blue-200 animate-pulse",
                }[report.status] || "bg-slate-400"

                return (
                  <a
                    href={`/report/${report.report_id}`}
                    key={report.report_id}
                    className="flex items-center gap-3.5 p-3 rounded-xl hover:bg-slate-50 transition-all duration-200 group border border-transparent hover:border-slate-100"
                  >
                    <span className={`h-2.5 w-2.5 rounded-full shadow-md shrink-0 ${statusDotColor}`} />
                    <div className="flex-1 min-w-0">
                      <p className="font-semibold text-sm text-slate-800 truncate group-hover:text-blue-700">
                        {report.topic}
                      </p>
                      <p className="text-xs text-slate-400 mt-0.5 flex items-center gap-1 font-medium">
                        <span>{formatDate(report.created_at)}</span>
                        {report.confidence_score > 0 && (
                          <>
                            <span>•</span>
                            <span className="text-slate-500 font-semibold">{report.confidence_score}% confidence</span>
                          </>
                        )}
                        <span>•</span>
                        <span className="capitalize">{report.depth} depth</span>
                      </p>
                    </div>
                    <ChevronRight size={16} className="text-slate-300 group-hover:text-blue-600 transition-colors shrink-0" />
                  </a>
                )
              })}
            </div>
          </motion.div>
        )}
      </section>

      {/* Unique Pipeline Features Matrix cards */}
      <section className="max-w-2xl mx-auto px-4 pb-12">
        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true }}
          variants={featuresContainerVariants}
          className="grid grid-cols-1 md:grid-cols-3 gap-4"
        >
          <motion.div variants={featureItemVariants}>
            <FeatureCard
              icon={<CheckCircle className="text-green-500 h-6 w-6" />}
              title="Fact-Verified Claims"
              description="Extracts claims and tests validity using cross-referenced vector embeddings."
            />
          </motion.div>

          <motion.div variants={featureItemVariants}>
            <FeatureCard
              icon={<Shield className="text-blue-500 h-6 w-6" />}
              title="Source Credibility"
              description="Rates web articles, news, and blogs into specific reliability groups."
            />
          </motion.div>

          <motion.div variants={featureItemVariants}>
            <FeatureCard
              icon={<Globe className="text-purple-500 h-6 w-6" />}
              title="Multi-Language Outputs"
              description="Automatically translates report layouts to English, Spanish, or Hindi."
            />
          </motion.div>
        </motion.div>

        {/* Comparison mode navigation route trigger */}
        <div className="text-center mt-8">
          <a href="/compare" className="text-xs font-semibold text-slate-400 hover:text-blue-600 transition-colors uppercase tracking-wider">
            Switch to Research Comparison Mode →
          </a>
        </div>
      </section>
    </PageTransition>
  )
}

export default function HomePage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
          <Spinner className="h-8 w-8 text-blue-600" />
        </div>
      }
    >
      <Home />
    </Suspense>
  )
}
