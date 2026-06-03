/* Report viewer placeholder
- Renders the final report and export buttons.
*/

import React from 'react'

export default function ReportPage({ params }: { params: { id: string } }) {
  return (
    <div className="p-6">
      <h2 className="text-2xl">Report {params.id}</h2>
      <div>Report content will be rendered here.</div>
    </div>
  )
}
