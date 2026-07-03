"use client"

import React from "react"
import { Globe } from "lucide-react"

interface LanguageSelectorProps {
  selected: string
  onChange: (language: string) => void
  compact?: boolean
}

const LANGUAGES = [
  { key: "english", name: "English", native: "English", flag: "🇬🇧" },
  { key: "hindi", name: "Hindi", native: "हिन्दी", flag: "🇮🇳" },
  { key: "spanish", name: "Spanish", native: "Español", flag: "🇪🇸" },
]

export default function LanguageSelector({
  selected,
  onChange,
  compact = false,
}: LanguageSelectorProps) {
  if (compact) {
    return (
      <div className="flex flex-wrap gap-2" role="group" aria-label="Language selector">
        {LANGUAGES.map((lang) => {
          const isSelected = selected === lang.key
          return (
            <button
              key={lang.key}
              type="button"
              onClick={() => onChange(lang.key)}
              className={`flex items-center gap-2 rounded-full px-4 py-2 text-sm font-medium transition-all duration-200 focus-visible:outline-2 focus-visible:outline-blue-500 ${
                isSelected
                  ? "bg-slate-900 text-white shadow-sm"
                  : "bg-white border border-slate-200 text-slate-600 hover:border-slate-300 hover:bg-slate-50"
              }`}
            >
              <span>{lang.flag}</span>
              <span>{lang.name}</span>
            </button>
          )
        })}
      </div>
    )
  }

  return (
    <div className="grid grid-cols-3 gap-3" role="group" aria-label="Language selector">
      {LANGUAGES.map((lang) => {
        const isSelected = selected === lang.key
        return (
          <button
            key={lang.key}
            type="button"
            onClick={() => onChange(lang.key)}
            className={`flex flex-col items-center justify-center p-4 rounded-xl border-2 text-center transition-all duration-200 hover:scale-[1.02] hover:shadow-sm ${
              isSelected
                ? "bg-blue-50/50 border-blue-600 text-blue-900 shadow-sm"
                : "bg-white border-slate-200 text-slate-700 hover:border-slate-300 hover:bg-slate-50"
            }`}
          >
            <span className="text-2xl mb-1 filter drop-shadow-sm">{lang.flag}</span>
            <span className="font-semibold text-sm leading-tight">{lang.name}</span>
            <span className={`text-xs mt-0.5 ${isSelected ? "text-blue-600" : "text-slate-400"}`}>
              {lang.native}
            </span>
          </button>
        )
      })}
    </div>
  )
}
