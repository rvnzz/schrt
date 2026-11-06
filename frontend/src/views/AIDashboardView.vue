<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { ArrowDown, ArrowUp, ArrowUpDown, RefreshCw, RotateCcw, Sparkles } from 'lucide-vue-next'
import { api, getErrorMessage } from '@/lib/api'
import { formatDate } from '@/lib/utils'
import {
  formatDuration,
  KIND_OPTIONS,
  type AiAssignmentRow,
  type AiOverview,
  type AiProblemKind,
  type AiProblemRow,
} from '@/lib/ai'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import AssignmentBriefDialog from '@/components/AssignmentBriefDialog.vue'
import { toast } from 'vue-sonner'

type SortField = 'kind' | 'age' | 'student' | 'group'

const KIND_ORDER: Record<AiProblemKind, number> = {
  error: 0,
  no_brief: 1,
  not_queued: 2,
  stale_pending: 3,
  ai_off: 4,
}

const overview = ref<AiOverview | null>(null)
const loading = ref(false)
const busy = ref('')
const groupFilter = ref('all')
const kindFilter = ref<AiProblemKind | 'all'>('all')
const search = ref('')
const sort = ref<{ field: SortField; dir: 'asc' | 'desc' }>({ field: 'kind', dir: 'asc' })
const briefOpen = ref(false)
const briefAssignment = ref<{ id: number; title: string } | null>(null)
let pollTimer: number | null = null

const groups = computed(() => {
  const map = new Map<number, string>()
  for (const row of overview.value?.assignments ?? []) map.set(row.group_id, row.group_name)
  return [...map.entries()].sort((a, b) => a[1].localeCompare(b[1], 'ru'))
})

const cards = computed(() => {
  const data = overview.value
  if (!data) return []
  return [
    {
      key: 'done',
      label: 'Проверено AI',
      value: data.totals.done ?? 0,
      hint: data.problems_total ? '' : 'Все работы проверены',
      kind: null as AiProblemKind | null,
    },
    {
      key: 'pending',
      label: 'В очереди',
      value: data.totals.pending ?? 0,
      hint: data.totals.pending ? 'ждут ответа модели' : 'очередь пуста',
      kind: 'stale_pending' as AiProblemKind,
    },
    {
      key: 'error',
      label: 'Ошибки проверки',
      value: data.problems_by_kind.error ?? 0,
      hint: 'упал запрос к AI или ответ не разобрался',
      kind: 'error' as AiProblemKind,
    },
    {
      key: 'no_brief',
      label: 'Без текста задания',
      value: data.problems_by_kind.no_brief ?? 0,
      hint: `не поставлено в очередь: ${data.problems_by_kind.not_queued ?? 0}`,
      kind: 'no_brief' as AiProblemKind,
    },
  ]
})

const visibleProblems = computed(() => {
  const term = search.value.trim().toLowerCase()
  const rows = (overview.value?.problems ?? []).filter((row) => {
    if (groupFilter.value !== 'all' && String(row.group_id) !== groupFilter.value) return false
    if (kindFilter.value !== 'all' && row.kind !== kindFilter.value) return false
    if (
      term &&
      !`${row.group_name} ${row.assignment_title} ${row.student} ${row.original_filename}`
        .toLowerCase()
        .includes(term)
    ) {
      return false
    }
    return true
  })

  const direction = sort.value.dir === 'asc' ? 1 : -1
  return [...rows].sort((a, b) => {
    switch (sort.value.field) {
      case 'age':
        return direction * ((a.age_seconds ?? 0) - (b.age_seconds ?? 0))
      case 'student':
        return direction * a.student.localeCompare(b.student, 'ru')
      case 'group':
        return direction * (a.group_name.localeCompare(b.group_name, 'ru') || a.assignment_title.localeCompare(b.assignment_title, 'ru'))
      default:
        return (
          direction *
          (KIND_ORDER[a.kind] - KIND_ORDER[b.kind] || (b.age_seconds ?? 0) - (a.age_seconds ?? 0))
        )
    }
  })
})

