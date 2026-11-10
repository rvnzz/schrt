<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ArrowDown, ArrowUp, ArrowUpDown } from 'lucide-vue-next'
import { api, getErrorMessage } from '@/lib/api'
import { formatDate, triggerDownload } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import AssignmentBriefDialog from '@/components/AssignmentBriefDialog.vue'
import { toast } from 'vue-sonner'

interface Group {
  id: number
  name: string
}

interface GroupMember {
  first_name: string
  last_name: string
}

interface Submission {
  id: number
  first_name: string
  last_name: string
  original_filename: string
  file_size: number
  submitted_at: string
  is_late: boolean
  is_group_work: boolean
  group_members: GroupMember[] | null
  ai_status: string
  ai_grade: number | null
  ai_feedback: string | null
  ai_error: string | null
  ai_review_reason: string | null
  ai_attempts: number
}

interface AssignmentDetail {
  id: number
  title: string
  description: string | null
  code: string
  group_id: number
  group: Group
  deadline: string | null
  is_hard_deadline: boolean
  allow_group_submissions: boolean
  brief_md: string | null
  max_file_size_mb: number
  submissions: Submission[]
}

const route = useRoute()
const assignmentId = Number(route.params.id)
const assignment = ref<AssignmentDetail | null>(null)
const link = ref('')
const expandedFeedback = ref<Record<number, boolean>>({})
const briefOpen = ref(false)
type SubmissionSortField = 'last_name' | 'submitted_at' | 'ai_grade' | 'file_size'
const submissionSort = ref<{ field: SubmissionSortField; dir: 'asc' | 'desc' }>({
  field: 'last_name',
  dir: 'asc',
})
let pollInterval: number | null = null

const sortedSubmissions = computed(() => {
  const submissions = [...(assignment.value?.submissions ?? [])]
  const direction = submissionSort.value.dir === 'asc' ? 1 : -1
  return submissions.sort((a, b) => {
    switch (submissionSort.value.field) {
      case 'submitted_at':
        return direction * (new Date(a.submitted_at).getTime() - new Date(b.submitted_at).getTime())
      case 'ai_grade':
        return direction * ((a.ai_grade ?? -1) - (b.ai_grade ?? -1) || a.last_name.localeCompare(b.last_name, 'ru'))
      case 'file_size':
        return direction * (a.file_size - b.file_size || a.last_name.localeCompare(b.last_name, 'ru'))
      default:
        return direction * (a.last_name.localeCompare(b.last_name, 'ru') || a.first_name.localeCompare(b.first_name, 'ru'))
    }
  })
})

function sortBySubmission(field: SubmissionSortField) {
  if (submissionSort.value.field === field) {
    submissionSort.value = { field, dir: submissionSort.value.dir === 'asc' ? 'desc' : 'asc' }
  } else {
    submissionSort.value = { field, dir: field === 'submitted_at' || field === 'file_size' ? 'desc' : 'asc' }
  }
}

function submissionSortIcon(field: SubmissionSortField) {
  if (submissionSort.value.field !== field) return ArrowUpDown
  return submissionSort.value.dir === 'asc' ? ArrowUp : ArrowDown
}

function hasPendingGrading(): boolean {
  return assignment.value?.submissions.some((s) => s.ai_status === 'pending') ?? false
}

async function fetchAssignment() {
  try {
    const [assignmentResponse, linkResponse] = await Promise.all([
      api.get(`/assignments/${assignmentId}`),
      api.get(`/assignments/${assignmentId}/link`),
    ])
    assignment.value = assignmentResponse.data
    link.value = linkResponse.data.link
    if (hasPendingGrading()) {
      startPolling()
    }
  } catch (err) {
    toast.error(getErrorMessage(err))
  }
}

async function downloadSingle(submissionId: number, filename: string) {
  try {
    const response = await api.get(`/submissions/${submissionId}/download`, {
      responseType: 'blob',
    })
    triggerDownload(response.data, filename)
  } catch (err) {
    toast.error(getErrorMessage(err))
  }
}

async function downloadAll() {
  try {
    const response = await api.get(`/submissions/assignments/${assignmentId}/download-all`, {
      responseType: 'blob',
    })
    triggerDownload(response.data, `assignment_${assignmentId}_submissions.zip`)
  } catch (err) {
    toast.error(getErrorMessage(err))
  }
}

async function gradeAll() {
  if (!assignment.value?.brief_md) {
    // Без текста задания проверять нечем — сразу предлагаем его добавить
    briefOpen.value = true
    return
  }
  try {
    await api.post(`/assignments/${assignmentId}/grade-all`)
    toast.success('Проверка всех работ запущена')
    await fetchAssignment()
  } catch (err) {
    toast.error(getErrorMessage(err))
  }
}

