import React from 'react'

export default function ThinkingLog({ logs }: { logs: string[] }) {
  return (
    <div className="space-y-2">
      {logs.map((l, i) => (
        <div key={i} className="text-sm text-gray-700">{l}</div>
      ))}
    </div>
  )
}
