"use client"

import React from "react"
import { clsx } from "clsx"

interface SkeletonProps {
  className?: string
  variant?: "text" | "circle" | "rect"
  animate?: boolean
}

export const Skeleton = ({
  className,
  variant = "rect",
  animate = true,
}: SkeletonProps) => {
  return (
    <div
      className={clsx(
        "bg-slate-200",
        animate && "animate-pulse",
        variant === "circle" && "rounded-full",
        variant === "text" && "rounded",
        variant === "rect" && "rounded-lg",
        className
      )}
    />
  )
}

export const SkeletonCard = () => {
  return (
    <div className="bg-white rounded-2xl border border-slate-200 p-5 space-y-4">
      {/* Top Row: Status Dot + Topic Title + Date */}
      <div className="flex items-start gap-3">
        <Skeleton variant="circle" className="w-3 h-3 mt-1.5 shrink-0" />
        <div className="flex-1 space-y-2">
          <Skeleton variant="text" className="h-4 w-5/6" />
          <Skeleton variant="text" className="h-3 w-1/3" />
        </div>
        <Skeleton variant="rect" className="h-5 w-16 shrink-0" />
      </div>

      {/* Middle: Stats details + Confidence bar */}
      <div className="space-y-3 pt-1">
        <div className="flex gap-2">
          <Skeleton variant="text" className="h-3 w-16" />
          <Skeleton variant="text" className="h-3 w-12" />
          <Skeleton variant="text" className="h-3 w-20" />
        </div>
        
        {/* Confidence bar placeholder */}
        <div className="bg-slate-50 border border-slate-100 p-2.5 rounded-xl space-y-2">
          <div className="flex justify-between">
            <Skeleton variant="text" className="h-2.5 w-16" />
            <Skeleton variant="text" className="h-2.5 w-8" />
          </div>
          <Skeleton variant="rect" className="h-1.5 w-full" />
        </div>
      </div>

      {/* Bottom: Action buttons */}
      <div className="flex gap-2 pt-1.5">
        <Skeleton variant="rect" className="h-9 flex-1" />
        <Skeleton variant="rect" className="h-9 w-10 shrink-0" />
      </div>
    </div>
  )
}

export const SkeletonReportHeader = () => {
  return (
    <div className="bg-white border-b border-slate-200/60 sticky top-[69px] z-20">
      <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between gap-4">
        {/* Back + Title */}
        <div className="flex items-center gap-3.5 flex-1 min-w-0">
          <Skeleton variant="circle" className="w-8 h-8 shrink-0" />
          <div className="flex-1 space-y-1.5">
            <Skeleton variant="text" className="h-5 w-3/4 max-w-[400px]" />
            <Skeleton variant="text" className="h-3 w-1/3 max-w-[200px]" />
          </div>
        </div>

        {/* Buttons list */}
        <div className="flex items-center gap-2 shrink-0">
          <Skeleton variant="rect" className="h-9 w-24 md:w-32" />
          <Skeleton variant="rect" className="h-9 w-12 md:w-28" />
          <Skeleton variant="rect" className="h-9 w-12 md:w-28" />
        </div>
      </div>
    </div>
  )
}

export const SkeletonReportSection = ({ withFindings = false }: { withFindings?: boolean }) => {
  return (
    <div className="bg-white border border-slate-200/60 p-5 sm:p-6 rounded-2xl shadow-sm space-y-4">
      {/* Title */}
      <div className="flex items-center gap-2">
        <Skeleton variant="circle" className="w-5 h-5" />
        <Skeleton variant="text" className="h-5 w-36" />
      </div>
      <Skeleton variant="rect" className="h-1 w-12" />

      {/* Text lines */}
      <div className="space-y-3 pt-2">
        <Skeleton variant="text" className="h-4 w-full" />
        <Skeleton variant="text" className="h-4 w-[96%]" />
        <Skeleton variant="text" className="h-4 w-[92%]" />
        <Skeleton variant="text" className="h-4 w-[85%]" />
        <Skeleton variant="text" className="h-4 w-[60%]" />
      </div>

      {/* Finding cards */}
      {withFindings && (
        <div className="space-y-3 pt-2">
          {[1, 2].map((i) => (
            <div key={i} className="flex gap-4 p-4 rounded-xl border border-slate-100 bg-slate-50/20">
              <Skeleton variant="circle" className="w-6 h-6 shrink-0" />
              <div className="flex-1 space-y-2">
                <Skeleton variant="text" className="h-4 w-full" />
                <Skeleton variant="text" className="h-4 w-[90%]" />
                <div className="flex gap-2.5 pt-1.5">
                  <Skeleton variant="rect" className="h-4 w-20" />
                  <Skeleton variant="rect" className="h-4 w-24" />
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export const SkeletonSidebar = () => {
  return (
    <div className="space-y-6">
      {/* Confidence score card */}
      <div className="bg-white rounded-2xl border border-slate-250 p-6 shadow-sm space-y-4">
        <div className="flex items-center gap-4">
          <Skeleton variant="circle" className="w-16 h-16 shrink-0" />
          <div className="space-y-2 flex-1">
            <Skeleton variant="text" className="h-3 w-16" />
            <Skeleton variant="text" className="h-4 w-24" />
            <Skeleton variant="text" className="h-2.5 w-20" />
          </div>
        </div>
        <Skeleton variant="rect" className="h-2 w-full" />
        <Skeleton variant="text" className="h-3 w-4/5" />
      </div>

      {/* Telemetry stats card */}
      <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm space-y-4">
        <div className="flex items-center gap-2">
          <Skeleton variant="circle" className="w-4 h-4" />
          <Skeleton variant="text" className="h-4 w-32" />
        </div>
        <div className="space-y-3 pt-1">
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="flex justify-between">
              <Skeleton variant="text" className="h-3.5 w-24" />
              <Skeleton variant="text" className="h-3.5 w-12" />
            </div>
          ))}
        </div>
      </div>

      {/* Suggested Followups */}
      <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm space-y-4">
        <div className="flex items-center gap-2">
          <Skeleton variant="circle" className="w-4 h-4" />
          <Skeleton variant="text" className="h-4 w-28" />
        </div>
        <div className="space-y-2.5 pt-1">
          {[1, 2, 3].map((i) => (
            <Skeleton variant="rect" className="h-10 w-full" />
          ))}
        </div>
      </div>
    </div>
  )
}

export const SkeletonAgentCards = () => {
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
      {[1, 2, 3, 4, 5, 6].map((i) => (
        <div key={i} className="bg-white rounded-2xl border border-slate-200 p-5 space-y-3 shadow-sm">
          <div className="flex items-center justify-between">
            <Skeleton variant="circle" className="w-8 h-8" />
            <Skeleton variant="rect" className="h-5 w-12" />
          </div>
          <Skeleton variant="text" className="h-4 w-2/3" />
          <Skeleton variant="text" className="h-3 w-full" />
          <Skeleton variant="rect" className="h-2.5 w-full" />
        </div>
      ))}
    </div>
  )
}
