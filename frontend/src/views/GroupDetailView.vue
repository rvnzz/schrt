<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ArrowDown, ArrowUp, ArrowUpDown, Search } from 'lucide-vue-next'
import { api, getErrorMessage } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { toast } from 'vue-sonner'

interface Submission {
  student_id: number | null
  submitted_at: string
  is_late: boolean
  ai_status: string
  ai_grade: number | null
}

interface Assignment {
  id: number
  title: string
  code: string
  created_at: string
  submissions: Submission[]
}

interface Student {
  id: number
  first_name: string
  last_name: string
  is_auto_added: boolean
}

interface GroupDetail {
  id: number
  name: string
  students: Student[]
  assignments: Assignment[]
}

type SortField = 'last_name' | 'first_name' | 'submitted' | 'average'
type SortDir = 'asc' | 'desc'

const route = useRoute()
const groupId = Number(route.params.id)
const group = ref<GroupDetail | null>(null)
const fileInput = ref<HTMLInputElement | null>(null)
const search = ref('')
const source = ref<'all' | 'imported' | 'auto'>('all')
const sort = ref<{ field: SortField; dir: SortDir }>({ field: 'last_name', dir: 'asc' })

const sortedAssignments = computed(() =>
  [...(group.value?.assignments ?? [])].sort(
    (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
  )
)

function latestSubmission(studentId: number, assignment: Assignment): Submission | null {
  const own = assignment.submissions.filter((sub) => sub.student_id === studentId)
  if (!own.length) return null
  return own.reduce((acc, sub) => (new Date(sub.submitted_at) >= new Date(acc.submitted_at) ? sub : acc))
}

function submittedCount(studentId: number): number {
  return sortedAssignments.value.filter((assignment) => latestSubmission(studentId, assignment)).length
}

function grades(studentId: number): number[] {
  const list: number[] = []
  for (const assignment of sortedAssignments.value) {
    const grade = latestSubmission(studentId, assignment)?.ai_grade
    if (grade !== null && grade !== undefined) list.push(grade)
  }
  return list
}

function averageGrade(studentId: number): number | null {
  const list = grades(studentId)
  if (!list.length) return null
  return Math.round((list.reduce((sum, grade) => sum + grade, 0) / list.length) * 100) / 100
}

const visibleStudents = computed(() => {
  const bySource =
    source.value === 'all'
      ? (group.value?.students ?? [])
      : (group.value?.students ?? []).filter((student) =>
          source.value === 'auto' ? student.is_auto_added : !student.is_auto_added
        )

  const students = [...bySource]
  const term = search.value.trim().toLowerCase()
  const filtered = term
    ? students.filter((student) =>
        `${student.last_name} ${student.first_name}`.toLowerCase().includes(term)
      )
    : students
  const direction = sort.value.dir === 'asc' ? 1 : -1

  return filtered.sort((a, b) => {
    switch (sort.value.field) {
      case 'first_name':
        return direction * (a.first_name.localeCompare(b.first_name, 'ru') || a.last_name.localeCompare(b.last_name, 'ru'))
      case 'submitted':
        return direction * (submittedCount(a.id) - submittedCount(b.id) || a.last_name.localeCompare(b.last_name, 'ru'))
      case 'average':
        return direction * ((averageGrade(a.id) ?? -1) - (averageGrade(b.id) ?? -1) || a.last_name.localeCompare(b.last_name, 'ru'))
      default:
        return direction * (a.last_name.localeCompare(b.last_name, 'ru') || a.first_name.localeCompare(b.first_name, 'ru'))
    }
  })
})

const autoAddedCount = computed(
  () => (group.value?.students ?? []).filter((student) => student.is_auto_added).length
)

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

async function fetchGroup() {
  try {
    const response = await api.get(`/groups/${groupId}`)
    group.value = response.data
  } catch (err) {
    toast.error(getErrorMessage(err))
  }
}

async function handleCsvUpload(event: Event) {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]
  if (!file) return

  const formData = new FormData()
  formData.append('file', file)

  try {
    await api.post(`/groups/${groupId}/students/import`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    toast.success('Студенты импортированы')
    await fetchGroup()
  } catch (err) {
    toast.error(getErrorMessage(err))
  } finally {
    if (fileInput.value) fileInput.value.value = ''
  }
}

async function deleteStudent(studentId: number) {
  if (!confirm('Удалить студента?')) return
  try {
    await api.delete(`/groups/${groupId}/students/${studentId}`)
    await fetchGroup()
    toast.success('Студент удалён')
  } catch (err) {
    toast.error(getErrorMessage(err))
  }
}

function cellValue(studentId: number, assignment: Assignment): string {
  const submission = latestSubmission(studentId, assignment)
  if (!submission) return '—'
  const mark = submission.is_late ? '⚠️' : '✅'
  return submission.ai_grade !== null && submission.ai_grade !== undefined
    ? `${mark} ${submission.ai_grade}`
    : mark
}

function assignmentsCount() {
  return sortedAssignments.value.length
}

onMounted(fetchGroup)
</script>

<template>
  <div v-if="group" class="space-y-6">
    <div class="flex items-start justify-between gap-3 flex-wrap">
      <div>
        <h1 class="text-3xl font-bold">{{ group.name }}</h1>
        <p class="text-muted-foreground">
          Студентов: {{ group.students.length }} · Заданий: {{ assignmentsCount() }}
        </p>
      </div>
    </div>

    <Card>
      <CardHeader>
        <CardTitle>Студенты</CardTitle>
        <CardDescription>
          Загрузите список из CSV — или не загружайте: сдающие студенты добавляются в группу автоматически
        </CardDescription>
      </CardHeader>
      <CardContent class="space-y-4">
        <div class="flex items-end gap-4 flex-wrap">
          <div class="grid gap-2">
            <Label for="csv">CSV файл</Label>
            <Input id="csv" type="file" accept=".csv" ref="fileInput" @change="handleCsvUpload" />
          </div>
          <div class="relative min-w-[200px] flex-1">
            <Search class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input v-model="search" class="pl-9" placeholder="Поиск по фамилии или имени" />
          </div>
          <div class="grid w-52 gap-2">
            <Label for="sourceFilter">Кто в списке</Label>
            <Select v-model="source">
              <SelectTrigger id="sourceFilter">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Все ({{ group.students.length }})</SelectItem>
                <SelectItem value="imported">Из CSV ({{ group.students.length - autoAddedCount }})</SelectItem>
                <SelectItem value="auto">Из сдач ({{ autoAddedCount }})</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>
                <button type="button" class="inline-flex items-center gap-1" @click="sortBy('last_name')">
                  Фамилия
                  <component :is="sortIcon('last_name')" class="h-3.5 w-3.5" />
                </button>
              </TableHead>
              <TableHead>
                <button type="button" class="inline-flex items-center gap-1" @click="sortBy('first_name')">
                  Имя
                  <component :is="sortIcon('first_name')" class="h-3.5 w-3.5" />
                </button>
              </TableHead>
              <TableHead>
                <button type="button" class="inline-flex items-center gap-1" @click="sortBy('submitted')">
                  Сдано
                  <component :is="sortIcon('submitted')" class="h-3.5 w-3.5" />
                </button>
              </TableHead>
              <TableHead>
                <button type="button" class="inline-flex items-center gap-1" @click="sortBy('average')">
                  Средний балл
                  <component :is="sortIcon('average')" class="h-3.5 w-3.5" />
                </button>
              </TableHead>
              <TableHead class="text-right">Действия</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow v-for="student in visibleStudents" :key="student.id">
              <TableCell>
                <span class="inline-flex items-center gap-2">
                  {{ student.last_name }}
                  <Badge v-if="student.is_auto_added" variant="outline" class="text-xs">из сдачи</Badge>
                </span>
              </TableCell>
              <TableCell>{{ student.first_name }}</TableCell>
              <TableCell>{{ submittedCount(student.id) }} из {{ assignmentsCount() }}</TableCell>
              <TableCell>
                <Badge v-if="averageGrade(student.id) !== null" :variant="averageGrade(student.id)! >= 4 ? 'default' : 'secondary'">
                  {{ averageGrade(student.id) }}
                </Badge>
                <span v-else class="text-sm text-muted-foreground">—</span>
              </TableCell>
              <TableCell class="text-right">
                <Button variant="destructive" size="sm" @click="deleteStudent(student.id)">Удалить</Button>
              </TableCell>
            </TableRow>
            <TableRow v-if="!visibleStudents.length">
              <TableCell :colspan="5" class="text-sm text-muted-foreground">
                Никого не нашли — измените запрос или фильтр. Список появится сам, когда студенты начнут сдавать работы.
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </CardContent>
    </Card>

    <Card>
      <CardHeader>
        <div class="flex items-center justify-between gap-2 flex-wrap">
          <div>
            <CardTitle>Таблица сдач и оценок</CardTitle>
            <CardDescription>Студенты × задания: отметка о сдаче и оценка AI</CardDescription>
          </div>
          <p class="text-sm text-muted-foreground">
            Порядок студентов: {{ sort.field === 'last_name' ? 'фамилия' : sort.field === 'first_name' ? 'имя' : sort.field === 'submitted' ? 'сдачи' : 'средний балл' }} ({{ sort.dir === 'asc' ? 'по возрастанию' : 'по убыванию' }})
          </p>
        </div>
      </CardHeader>
      <CardContent>
        <div class="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>
                  <button type="button" class="inline-flex items-center gap-1" @click="sortBy('last_name')">
                    Фамилия
                    <component :is="sortIcon('last_name')" class="h-3.5 w-3.5" />
                  </button>
                </TableHead>
                <TableHead>
                  <button type="button" class="inline-flex items-center gap-1" @click="sortBy('first_name')">
                    Имя
                    <component :is="sortIcon('first_name')" class="h-3.5 w-3.5" />
                  </button>
                </TableHead>
                <TableHead v-for="assignment in sortedAssignments" :key="assignment.id">
                  <router-link :to="`/assignments/${assignment.id}`" class="text-primary hover:underline">
                    {{ assignment.title }}
                  </router-link>
                </TableHead>
                <TableHead>Средний балл</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow v-for="student in visibleStudents" :key="student.id">
                <TableCell>{{ student.last_name }}</TableCell>
                <TableCell>{{ student.first_name }}</TableCell>
                <TableCell v-for="assignment in sortedAssignments" :key="assignment.id">
                  {{ cellValue(student.id, assignment) }}
                </TableCell>
                <TableCell>{{ averageGrade(student.id) ?? '—' }}</TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </div>
        <p class="mt-3 text-xs text-muted-foreground">
          ✅ — сдано вовремя, ⚠️ — сдано позже дедлайна, — работу не сдавали. Число рядом с отметкой — оценка AI.
        </p>
      </CardContent>
    </Card>
  </div>
  <div v-else class="text-sm text-muted-foreground">Загрузка группы…</div>
</template>