async function gradeSubmission(submissionId: number) {
  try {
    await api.post(`/submissions/${submissionId}/grade`)
    toast.success('Перепроверка запущена')
    await fetchAssignment()
  } catch (err) {
    toast.error(getErrorMessage(err))
  }
}

function toggleFeedback(submissionId: number) {
  expandedFeedback.value[submissionId] = !expandedFeedback.value[submissionId]
}

async function exportGradesCsv() {
  try {
    const response = await api.get(`/assignments/${assignmentId}/grades-csv`, {
      responseType: 'blob',
    })
    triggerDownload(response.data, `assignment_${assignmentId}_grades.csv`)
  } catch (err) {
    toast.error(getErrorMessage(err))
  }
}

function copyLink() {
  navigator.clipboard.writeText(link.value)
  toast.success('Ссылка скопирована')
}

function formatBytes(bytes: number) {
  if (bytes === 0) return '0 Bytes'
  const k = 1024
  const sizes = ['Bytes', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

function formatGroupMembers(submission: Submission): string {
  if (!submission.is_group_work || !submission.group_members) return '—'
  return submission.group_members.map((m) => `${m.first_name} ${m.last_name}`).join(', ')
}

function aiStatusText(status: string): string {
  const map: Record<string, string> = {
    pending: 'Проверяется…',
    done: 'Готово',
    error: 'Ошибка',
    // Модель не нашла обязательные материалы — оценку она не поставила
    manual_review: 'Ручная проверка',
    disabled: '—',
  }
  return map[status] || status
}

function startPolling() {
  if (pollInterval) return
  pollInterval = window.setInterval(() => {
    if (hasPendingGrading()) {
      fetchAssignment()
    } else {
      stopPolling()
    }
  }, 5000)
}

function stopPolling() {
  if (pollInterval) {
    clearInterval(pollInterval)
    pollInterval = null
  }
}

onMounted(async () => {
  await fetchAssignment()
  if (hasPendingGrading()) {
    startPolling()
  }
})

onUnmounted(stopPolling)
</script>

<template>
  <div v-if="assignment" class="space-y-6">
    <div class="flex items-start justify-between">
      <div>
        <h1 class="text-3xl font-bold">{{ assignment.title }}</h1>
        <p class="text-muted-foreground">Группа: {{ assignment.group.name }}</p>
      </div>
      <div class="flex flex-wrap gap-2">
        <Button variant="outline" as-child>
          <router-link to="/grading">Проблемы AI-проверки</router-link>
        </Button>
        <Button variant="outline" @click="downloadAll">Скачать все работы</Button>
      </div>
    </div>

    <Card>
      <CardHeader>
        <CardTitle>Ссылка для сдачи</CardTitle>
        <CardDescription>Поделитесь этой ссылкой со студентами</CardDescription>
      </CardHeader>
      <CardContent>
        <div class="flex items-center gap-2">
          <code class="flex-1 rounded bg-muted px-3 py-2 text-sm">{{ link }}</code>
          <Button variant="secondary" @click="copyLink">Копировать</Button>
        </div>
      </CardContent>
    </Card>

    <Card>
      <CardHeader>
        <CardTitle>Параметры</CardTitle>
      </CardHeader>
      <CardContent class="space-y-2 text-sm">
        <p>
          Дедлайн: {{ formatDate(assignment.deadline) }}
          <span v-if="assignment.is_hard_deadline" class="ml-2 text-destructive">(жёсткий)</span>
        </p>
        <p>Групповая сдача: {{ assignment.allow_group_submissions ? 'разрешена' : 'нет' }}</p>
        <p>Макс. размер файла: {{ assignment.max_file_size_mb }} МБ</p>
        <p v-if="assignment.description">Описание: {{ assignment.description }}</p>
      </CardContent>
    </Card>

    <Card>
      <CardHeader>
        <div class="flex items-center justify-between gap-2 flex-wrap">
          <div>
            <CardTitle>Сданные работы ({{ assignment.submissions.length }})</CardTitle>
            <CardDescription>
              У каждого студента должен быть свой файл. Если работы сдавали вместе — участники перечислены в колонке «Участники».
            </CardDescription>
          </div>
          <div class="flex items-center gap-2">
            <Button variant="outline" size="sm" @click="gradeAll">
              {{ assignment.brief_md ? 'Проверить все работы AI' : 'Добавить текст задания и проверить' }}
            </Button>
            <Button
              variant="outline"
              size="sm"
              @click="exportGradesCsv"
            >
              Экспорт оценок AI (CSV)
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>
                <button type="button" class="inline-flex items-center gap-1" @click="sortBySubmission('last_name')">
                  Фамилия
                  <component :is="submissionSortIcon('last_name')" class="h-3.5 w-3.5" />
                </button>
              </TableHead>
              <TableHead>Имя</TableHead>
              <TableHead>Файл</TableHead>
              <TableHead>
                <button type="button" class="inline-flex items-center gap-1" @click="sortBySubmission('file_size')">
                  Размер
                  <component :is="submissionSortIcon('file_size')" class="h-3.5 w-3.5" />
                </button>
              </TableHead>
              <TableHead>
                <button type="button" class="inline-flex items-center gap-1" @click="sortBySubmission('submitted_at')">
                  Время
                  <component :is="submissionSortIcon('submitted_at')" class="h-3.5 w-3.5" />
                </button>
              </TableHead>
              <TableHead>Статус</TableHead>
              <TableHead>Участники</TableHead>
              <TableHead>
                <button type="button" class="inline-flex items-center gap-1" @click="sortBySubmission('ai_grade')">
                  Оценка AI
                  <component :is="submissionSortIcon('ai_grade')" class="h-3.5 w-3.5" />
                </button>
              </TableHead>
              <TableHead>Комментарий AI</TableHead>
              <TableHead class="text-right">Действия</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow v-for="sub in sortedSubmissions" :key="sub.id">
              <TableCell>{{ sub.last_name }}</TableCell>
              <TableCell>{{ sub.first_name }}</TableCell>
              <TableCell>{{ sub.original_filename }}</TableCell>
              <TableCell>{{ formatBytes(sub.file_size) }}</TableCell>
              <TableCell>{{ formatDate(sub.submitted_at) }}</TableCell>
              <TableCell>
                <Badge v-if="sub.is_late" variant="destructive">Просрочено</Badge>
                <Badge v-else variant="default">Вовремя</Badge>
              </TableCell>
              <TableCell>
                <Badge v-if="sub.is_group_work" variant="secondary">Групповая</Badge>
                <span class="text-sm text-muted-foreground">{{ formatGroupMembers(sub) }}</span>
              </TableCell>
              <TableCell>
                <Badge
                  v-if="sub.ai_status === 'done'"
                  :variant="sub.ai_grade && sub.ai_grade >= 4 ? 'default' : 'destructive'"
                >
                  {{ sub.ai_grade }}
                </Badge>
                <Badge v-else-if="sub.ai_status === 'pending'" variant="outline">{{ aiStatusText(sub.ai_status) }}</Badge>
                <Badge v-else-if="sub.ai_status === 'error'" variant="destructive">{{ aiStatusText(sub.ai_status) }}</Badge>
                <Badge v-else-if="sub.ai_status === 'manual_review'" variant="secondary">
                  {{ aiStatusText(sub.ai_status) }}
                </Badge>
                <span v-else class="text-muted-foreground">{{ aiStatusText(sub.ai_status) }}</span>
              </TableCell>
              <TableCell>
                <div v-if="sub.ai_status === 'error' && sub.ai_error" class="max-w-xs">
                  <p class="text-xs text-destructive">{{ sub.ai_error }}</p>
                  <p v-if="sub.ai_attempts" class="mt-1 text-xs text-muted-foreground">
                    попыток: {{ sub.ai_attempts }}
                  </p>
                </div>
                <div v-else-if="sub.ai_review_reason" class="max-w-xs">
                  <p class="text-xs text-amber-600 dark:text-amber-500">{{ sub.ai_review_reason }}</p>
                  <p v-if="sub.ai_feedback" class="mt-1 text-xs text-muted-foreground">
                    {{ sub.ai_feedback }}
                  </p>
                </div>
                <div v-else-if="sub.ai_feedback" class="max-w-xs">
                  <div
                    :class="[
                      'text-sm text-muted-foreground',
                      !expandedFeedback[sub.id] && 'line-clamp-2',
                    ]"
                  >
                    {{ sub.ai_feedback }}
                  </div>
                  <button
                    type="button"
                    class="mt-1 text-xs text-primary hover:underline"
                    @click="toggleFeedback(sub.id)"
                  >
                    {{ expandedFeedback[sub.id] ? 'Свернуть' : 'Развернуть' }}
                  </button>
                </div>
                <span v-else class="text-sm text-muted-foreground">—</span>
              </TableCell>
              <TableCell class="text-right">
                <div class="flex justify-end gap-2">
                  <Button variant="outline" size="sm" @click="gradeSubmission(sub.id)">Перепроверить</Button>
                  <Button variant="outline" size="sm" @click="downloadSingle(sub.id, sub.original_filename)">Скачать</Button>
                </div>
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </CardContent>
    </Card>

    <AssignmentBriefDialog
      v-model:open="briefOpen"
      :assignment-id="assignmentId"
      :assignment-title="assignment.title"
      @saved="fetchAssignment()"
    />
  </div>
</template>
