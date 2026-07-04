"use client"

import React, { useEffect, useRef } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { Brain, ChevronDown } from "lucide-react"
import { clsx } from "clsx"

export interface ThinkingLogItem {
  agent: string
  thought: string
  timestamp: number
}

interface ThinkingLogProps {
  thoughts: ThinkingLogItem[]
  isOpen: boolean
  onToggle: () => void
}

const agentColors: Record<string, string> = {
  orchestrator: "bg-purple-500 shadow-purple-500/20",
  search_agent: "bg-blue-500 shadow-blue-500/20",
  summary_agent: "bg-amber-500 shadow-amber-500/20",
  factcheck_agent: "bg-green-500 shadow-green-500/20",
  writer_agent: "bg-rose-500 shadow-rose-500/20",
  followup_agent: "bg-indigo-500 shadow-indigo-500/20",
}

const agentTextColors: Record<string, string> = {
  orchestrator: "text-purple-400",
  search_agent: "text-blue-400",
  summary_agent: "text-amber-400",
  factcheck_agent: "text-green-400",
  writer_agent: "text-rose-400",
  followup_agent: "text-indigo-400",
}

export default function ThinkingLog({ thoughts, isOpen, onToggle }: ThinkingLogProps) {
  const bottomRef = useRef<HTMLDivElement | null>(null)

  // Auto-scroll anchor effect on new logs addition
  useEffect(() => {
    if (isOpen && thoughts.length > 0) {
      bottomRef.current?.scrollIntoView({
        behavior: "smooth",
      })
    }
  }, [thoughts, isOpen])

  return (
    <div className="bg-slate-900 rounded-2xl border border-slate-800 shadow-lg overflow-hidden transition-all duration-300">
      {/* Header section button */}
      <button
        type="button"
        onClick={onToggle}
        className="w-full flex items-center justify-between p-4 sm:p-5 hover:bg-slate-800/50 transition-colors focus:outline-none"
        aria-expanded={isOpen}
      >
        <div className="flex items-center gap-3">
          <div className="h-7 w-7 rounded-xl bg-purple-950 flex items-center justify-center text-purple-400 border border-purple-900/50">
            <Brain size={15} className="animate-pulse" />
          </div>
          <div className="text-left">
            <span className="text-sm font-semibold text-slate-100 block">Agent Reasoning Logs</span>
            <span className="text-[10px] text-slate-400 font-medium block">
              Inspect backend multi-agent decision steps
            </span>
          </div>
          <span className="text-xs bg-purple-900/40 text-purple-300 px-2 py-0.5 rounded-full font-bold border border-purple-800/30">
            {thoughts.length} thoughts
          </span>
        </div>

        <ChevronDown
          size={16}
          className={clsx("text-slate-400 transition-transform duration-300", isOpen && "rotate-180")}
        />
      </button>

      {/* Collapse container panel */}
      <AnimatePresence initial={false}>
        {isOpen && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.3, ease: "easeInOut" }}
            className="overflow-hidden border-t border-slate-800"
          >
            <div className="p-4 sm:p-5 space-y-3 max-h-72 overflow-y-auto font-mono text-xs">
              {thoughts.length === 0 ? (
                <p className="text-xs text-slate-500 py-6 text-center italic font-sans font-medium">
                  Reasoning traces will populate here when agents activate...
                </p>
              ) : (
                thoughts.map((thought, index) => {
                  const agentKey = thought.agent.replace("_agent", "")
                  const dotColor = agentColors[thought.agent] || "bg-slate-500 shadow-slate-500/20"
                  const labelColor = agentTextColors[thought.agent] || "text-slate-400"

                  return (
                    <motion.div
                      key={`${thought.timestamp}-${index}`}
                      initial={{ opacity: 0, x: -8 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ duration: 0.2 }}
                      className="flex items-start gap-3 py-1 border-b border-slate-800/50 last:border-0"
                    >
                      {/* Agent dot indicator */}
                      <div className={clsx("w-1.5 h-1.5 rounded-full mt-1.5 flex-shrink-0 shadow-sm animate-pulse", dotColor)} />
                      
                      {/* Thought text content */}
                      <div className="flex-1 min-w-0 leading-relaxed text-slate-300">
                        <span className={clsx("font-bold mr-1.5 flex-shrink-0 capitalize", labelColor)}>
                          [{agentKey}]
                        </span>
                        <span>{thought.thought}</span>
                      </div>
                    </motion.div>
                  )
                })
              )}
              {/* Auto-scroll anchor point */}
              <div ref={bottomRef} />
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
