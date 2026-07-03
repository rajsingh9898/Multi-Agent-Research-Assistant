"use client"

/**
 * Typed API helpers for calling the FastAPI backend with Firebase auth.
 */

import { getIdToken } from "./firebase"

export type ResearchStartRequest = {
  topic: string
  depth: "quick" | "deep" | "expert"
  language: "english" | "hindi" | "spanish"
}

export interface ResearchStartResponse {
  success: boolean
  report_id: string
  topic: string
  status: string
  websocket_url: string
  message: string
}

export interface HistoryItem {
  report_id: string
  topic: string
  status: string
  created_at: string | null
  confidence_score: number
  pdf_url: string | null
  word_count: number | null
  depth: string
  language: string
}

export interface HistoryResponse {
  success: boolean
  reports: HistoryItem[]
  count: number
}

export type AuthUser = {
  uid: string
  email: string | null
  display_name: string | null
  photo_url: string | null
  email_verified: boolean
  created_at: string | null
  last_login_at: string | null
}

export type ReportData = {
  report_id: string
  user_id: string
  topic: string
  depth: string
  language: string
  status: string
  confidence_score: number
  source_credibility: Array<Record<string, unknown>>
  thinking_logs: Array<Record<string, unknown>>
  followup_questions: string[]
  report_markdown: string
  created_at: string
  completed_at: string | null
}

export type ApiOptions = {
  method?: string
  body?: unknown
  headers?: Record<string, string>
}

const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"

/**
 * Build an authenticated fetch request with the Firebase bearer token attached.
 */
export async function authFetch<T>(path: string, options: ApiOptions = {}): Promise<T> {
  try {
    const token = await getIdToken()
    if (!token) {
      throw new Error("You must sign in before calling protected endpoints")
    }

    const response = await fetch(`${apiBaseUrl}${path}`, {
      method: options.method ?? "GET",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
        ...(options.headers ?? {}),
      },
      body: options.body ? JSON.stringify(options.body) : undefined,
    })

    if (!response.ok) {
      const errorBody = await response.json().catch(() => null)
      throw new Error(errorBody?.detail ?? `Request failed with status ${response.status}`)
    }

    return (await response.json()) as T
  } catch (error) {
    const message = error instanceof Error ? error.message : "API request failed"
    throw new Error(message)
  }
}

/**
 * Helper methods for the auth endpoints.
 */
export const authAPI = {
  /** Return the current authenticated user from the backend. */
  getMe: () => authFetch<AuthUser>("/api/auth/me"),
}

/**
 * Helper methods for research workflow endpoints.
 */
export const researchAPI = {
  /** Start a new research session. */
  start: (topic: string, depth: string, language: string) =>
    authFetch<ResearchStartResponse>("/api/research/start", {
      method: "POST",
      body: { topic, depth, language },
    }),

  /** Fetch a report by id. */
  getReport: (reportId: string) => authFetch<ReportData>(`/api/research/${reportId}`),

  /** Fetch the signed-in user's report history. */
  getHistory: () => authFetch<HistoryResponse>("/api/reports/history"),

  /** Delete a report by id. */
  deleteReport: (reportId: string) =>
    authFetch<{ message: string }>(`/api/reports/${reportId}`, {
      method: "DELETE",
    }),

  /** Request PDF export for a report. */
  exportPdf: (reportId: string) =>
    authFetch<{ pdf_url: string }>("/api/export/pdf", {
      method: "POST",
      body: { report_id: reportId },
    }),
}
