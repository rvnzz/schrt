export type AiProblemKind =
  | 'error'
  | 'manual_review'
  | 'no_brief'
  | 'not_queued'
  | 'stale_pending'
  | 'ai_off'

export interface AiProblemRow {
  submission_id: number
  assignment_id: number
  assignment_title: string
  assignment_code: string
  group_id: number
  group_name: string
  student: string
  original_filename: string
  submitted_at: string
  status: string
  kind: AiProblemKind
  kind_label: string
  reason: string
  attempts: number
  age_seconds: number | null
  has_brief: boolean
  fixable_by_brief: boolean
  retryable: boolean
  /** Работу увели человеку: AI не нашёл обязательных материалов */
  manual_review: boolean
}

/** done-работа, в комментарии которой AI пожаловался на недостающие скриншоты. */
export interface AiEvidenceRow {
  submission_id: number
  assignment_id: number
  assignment_title: string
  group_id: number
  group_name: string
  student: string
  original_filename: string
  grade: number | null
  hint: string
  submitted_at: string
}

export interface AiAssignmentRow {
  id: number
  title: string
  code: string
  group_id: number
  group_name: string
  deadline: string | null
  has_brief: boolean
  brief_chars: number
  submissions_total: number
  status_counts: Record<string, number>
  problem_counts: Record<AiProblemKind, number>
  problems_total: number
  avg_grade: number | null
  grades: Record<string, number>
  graded_total: number
  oldest_pending_seconds: number | null
  last_checked_at: string | null
}

export interface AiLowGradeRow {
  submission_id: number
  assignment_id: number
  assignment_title: string
  group_name: string
  student: string
  original_filename: string
  grade: number
  feedback: string
  submitted_at: string
}

export interface AiOverview {
  ai_enabled: boolean
  model: string
  worker_poll_seconds: number
  stale_minutes: number
  generated_at: string
  totals: Record<string, number>
  problems_by_kind: Record<AiProblemKind, number>
  problems_total: number
  assignments: AiAssignmentRow[]
  problems: AiProblemRow[]
  low_grades: AiLowGradeRow[]
  /** Проверенные работы, где AI написал, что не нашёл материалы */
  missing_evidence: { count: number; items: AiEvidenceRow[] }
}

export const KIND_OPTIONS: Array<{ value: AiProblemKind | 'all'; label: string }> = [
  { value: 'all', label: 'Все проблемы' },
  { value: 'error', label: 'Ошибка проверки' },
  { value: 'manual_review', label: 'Нужна ручная проверка' },
  { value: 'no_brief', label: 'Нет текста задания' },
  { value: 'not_queued', label: 'Не поставлено в очередь' },
  { value: 'stale_pending', label: 'Давно в очереди' },
  { value: 'ai_off', label: 'AI не настроен' },
]

/** «3 ч 20 мин», «5 мин», «2 сут 4 ч» — для возраста сдачи и ожидания в очереди. */
export function formatDuration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return '—'
  if (seconds < 60) return `${seconds} с`
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes} мин`
  const hours = Math.floor(minutes / 60)
  const restMinutes = minutes % 60
  if (hours < 24) return restMinutes ? `${hours} ч ${restMinutes} мин` : `${hours} ч`
  const days = Math.floor(hours / 24)
  return `${days} дн ${hours % 24} ч`
}
