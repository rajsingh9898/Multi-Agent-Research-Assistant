export interface WSEvent {
  event: string
  agent: string
  message: string
  data: Record<string, any>
  timestamp: number
}

const getWsUrl = (reportId: string): string => {
  const backendUrl =
    process.env.NEXT_PUBLIC_BACKEND_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    "http://localhost:8000"

  // Convert HTTP → WS, HTTPS → WSS
  const wsUrl = backendUrl
    .replace(/^https:\/\//, "wss://")
    .replace(/^http:\/\//, "ws://")

  return `${wsUrl}/ws/research/${reportId}`
}


export class ResearchWebSocket {
  private ws: WebSocket | null = null
  private reportId: string
  private onEvent: (event: WSEvent) => void
  private onConnected: () => void
  private onDisconnected: () => void
  private onError: (error: string) => void

  private reconnectAttempts = 0
  private maxReconnects = 5
  private reconnectDelay = 2000
  private isIntentionalClose = false
  private pingInterval: NodeJS.Timeout | null = null

  constructor(
    reportId: string,
    onEvent: (event: WSEvent) => void,
    onConnected: () => void,
    onDisconnected: () => void,
    onError: (error: string) => void
  ) {
    this.reportId = reportId
    this.onEvent = onEvent
    this.onConnected = onConnected
    this.onDisconnected = onDisconnected
    this.onError = onError
  }

  public connect(): void {
    this.isIntentionalClose = false
    const url = getWsUrl(this.reportId)
    
    try {
      this.ws = new WebSocket(url)
      
      this.ws.onopen = () => {
        this.reconnectAttempts = 0
        this.onConnected()
        this.startPingInterval()
      }

      this.ws.onmessage = (event: MessageEvent) => {
        try {
          const parsed = JSON.parse(event.data) as WSEvent
          if (parsed.event === "keepalive") {
            // Keepalive telemetry ignore
            return
          }
          this.onEvent(parsed)
        } catch (err) {
          console.error("Failed to parse WebSocket message JSON content:", err)
        }
      }

      this.ws.onclose = () => {
        this.stopPingInterval()
        if (!this.isIntentionalClose && this.reconnectAttempts < this.maxReconnects) {
          this.reconnectAttempts++
          this.onDisconnected()
          setTimeout(() => this.connect(), this.reconnectDelay)
        } else if (!this.isIntentionalClose) {
          this.onError("Connection closed. Maximum reconnection attempts reached.")
        }
      }

      this.ws.onerror = () => {
        this.onError("WebSocket connection error encountered.")
      }

    } catch (err) {
      this.onError(`Failed to establish socket connection: ${err}`)
    }
  }

  public disconnect(): void {
    this.isIntentionalClose = true
    this.stopPingInterval()
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
  }

  public isConnected(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN
  }

  private startPingInterval(): void {
    this.stopPingInterval()
    this.pingInterval = setInterval(() => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.ws.send("ping")
      }
    }, 25000)
  }

  private stopPingInterval(): void {
    if (this.pingInterval) {
      clearInterval(this.pingInterval)
      this.pingInterval = null
    }
  }
}
