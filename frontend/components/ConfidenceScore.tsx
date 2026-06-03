import React from 'react'

export default function ConfidenceScore({ value }: { value: number }) {
  return (
    <div className="flex items-center gap-2">
      <div className="font-medium">Confidence:</div>
      <div className="text-lg">{value}%</div>
    </div>
  )
}
