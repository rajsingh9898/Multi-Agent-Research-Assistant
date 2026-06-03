/* Research progress page placeholder
- Shows live agent updates via WebSocket for a running report.
*/

import React from 'react'

export default function ResearchPage({ params }: { params: { id: string } }) {
  return (
    <div className="p-6">
      <h2 className="text-2xl">Research {params.id}</h2>
      <p>Live updates will show here.</p>
    </div>
  )
}
