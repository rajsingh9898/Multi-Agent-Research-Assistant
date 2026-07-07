"use client"

import React from "react"
import { motion, AnimatePresence } from "framer-motion"
import { Trash2, AlertTriangle, Loader2 } from "lucide-react"

interface DeleteConfirmModalProps {
  isOpen: boolean
  topic: string
  onConfirm: () => void
  onCancel: () => void
  isDeleting: boolean
}

export default function DeleteConfirmModal({
  isOpen,
  topic,
  onConfirm,
  onCancel,
  isDeleting,
}: DeleteConfirmModalProps) {
  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* BACKDROP */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onCancel}
            className="fixed inset-0 bg-black/50 z-50 backdrop-blur-sm"
          />

          {/* MODAL */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 20 }}
            transition={{ type: "spring", stiffness: 300, damping: 30 }}
            className="fixed inset-0 z-50 flex items-center justify-center p-4"
          >
            <div
              className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-6"
              onClick={(e) => e.stopPropagation()}
            >
              {/* ICON */}
              <div className="w-14 h-14 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <Trash2 size={24} className="text-red-500" />
              </div>

              {/* TITLE */}
              <h2 className="text-xl font-bold text-slate-800 text-center mb-2">
                Delete Report?
              </h2>

              {/* TOPIC */}
              <p className="text-slate-505 text-center text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                You're about to delete:
              </p>
              <p className="text-slate-800 font-semibold text-center text-sm mb-6 bg-slate-50 rounded-xl px-4 py-3 border border-slate-200 line-clamp-2 leading-relaxed">
                "{topic}"
              </p>

              {/* WARNING */}
              <div className="flex items-start gap-2.5 bg-amber-50 border border-amber-250 rounded-xl p-3.5 mb-6">
                <AlertTriangle size={16} className="text-amber-500 flex-shrink-0 mt-0.5" />
                <p className="text-xs text-amber-700 leading-relaxed font-medium">
                  This will permanently delete the report and all associated data. This action cannot be undone.
                </p>
              </div>

              {/* BUTTONS */}
              <div className="flex gap-3">
                <button
                  type="button"
                  onClick={onCancel}
                  disabled={isDeleting}
                  className="flex-1 px-4 py-3 border border-slate-200 text-slate-700 rounded-xl font-semibold text-sm hover:bg-slate-50 transition-colors disabled:opacity-50 focus:outline-none"
                >
                  Cancel
                </button>

                <button
                  type="button"
                  onClick={onConfirm}
                  disabled={isDeleting}
                  className="flex-1 px-4 py-3 bg-red-600 hover:bg-red-700 text-white rounded-xl font-semibold text-sm transition-colors flex items-center justify-center gap-2 disabled:opacity-50 focus:outline-none shadow-md shadow-red-500/10"
                >
                  {isDeleting ? (
                    <>
                      <Loader2 size={16} className="animate-spin" />
                      <span>Deleting...</span>
                    </>
                  ) : (
                    <>
                      <Trash2 size={16} />
                      <span>Delete Report</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
