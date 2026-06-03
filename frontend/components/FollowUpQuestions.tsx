import React from 'react'

export default function FollowUpQuestions({ questions }: { questions: string[] }) {
  return (
    <ul className="list-disc pl-6">
      {questions.map((q, i) => (
        <li key={i}>{q}</li>
      ))}
    </ul>
  )
}
