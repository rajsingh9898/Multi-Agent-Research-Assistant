import React from 'react'

export default function ReportViewer({ markdown }: { markdown: string }) {
  return (
    <div className="prose max-w-none">
      {/* Use react-markdown to render the markdown */}
      <pre>{markdown}</pre>
    </div>
  )
}
