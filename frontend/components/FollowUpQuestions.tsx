"use client"

import React from "react"
import { motion } from "framer-motion"
import { Sparkles, ArrowRight } from "lucide-react"

interface FollowUpQuestionsProps {
  questions: string[]
  onQuestionClick: (question: string) => void
}

export default function FollowUpQuestions({
  questions,
  onQuestionClick,
}: FollowUpQuestionsProps) {
  return (
    <div className="bg-gradient-to-br from-indigo-50/50 to-purple-50/50 rounded-2xl border border-indigo-100 p-5 sm:p-6">
      {/* Header icon row */}
      <div className="flex items-center gap-3 mb-4">
        <div className="w-8 h-8 bg-indigo-100 border border-indigo-200/25 rounded-xl flex items-center justify-center text-indigo-600">
          <Sparkles size={16} className="animate-pulse" />
        </div>
        <div>
          <h3 className="font-bold text-slate-800 text-sm">Continue Your Research</h3>
          <p className="text-[11px] text-slate-400 font-semibold uppercase tracking-wider">
            AI-Suggested Follow-Ups
          </p>
        </div>
      </div>

      {/* Questions list buttons */}
      <div className="space-y-2.5">
        {questions.map((question, index) => (
          <motion.button
            key={index}
            type="button"
            onClick={() => onQuestionClick(question)}
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: index * 0.08 }}
            whileHover={{ x: 4 }}
            whileTap={{ scale: 0.99 }}
            className="w-full text-left flex items-start gap-3.5 p-3.5 rounded-xl bg-white border border-indigo-100/70 hover:border-indigo-300 hover:shadow-sm transition-all duration-200 group focus:outline-none"
          >
            {/* Number Index badge */}
            <span className="flex-shrink-0 w-6 h-6 rounded-full bg-indigo-50 text-indigo-700 text-xs font-extrabold flex items-center justify-center group-hover:bg-indigo-600 group-hover:text-white transition-all duration-200">
              {index + 1}
            </span>

            {/* Question query title */}
            <span className="text-xs sm:text-sm font-semibold text-slate-700 group-hover:text-slate-900 transition-colors duration-150 flex-1 leading-relaxed">
              {question}
            </span>

            {/* Right arrow transition */}
            <ArrowRight
              size={14}
              className="text-slate-300 group-hover:text-indigo-600 flex-shrink-0 mt-1 transition-all duration-200 group-hover:translate-x-1"
            />
          </motion.button>
        ))}
      </div>

      <p className="text-[10px] text-slate-400 font-bold tracking-wider mt-4 text-center uppercase">
        Click any suggestion to trigger a new research report
      </p>
    </div>
  )
}
