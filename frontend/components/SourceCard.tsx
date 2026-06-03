import React from 'react'

export default function SourceCard({ title, url, credibility }: { title: string; url: string; credibility: string }) {
  return (
    <div className="p-3 border rounded">
      <a href={url} className="font-semibold text-blue-600">{title}</a>
      <div className="text-sm text-gray-500">{credibility}</div>
    </div>
  )
}
