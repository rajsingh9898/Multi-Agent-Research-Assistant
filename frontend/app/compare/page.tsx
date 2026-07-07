"use client"

import React from "react"
import Link from "next/link"
import { GitCompare, HelpCircle, ArrowRight, Plus } from "lucide-react"

import PageTransition from "../../components/ui/PageTransition"

export default function ComparePage() {
  return (
    <PageTransition className="max-w-4xl mx-auto px-4 py-8">
      {/* HEADER SECTION */}
      <div className="text-center max-w-2xl mx-auto mb-10">
        <div className="w-16 h-16 bg-blue-50 border border-blue-100 rounded-2xl flex items-center justify-center text-blue-600 mx-auto mb-5 shadow-sm">
          <GitCompare size={28} />
        </div>
        
        <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-blue-100 text-blue-800 border border-blue-200 uppercase tracking-wider mb-3">
          Roadmap Feature
        </span>
        
        <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight mb-3 sm:text-4xl">
          Compare Research Topics
        </h1>
        
        <p className="text-slate-500 font-semibold text-sm leading-relaxed">
          Cross-reference reports side-by-side, analyze divergent sources, and compare credibility and confidence metrics instantly.
        </p>
      </div>

      {/* DISABLED INPUT FIELDS AREA */}
      <div className="bg-white border border-slate-200/80 rounded-3xl p-6 sm:p-8 shadow-sm max-w-2xl mx-auto mb-10 relative overflow-hidden">
        {/* Background Overlay Badge */}
        <div className="absolute top-4 right-4 bg-slate-100 text-slate-500 text-[10px] font-extrabold px-2.5 py-0.5 rounded-full border border-slate-200/50 uppercase tracking-wider select-none">
          Locked
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 opacity-60 pointer-events-none select-none">
          {/* Topic A */}
          <div className="space-y-2">
            <label className="text-xs font-bold text-slate-400 uppercase tracking-wider block">
              Topic A Query
            </label>
            <textarea
              disabled
              placeholder="e.g. Artificial Intelligence impacts on primary education"
              className="w-full p-4 border border-slate-200 bg-slate-50 text-slate-400 rounded-2xl text-sm h-32 resize-none"
            />
          </div>

          {/* Topic B */}
          <div className="space-y-2">
            <label className="text-xs font-bold text-slate-400 uppercase tracking-wider block">
              Topic B Query
            </label>
            <textarea
              disabled
              placeholder="e.g. Traditional learning methods impacts on primary education"
              className="w-full p-4 border border-slate-200 bg-slate-50 text-slate-400 rounded-2xl text-sm h-32 resize-none"
            />
          </div>
        </div>

        <div className="mt-8 border-t border-slate-100 pt-6 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2.5">
            <HelpCircle size={18} className="text-slate-400 shrink-0" />
            <p className="text-xs text-slate-500 font-medium">
              Want to see this feature live? Let us know in feedback.
            </p>
          </div>
          
          <button
            type="button"
            disabled
            className="w-full sm:w-auto flex items-center justify-center gap-2 px-5 py-3 bg-slate-100 border border-slate-200/80 text-slate-400 rounded-xl text-sm font-bold pointer-events-none"
          >
            <span>Compare Topics</span>
            <ArrowRight size={14} />
          </button>
        </div>
      </div>

      {/* REDIRECT ACTION BUTTON */}
      <div className="text-center">
        <Link
          href="/"
          className="inline-flex items-center gap-2 px-6 py-3.5 bg-blue-600 hover:bg-blue-700 text-white rounded-2xl text-sm font-bold transition-all shadow-md shadow-blue-500/10 hover:shadow-lg focus:outline-none"
        >
          <Plus size={16} />
          <span>Start Regular Research</span>
        </Link>
      </div>
    </PageTransition>
  )
}
