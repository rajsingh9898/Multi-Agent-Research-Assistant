"use client"

import { toast } from "react-hot-toast"

export const TOAST_STYLES = {
  success: {
    duration: 3000,
    style: {
      background: "#f0fdf4",
      color: "#166534",
      border: "1px solid #bbf7d0",
      borderRadius: "12px",
      padding: "12px 16px",
      fontSize: "14px",
      fontWeight: "600",
    },
    iconTheme: {
      primary: "#16a34a",
      secondary: "#f0fdf4",
    },
  },
  error: {
    duration: 4000,
    style: {
      background: "#fef2f2",
      color: "#991b1b",
      border: "1px solid #fecaca",
      borderRadius: "12px",
      padding: "12px 16px",
      fontSize: "14px",
      fontWeight: "600",
    },
    iconTheme: {
      primary: "#dc2626",
      secondary: "#fef2f2",
    },
  },
  loading: {
    style: {
      background: "#eff6ff",
      color: "#1e40af",
      border: "1px solid #bfdbfe",
      borderRadius: "12px",
      padding: "12px 16px",
      fontSize: "14px",
      fontWeight: "650",
    },
  },
}

export const showSuccess = (message: string) => {
  return toast.success(message, TOAST_STYLES.success)
}

export const showError = (message: string) => {
  return toast.error(message, TOAST_STYLES.error)
}

export const showLoading = (message: string, id?: string) => {
  return toast.loading(message, {
    ...TOAST_STYLES.loading,
    id,
  })
}

export const dismissToast = (id: string) => {
  toast.dismiss(id)
}

export const RESEARCH_TOASTS = {
  RESEARCH_STARTED: "🚀 Research started! Watch the agents work.",
  RESEARCH_COMPLETE: "✅ Report ready! Redirecting...",
  PDF_GENERATING: "📄 Generating your PDF...",
  PDF_READY: "📥 PDF ready! Opening...",
  LINK_COPIED: "🔗 Link copied to clipboard!",
  REPORT_DELETED: "🗑️ Report deleted successfully",
  LOGIN_SUCCESS: (name: string) => `👋 Welcome back, ${name}!`,
  LOGOUT_SUCCESS: "👋 Signed out. See you soon!",
  SIGNIN_REQUIRED: "🔐 Please sign in to continue",
  ERROR_GENERIC: "❌ Something went wrong. Try again.",
  ERROR_NETWORK: "📡 Connection failed. Check your internet.",
  ERROR_NOT_FOUND: "🔍 Report not found.",
}
