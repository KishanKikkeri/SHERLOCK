import { Sparkles } from 'lucide-react'

export function SuggestedQuestions({
  questions,
  onSelect,
  disabled,
}: {
  questions: string[]
  onSelect: (question: string) => void
  disabled?: boolean
}) {
  if (questions.length === 0) return null

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <Sparkles className="h-3.5 w-3.5 text-muted" aria-hidden />
      {questions.map((q) => (
        <button
          key={q}
          type="button"
          disabled={disabled}
          onClick={() => onSelect(q)}
          className="rounded-full border border-border bg-surface px-2.5 py-1 text-xs text-muted transition-colors hover:border-accent/40 hover:text-accent disabled:pointer-events-none disabled:opacity-50"
        >
          {q}
        </button>
      ))}
    </div>
  )
}
