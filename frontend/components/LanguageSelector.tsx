import React from 'react'

export default function LanguageSelector({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)} className="p-2 border rounded">
      <option value="english">English</option>
      <option value="hindi">Hindi</option>
      <option value="spanish">Spanish</option>
    </select>
  )
}
