"use client"

import React from "react"
import { motion } from "framer-motion"
import { Clock, CheckCircle2, XCircle, Loader2 } from "lucide-react"
import { clsx } from "clsx"

export type AgentStatus = "waiting" | "running" | "done" | "failed"

export interface AgentInfo {
  id: string
  name: string
  emoji: string
  description: string
  status: AgentStatus
  message: string
  startedAt: number | null
  completedAt: number | null
}

interface AgentCardProps {
  agent: AgentInfo
  isActive: boolean
}

const statusColors: Record<AgentStatus, string> = {
  waiting: "border-slate-200 bg-white text-slate-400",
  running: "border-blue-400 bg-blue-50/45 text-blue-700",
  done: "border-green-400 bg-green-50/45 text-green-700",
  failed: "border-red-400 bg-red-50/45 text-red-700",
}

const statusTextColors: Record<AgentStatus, string> = {
  waiting: "text-slate-400",
  running: "text-blue-600 font-bold",
  done: "text-green-600 font-bold",
  failed: "text-red-600 font-bold",
}

export default function AgentCard({ agent, isActive }: AgentCardProps) {
  // Border animations based on states
  const borderVariants: any = {
    waiting: { scale: 1 },
    running: {
      scale: 1.01,
      transition: { type: "spring", stiffness: 300, damping: 20 },
    },
    done: {
      scale: 1,
      transition: { type: "spring", stiffness: 400, damping: 15 },
    },
    failed: {
      x: [0, -4, 4, -4, 4, 0],
      transition: { duration: 0.4 },
    },
  }

  return (
    <motion.div
      layout
      variants={borderVariants}
      animate={agent.status}
      className={clsx(
        "relative rounded-2xl border-2 p-4 sm:p-5 flex flex-col justify-between transition-all duration-300",
        statusColors[agent.status],
        isActive && "shadow-lg shadow-blue-100"
      )}
    >
      {/* Pulse ring on active task running */}
      {agent.status === "running" && (
        <div className="absolute inset-0 rounded-2xl border-2 border-blue-400 animate-ping opacity-25" />
      )}

      <div>
        {/* Header row details */}
        <div className="flex items-start justify-between mb-3">
          <div className="flex items-center gap-2.5 min-w-0">
            <span className="text-2xl filter drop-shadow-sm flex-shrink-0">
              {agent.status === "done" ? "✅" : agent.status === "failed" ? "❌" : agent.emoji}
            </span>
            <div className="min-w-0">
              <p className="font-bold text-slate-800 text-sm leading-snug truncate">{agent.name}</p>
              <p className="text-[11px] text-slate-400 font-medium truncate">{agent.description}</p>
            </div>
          </div>

          {/* Status Indicator Icon */}
          <div className="flex-shrink-0">
            {agent.status === "waiting" && <Clock size={16} className="text-slate-300" />}
            {agent.status === "running" && <Loader2 size={16} className="text-blue-500 animate-spin" />}
            {agent.status === "done" && <CheckCircle2 size={16} className="text-green-500" />}
            {agent.status === "failed" && <XCircle size={16} className="text-red-500" />}
          </div>
        </div>

        {/* State status text label */}
        <div className={clsx("text-[10px] font-bold uppercase tracking-wider mb-1.5", statusTextColors[agent.status])}>
          {agent.status === "waiting" && "Waiting..."}
          {agent.status === "running" && "Running..."}
          {agent.status === "done" && "Complete"}
          {agent.status === "failed" && "Failed"}
        </div>

        {/* Dynamic status messaging */}
        {agent.message && (
          <p className="text-xs text-slate-600 leading-normal line-clamp-3 break-words font-medium">
            {agent.message}
          </p>
        )}
      </div>

      {/* Timing completion metrics */}
      {agent.completedAt && agent.startedAt && (
        <div className="mt-3 pt-2.5 border-t border-slate-100 flex items-center justify-end text-[10px] font-bold text-slate-400">
          <span>{((agent.completedAt - agent.startedAt) / 1000).toFixed(1)}s elapsed</span>
        </div>
      )}
    </motion.div>
  )
}
