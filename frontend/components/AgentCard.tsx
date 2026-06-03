import React from 'react'

export default function AgentCard({ name, status }: { name: string; status?: string }) {
  return (
    <div className="p-4 border rounded">
      <h3 className="font-semibold">{name}</h3>
      <div className="text-sm text-gray-500">{status || 'idle'}</div>
    </div>
  )
}
