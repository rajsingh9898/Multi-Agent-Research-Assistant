// Simple websocket helper for frontend to connect to backend live updates

export function wsUrl(reportId: string) {
  const base = process.env.NEXT_PUBLIC_WS_BASE || 'ws://localhost:8000'
  return `${base.replace(/^http/, 'ws')}/ws/research/${reportId}`
}
