"use client"

import React from "react"
import { Loader2 } from "lucide-react"
import { clsx } from "clsx"

interface LoadingSpinnerProps {
  size?: "sm" | "md" | "lg"
  color?: "blue" | "white" | "slate"
  label?: string
}

const sizeClasses = {
  sm: "w-4 h-4",
  md: "w-8 h-8",
  lg: "w-12 h-12",
}

const colorClasses = {
  blue: "text-blue-600",
  white: "text-white",
  slate: "text-slate-500",
}

export default function LoadingSpinner({
  size = "md",
  color = "blue",
  label,
}: LoadingSpinnerProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-3">
      <Loader2
        className={clsx(
          "animate-spin",
          sizeClasses[size] || sizeClasses.md,
          colorClasses[color] || colorClasses.blue
        )}
      />
      {label && (
        <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">
          {label}
        </span>
      )}
    </div>
  )
}

export const PageLoader = ({ label = "Loading..." }: { label?: string }) => {
  return (
    <div className="min-h-[60vh] w-full flex items-center justify-center">
      <LoadingSpinner size="lg" label={label} />
    </div>
  )
}

export const InlineLoader = ({ className }: { className?: string }) => {
  return (
    <Loader2 className={clsx("animate-spin w-4 h-4 text-current shrink-0", className)} />
  )
}
