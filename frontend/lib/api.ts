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

export type ReportStatus = "pending" | "running" | "done" | "failed"

export interface HistoryReport {
  report_id: string
  topic: string
  status: ReportStatus
  created_at: string | null
  confidence_score: number
  pdf_url: string | null
  word_count: number | null
  depth: string
  language: string
}

export type HistoryItem = HistoryReport

export interface HistoryResponse {
  success: boolean
  reports: HistoryReport[]
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

export interface KeyFinding {
  point: string
  citation: string
  status: "verified" | "uncertain"
}

export interface Source {
  url: string
  title: string
  credibility: string
  credibility_icon: string
}

export interface ReportData {
  title: string
  language: string
  executive_summary: string
  key_findings: KeyFinding[]
  detailed_analysis: string
  limitations: string
  conclusion: string
  sources: Source[]
  word_count: number
  confidence_score: number
  confidence_label: string
  confidence_emoji: string
  sub_questions_covered: string[]
  total_sources_used: number
  generated_at: string
  report_id: string
}

export interface FullReport {
  report_id: string
  topic: string
  depth: string
  language: string
  status: string
  created_at: string | null
  completed_at: string | null
  report_data: ReportData
  confidence_score: number
  pdf_url: string | null
  followup_questions: string[]
  error: string | null
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
  getReport: (reportId: string) => authFetch<FullReport>(`/api/research/${reportId}`),

  /** Fetch the signed-in user's report history. */
  getHistory: (limit?: number) => authFetch<HistoryResponse>(`/api/reports/history${limit ? `?limit=${limit}` : ""}`),

  /** Delete a report by id. */
  deleteReport: (reportId: string) =>
    authFetch<{ success: boolean; message: string }>(`/api/reports/${reportId}`, {
      method: "DELETE",
    }),

  /** Request PDF export for a report. */
  exportPdf: (reportId: string) =>
    authFetch<{ success: boolean; pdf_url: string }>("/api/export/pdf", {
      method: "POST",
      body: { report_id: reportId },
    }),
}