const assignmentsWithProblems = computed(
  () => (overview.value?.assignments ?? []).filter((row) => row.problems_total > 0)
)

const gradedAssignments = computed(() =>
  (overview.value?.assignments ?? []).filter((row) => row.graded_total > 0)
)

async function fetchOverview(silent = false) {
  if (!silent) loading.value = true
  try {
    const response = await api.get<AiOverview>('/ai/overview', {
      params: { stale_minutes: 15, problem_limit: 500 },
    })
    overview.value = response.data
    if (response.data.totals.pending > 0) startPolling()
    else stopPolling()
  } catch (err) {
    if (!silent) toast.error(getErrorMessage(err))
  } finally {
    loading.value = false
  }
}

function startPolling() {
  if (pollTimer) return
  pollTimer = window.setInterval(() => fetchOverview(true), 10000)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

async function retryAllErrors() {
  busy.value = 'all'
  try {
    const response = await api.post('/ai/enqueue', { scope: 'all_errors', limit: 100 })
    toast.success(`В очередь поставлено работ: ${response.data.enqueued}`)
    await fetchOverview(true)
  } catch (err) {
    toast.error(getErrorMessage(err))
  } finally {
    busy.value = ''
  }
}

async function retrySubmission(submissionId: number, busyKey: string) {
  busy.value = busyKey
  try {
    const response = await api.post('/ai/enqueue', { submission_ids: [submissionId] })
    if (response.data.enqueued) toast.success('Работа поставлена в очередь')
    else toast.error('Работу нельзя проверить: у задания нет текста для AI')
    await fetchOverview(true)
  } catch (err) {
    toast.error(getErrorMessage(err))
  } finally {
    busy.value = ''
  }
}

function retryRow(row: AiProblemRow) {
  return retrySubmission(row.submission_id, String(row.submission_id))
}

function openBrief(assignment: AiProblemRow) {
  briefAssignment.value = { id: assignment.assignment_id, title: assignment.assignment_title }
  briefOpen.value = true
}

function openBriefByRow(assignment: { id: number; title: string }) {
  briefAssignment.value = assignment
  briefOpen.value = true
}

function sortBy(field: SortField) {
  if (sort.value.field === field) {
    sort.value = { field, dir: sort.value.dir === 'asc' ? 'desc' : 'asc' }
  } else {
    sort.value = { field, dir: 'asc' }
  }
}

function sortIcon(field: SortField) {
  if (sort.value.field !== field) return ArrowUpDown
  return sort.value.dir === 'asc' ? ArrowUp : ArrowDown
}

function kindBadge(kind: AiProblemKind) {
  if (kind === 'error') return 'destructive'
  if (kind === 'ai_off') return 'destructive'
  if (kind === 'no_brief' || kind === 'not_queued') return 'secondary'
  return 'outline'
}

function gradeShare(row: AiAssignmentRow, grade: string) {
  if (!row.graded_total) return 0
  return Math.round(((row.grades[grade] ?? 0) / row.graded_total) * 100)
}

onMounted(() => fetchOverview())
onUnmounted(stopPolling)
</script>

<template>
  <div class="space-y-6">
    <div class="flex items-start justify-between gap-3 flex-wrap">
      <div>
        <h1 class="text-3xl font-bold">AI-проверка</h1>
        <p class="text-muted-foreground">
          Что не проверилось и почему, с быстрым текстом задания
          <span v-if="overview">· модель {{ overview.model }} · опрос каждые {{ overview.worker_poll_seconds }} с</span>
        </p>
      </div>
      <div class="flex flex-wrap gap-2">
        <Button variant="outline" :disabled="loading" @click="fetchOverview()">
          <RefreshCw class="mr-2 h-4 w-4" />
          Обновить
        </Button>
        <Button
          :disabled="!overview?.problems_by_kind?.error || busy === 'all'"
          @click="retryAllErrors"
        >
          <RotateCcw class="mr-2 h-4 w-4" />
          Повторить все ошибки
        </Button>
      </div>
    </div>

    <Card v-if="overview && !overview.ai_enabled" class="border-destructive/50 bg-destructive/10">
      <CardContent class="flex items-start gap-3 pt-6">
        <Sparkles class="mt-0.5 h-5 w-5 text-destructive" />
        <div class="space-y-1 text-sm">
          <p class="font-medium text-destructive">AI-проверка не настроена</p>
          <p class="text-muted-foreground">
            В контейнере не задан <code class="rounded bg-muted px-1">OPENCODE_GO_API_KEY</code>, поэтому
            работы не уходят агенту: непроверенных — {{ overview.problems_total }}. Текст задания можно
            заполнить уже сейчас, проверка включится после добавления ключа.
          </p>
        </div>
      </CardContent>
    </Card>

    <div v-if="overview" class="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      <button
        v-for="card in cards"
        :key="card.key"
        type="button"
        class="rounded-md border bg-card p-4 text-left transition-colors hover:bg-accent"
        :class="{ 'ring-2 ring-ring': kindFilter === card.kind && card.kind !== null }"
        @click="kindFilter = card.kind ?? 'all'"
      >
        <p class="text-sm text-muted-foreground">{{ card.label }}</p>
        <p class="mt-1 text-3xl font-semibold">{{ card.value }}</p>
        <p class="mt-1 text-xs text-muted-foreground">{{ card.hint }}</p>
      </button>
    </div>

    <Card>
      <CardHeader>
        <div class="flex items-start justify-between gap-2 flex-wrap">
          <div>
            <CardTitle>Проблемные работы ({{ visibleProblems.length }})</CardTitle>
            <CardDescription>
              Отсортировано по важности: сначала то, что чинится текстом задания или повтором
            </CardDescription>
          </div>
          <p v-if="overview && overview.problems_total > overview.problems.length" class="text-xs text-muted-foreground">
            Всего проблем {{ overview.problems_total }}, показаны первые {{ overview.problems.length }}
          </p>
        </div>
        <div class="mt-3 flex flex-wrap items-end gap-3">
          <div class="relative min-w-[200px] flex-1">
            <Input v-model="search" placeholder="Поиск: группа, задание, студент, файл" />
          </div>
          <div class="grid w-48 gap-1.5">
            <Label for="problemGroup">Группа</Label>
            <Select v-model="groupFilter">
              <SelectTrigger id="problemGroup">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Все группы</SelectItem>
                <SelectItem v-for="[id, name] in groups" :key="id" :value="String(id)">
                  {{ name }}
                </SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div class="grid w-52 gap-1.5">
            <Label for="problemKind">Проблема</Label>
            <Select v-model="kindFilter">
              <SelectTrigger id="problemKind">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem v-for="option in KIND_OPTIONS" :key="option.value" :value="option.value">
                  {{ option.label }}
                </SelectItem>
              </SelectContent>
            </Select>
          </div>
          <Button variant="outline" size="sm" @click="groupFilter = 'all'; kindFilter = 'all'; search = ''">
            Сбросить
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>
                <button type="button" class="inline-flex items-center gap-1" @click="sortBy('group')">
                  Группа / задание
                  <component :is="sortIcon('group')" class="h-3.5 w-3.5" />
                </button>
              </TableHead>
              <TableHead>
                <button type="button" class="inline-flex items-center gap-1" @click="sortBy('student')">
                  Студент
                  <component :is="sortIcon('student')" class="h-3.5 w-3.5" />
                </button>
              </TableHead>
              <TableHead>Файл</TableHead>
              <TableHead>
                <button type="button" class="inline-flex items-center gap-1" @click="sortBy('age')">
                  Ждёт
                  <component :is="sortIcon('age')" class="h-3.5 w-3.5" />
                </button>
              </TableHead>
              <TableHead>
                <button type="button" class="inline-flex items-center gap-1" @click="sortBy('kind')">
                  Проблема
                  <component :is="sortIcon('kind')" class="h-3.5 w-3.5" />
                </button>
              </TableHead>
              <TableHead>Причина</TableHead>
              <TableHead class="text-right">Действия</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow v-for="row in visibleProblems" :key="row.submission_id">
              <TableCell>
                <p class="font-medium">{{ row.group_name }}</p>
                <router-link
                  :to="`/assignments/${row.assignment_id}`"
                  class="text-sm text-primary hover:underline"
                >
                  {{ row.assignment_title }}
                </router-link>
              </TableCell>
              <TableCell>{{ row.student }}</TableCell>
              <TableCell class="max-w-[160px] truncate text-sm">{{ row.original_filename }}</TableCell>
              <TableCell class="text-sm">{{ formatDuration(row.age_seconds) }}</TableCell>
              <TableCell>
                <Badge :variant="kindBadge(row.kind)">{{ row.kind_label }}</Badge>
                <p v-if="row.attempts" class="mt-1 text-xs text-muted-foreground">попыток: {{ row.attempts }}</p>
              </TableCell>
              <TableCell>
                <p v-if="row.reason" class="max-w-xs break-words text-xs text-muted-foreground">{{ row.reason }}</p>
                <span v-else class="text-xs text-muted-foreground">—</span>
              </TableCell>
              <TableCell class="text-right">
                <div class="flex flex-col items-end gap-1">
                  <Button
                    v-if="row.fixable_by_brief"
                    size="sm"
                    @click="openBrief(row)"
                  >
                    Добавить текст задания
                  </Button>
                  <Button
                    v-else-if="row.retryable"
                    variant="outline"
                    size="sm"
                    :disabled="busy === String(row.submission_id)"
                    @click="retryRow(row)"
                  >
                    {{ row.kind === 'error' ? 'Перепроверить' : 'В очередь' }}
                  </Button>
                  <span v-else class="text-xs text-muted-foreground">
                    {{ row.kind === 'ai_off' ? 'нужен API-ключ' : 'воркер сам подхватит' }}
                  </span>
                  <router-link
                    :to="`/assignments/${row.assignment_id}`"
                    class="text-xs text-primary hover:underline"
                  >
                    открыть задание
                  </router-link>
                </div>
              </TableCell>
            </TableRow>
            <TableRow v-if="!visibleProblems.length">
              <TableCell :colspan="7" class="text-sm text-muted-foreground">
                {{ overview?.problems_total ? 'Под фильтр ничего не попало.' : 'Все сданные работы проверены — проблем нет.' }}
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </CardContent>
    </Card>

    <Card v-if="assignmentsWithProblems.length">
      <CardHeader>
        <CardTitle>Задания с проблемами</CardTitle>
        <CardDescription>Текст задания можно заполнить прямо здесь — непроверенные работы сразу уйдут в очередь</CardDescription>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Группа</TableHead>
              <TableHead>Задание</TableHead>
              <TableHead>Работ</TableHead>
              <TableHead>Текст для AI</TableHead>
              <TableHead>Проблемы</TableHead>
              <TableHead class="text-right">Действия</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow v-for="row in assignmentsWithProblems" :key="row.id">
              <TableCell>{{ row.group_name }}</TableCell>
              <TableCell>
                <router-link :to="`/assignments/${row.id}`" class="text-primary hover:underline">
                  {{ row.title }}
                </router-link>
              </TableCell>
              <TableCell>{{ row.submissions_total }}</TableCell>
              <TableCell>
                <Badge v-if="row.has_brief" variant="secondary">{{ row.brief_chars }} симв.</Badge>
                <Badge v-else variant="destructive">не задан</Badge>
              </TableCell>
              <TableCell class="text-sm text-muted-foreground">
                <span v-if="row.problem_counts.error">ошибок: {{ row.problem_counts.error }} · </span>
                <span v-if="row.problem_counts.no_brief">без текста: {{ row.problem_counts.no_brief }} · </span>
                <span v-if="row.problem_counts.not_queued">не в очереди: {{ row.problem_counts.not_queued }} · </span>
                <span v-if="row.problem_counts.stale_pending">зависло: {{ row.problem_counts.stale_pending }} · </span>
                <span v-if="row.problem_counts.ai_off">AI выключен: {{ row.problem_counts.ai_off }} · </span>
              </TableCell>
              <TableCell class="text-right">
                <Button size="sm" variant="outline" @click="openBriefByRow(row)">
                  Текст задания
                </Button>
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </CardContent>
    </Card>

    <div class="grid gap-6 lg:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle>Распределение оценок</CardTitle>
          <CardDescription>По заданиям, где AI уже поставил хотя бы одну оценку</CardDescription>
        </CardHeader>
        <CardContent class="space-y-4">
          <div v-for="row in gradedAssignments" :key="row.id" class="space-y-1">
            <div class="flex items-center justify-between gap-2 text-sm">
              <router-link :to="`/assignments/${row.id}`" class="truncate font-medium hover:underline">
                {{ row.group_name }} · {{ row.title }}
              </router-link>
              <span class="text-muted-foreground">
                среднее {{ row.avg_grade ?? '—' }} · оценок {{ row.graded_total }}
              </span>
            </div>
            <div class="flex h-2 overflow-hidden rounded bg-muted">
              <div
                v-for="grade in ['5', '4', '3', '2']"
                :key="grade"
                class="h-full"
                :class="{
                  'bg-primary': grade === '5' || grade === '4',
                  'bg-destructive': grade === '3' || grade === '2',
                }"
                :style="{ width: `${gradeShare(row, grade)}%` }"
                :title="`${grade} — ${row.grades[grade] ?? 0}`"
              />
            </div>
            <p class="text-xs text-muted-foreground">
              5: {{ row.grades['5'] ?? 0 }} · 4: {{ row.grades['4'] ?? 0 }} · 3: {{ row.grades['3'] ?? 0 }} · 2: {{ row.grades['2'] ?? 0 }}
            </p>
          </div>
          <p v-if="!gradedAssignments.length" class="text-sm text-muted-foreground">
            Оценок пока нет — сначала появится текст задания у сдач.
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Оценки 2 и 3 — нужен человеческий взгляд</CardTitle>
          <CardDescription>Их стоит перепроверить вручную: модель часто занижает за формат ответа</CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Студент</TableHead>
                <TableHead>Задание</TableHead>
                <TableHead>Оценка</TableHead>
                <TableHead class="text-right">Действия</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow v-for="row in overview?.low_grades.slice(0, 15) ?? []" :key="row.submission_id">
                <TableCell>
                  <p>{{ row.student }}</p>
                  <p class="text-xs text-muted-foreground">{{ row.group_name }}</p>
                </TableCell>
                <TableCell class="text-sm">{{ row.assignment_title }}</TableCell>
                <TableCell>
                  <Badge variant="destructive">{{ row.grade }}</Badge>
                </TableCell>
                <TableCell class="text-right">
                  <Button
                    variant="outline"
                    size="sm"
                    :disabled="busy === `low-${row.submission_id}`"
                    @click="retrySubmission(row.submission_id, `low-${row.submission_id}`)"
                  >
                    Перепроверить
                  </Button>
                </TableCell>
              </TableRow>
              <TableRow v-if="!overview?.low_grades.length">
                <TableCell :colspan="4" class="text-sm text-muted-foreground">Двоек и троек нет.</TableCell>
              </TableRow>
            </TableBody>
          </Table>
          <p v-if="(overview?.low_grades.length ?? 0) > 15" class="mt-2 text-xs text-muted-foreground">
            Показаны первые 15 из {{ overview?.low_grades.length }}
          </p>
        </CardContent>
      </Card>
    </div>

    <p v-if="overview" class="text-xs text-muted-foreground">
      Данные на {{ formatDate(overview.generated_at) }}
      <span v-if="overview.totals.pending"> · автообновление включено, пока в очереди есть работы</span>
    </p>

    <AssignmentBriefDialog
      v-model:open="briefOpen"
      :assignment-id="briefAssignment?.id ?? null"
      :assignment-title="briefAssignment?.title"
      @saved="fetchOverview(true)"
    />
  </div>
</template>
