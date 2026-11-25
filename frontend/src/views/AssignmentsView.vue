<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ArrowDownUp } from 'lucide-vue-next'
import { api, getErrorMessage } from '@/lib/api'
import { formatDate } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Textarea } from '@/components/ui/textarea'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Checkbox } from '@/components/ui/checkbox'
import { toast } from 'vue-sonner'

interface Group {
  id: number
  name: string
}

interface Assignment {
  id: number
  title: string
  description: string | null
  code: string
  group_id: number
  deadline: string | null
  is_hard_deadline: boolean
  allow_group_submissions: boolean
  brief_md: string | null
  max_file_size_mb: number
  created_at: string
}

type SortField = 'group' | 'title' | 'deadline' | 'created'

const SORT_LABELS: Record<SortField, string> = {
  group: 'По группам',
  title: 'По названию',
  deadline: 'По дедлайну',
  created: 'По дате создания',
}

const assignments = ref<Assignment[]>([])
const groups = ref<Group[]>([])
const isOpen = ref(false)
const loading = ref(false)
const editingAssignment = ref<Assignment | null>(null)
const storedSort = localStorage.getItem('assignments.sort')
const sortField = ref<SortField>(
  storedSort === 'group' || storedSort === 'title' || storedSort === 'deadline' || storedSort === 'created'
    ? storedSort
    : 'group'
)
const sortDesc = ref(localStorage.getItem('assignments.sortDesc') === 'desc')
const groupFilter = ref<string>(localStorage.getItem('assignments.group') || 'all')

const form = ref({
  title: '',
  description: '',
  group_id: '',
  deadline: '',
  is_hard_deadline: false,
  allow_group_submissions: false,
  brief_md: '',
  max_file_size_mb: 10,
})
const briefMdFile = ref<HTMLInputElement | null>(null)

function resetForm() {
  form.value = {
    title: '',
    description: '',
    group_id: '',
    deadline: '',
    is_hard_deadline: false,
    allow_group_submissions: false,
    brief_md: '',
    max_file_size_mb: 10,
  }
  if (briefMdFile.value) {
    briefMdFile.value.value = ''
  }
}

function populateForm(assignment: Assignment) {
  form.value = {
    title: assignment.title,
    description: assignment.description || '',
    group_id: String(assignment.group_id),
    deadline: assignment.deadline ? assignment.deadline.slice(0, 16) : '',
    is_hard_deadline: assignment.is_hard_deadline,
    allow_group_submissions: assignment.allow_group_submissions,
    brief_md: assignment.brief_md || '',
    max_file_size_mb: assignment.max_file_size_mb,
  }
}

function onBriefMdFileChange(event: Event) {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]
  if (!file) return
  const reader = new FileReader()
  reader.onload = () => {
    form.value.brief_md = String(reader.result || '')
  }
  reader.readAsText(file)
}

async function fetchData() {
  try {
    const [a, g] = await Promise.all([api.get('/assignments'), api.get('/groups')])
    assignments.value = a.data
    groups.value = g.data
    // Группа из сохранённого фильтра могла быть удалена — возвращаем «все»
    if (
      groupFilter.value !== 'all' &&
      !groups.value.some((group) => String(group.id) === groupFilter.value)
    ) {
      groupFilter.value = 'all'
    }
  } catch (err) {
    toast.error(getErrorMessage(err))
  }
}

function openCreateModal() {
  editingAssignment.value = null
  resetForm()
  isOpen.value = true
}

function openEditModal(assignment: Assignment) {
  editingAssignment.value = assignment
  populateForm(assignment)
  isOpen.value = true
}

async function saveAssignment() {
  loading.value = true
  const payload: any = {
    title: form.value.title,
    description: form.value.description || null,
    group_id: Number(form.value.group_id),
    deadline: form.value.deadline || null,
    is_hard_deadline: form.value.is_hard_deadline,
    allow_group_submissions: form.value.allow_group_submissions,
    max_file_size_mb: Number(form.value.max_file_size_mb),
  }
  if (form.value.brief_md.trim()) {
    payload.brief_md = form.value.brief_md.trim()
  }

  try {
    if (editingAssignment.value) {
      await api.patch(`/assignments/${editingAssignment.value.id}`, payload)
      toast.success('Задание обновлено')
    } else {
      await api.post('/assignments', payload)
      toast.success('Задание создано')
    }
    isOpen.value = false
    resetForm()
    editingAssignment.value = null
    await fetchData()
  } catch (err) {
    toast.error(getErrorMessage(err))
  } finally {
    loading.value = false
  }
}

async function deleteAssignment(id: number) {
  if (!confirm('Удалить задание?')) return
  try {
    await api.delete(`/assignments/${id}`)
    await fetchData()
    toast.success('Задание удалено')
  } catch (err) {
    toast.error(getErrorMessage(err))
  }
}

function groupName(id: number) {
  return groups.value.find((g) => g.id === id)?.name || '—'
}

const sortedGroups = computed(() =>
  [...groups.value].sort((a, b) => a.name.localeCompare(b.name, 'ru'))
)

const visibleAssignments = computed(() => {
  const direction = sortDesc.value ? -1 : 1
  const filtered =
    groupFilter.value === 'all'
      ? [...assignments.value]
      : assignments.value.filter((assignment) => assignment.group_id === Number(groupFilter.value))

  return filtered.sort((a, b) => {
    switch (sortField.value) {
      case 'title':
        return direction * a.title.localeCompare(b.title, 'ru')
      case 'deadline': {
        const left = a.deadline ? new Date(a.deadline).getTime() : Number.POSITIVE_INFINITY
        const right = b.deadline ? new Date(b.deadline).getTime() : Number.POSITIVE_INFINITY
        return direction * (left - right || groupName(a.group_id).localeCompare(groupName(b.group_id), 'ru'))
      }
      case 'created':
        return direction * (new Date(a.created_at).getTime() - new Date(b.created_at).getTime())
      default:
        return (
          direction * (
            groupName(a.group_id).localeCompare(groupName(b.group_id), 'ru') ||
            a.title.localeCompare(b.title, 'ru')
          )
        )
    }
  })
})

watch(sortField, (value) => localStorage.setItem('assignments.sort', value))
watch(sortDesc, (value) => localStorage.setItem('assignments.sortDesc', value ? 'desc' : 'asc'))
watch(groupFilter, (value) => localStorage.setItem('assignments.group', value))

onMounted(fetchData)
</script>

<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <h1 class="text-3xl font-bold">Задания</h1>
      <Button @click="openCreateModal">Создать задание</Button>
    </div>

    <div class="flex flex-wrap items-end gap-3">
      <div class="grid w-56 gap-1.5">
        <Label for="assignmentGroup">Группа</Label>
        <Select v-model="groupFilter">
          <SelectTrigger id="assignmentGroup">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Все группы</SelectItem>
            <SelectItem v-for="group in sortedGroups" :key="group.id" :value="String(group.id)">
              {{ group.name }}
            </SelectItem>
          </SelectContent>
        </Select>
      </div>
      <div class="grid w-56 gap-1.5">
        <Label for="assignmentSort">Сортировка</Label>
        <Select v-model="sortField">
          <SelectTrigger id="assignmentSort">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem v-for="(label, field) in SORT_LABELS" :key="field" :value="field">
              {{ label }}
            </SelectItem>
          </SelectContent>
        </Select>
      </div>
      <Button variant="outline" @click="sortDesc = !sortDesc" :title="sortDesc ? 'Сортировать по возрастанию' : 'Сортировать по убыванию'">
        <ArrowDownUp class="mr-2 h-4 w-4" />
        {{ sortDesc ? 'По убыванию' : 'По возрастанию' }}
      </Button>
      <p class="text-sm text-muted-foreground">
        Показано заданий: {{ visibleAssignments.length }} из {{ assignments.length }}
      </p>
    </div>

    <Dialog v-model:open="isOpen">
      <DialogContent class="max-w-lg">
        <DialogHeader>
          <DialogTitle>{{ editingAssignment ? 'Редактировать задание' : 'Новое задание' }}</DialogTitle>
          <DialogDescription>Заполните данные задания</DialogDescription>
        </DialogHeader>
          <div class="grid gap-4 py-4">
            <div class="grid gap-2">
              <Label>Название</Label>
              <Input v-model="form.title" />
            </div>
            <div class="grid gap-2">
              <Label>Описание</Label>
              <Textarea v-model="form.description" />
            </div>
            <div class="grid gap-2">
              <Label>Группа</Label>
              <Select v-model="form.group_id">
                <SelectTrigger>
                  <SelectValue placeholder="Выберите группу" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem v-for="group in sortedGroups" :key="group.id" :value="String(group.id)">
                    {{ group.name }}
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div class="grid gap-2">
              <Label>Дедлайн</Label>
              <Input type="datetime-local" v-model="form.deadline" />
            </div>
            <div class="flex items-center gap-2">
              <Checkbox id="hardDeadline" v-model="form.is_hard_deadline" />
              <Label for="hardDeadline" class="text-sm font-normal">Жёсткий дедлайн (блокировать сдачу после дедлайна)</Label>
            </div>
            <div class="flex items-center gap-2">
              <Checkbox id="allowGroup" v-model="form.allow_group_submissions" />
              <Label for="allowGroup" class="text-sm font-normal">Разрешить групповую сдачу</Label>
            </div>
            <div class="grid gap-2">
              <Label>Текст задания для AI (markdown)</Label>
              <Textarea v-model="form.brief_md" rows="6" placeholder="Введите markdown или загрузите .md файл" />
              <input type="file" accept=".md,.markdown" ref="briefMdFile" @change="onBriefMdFileChange" class="block w-full text-sm text-muted-foreground file:mr-4 file:rounded file:border-0 file:bg-secondary file:px-3 file:py-2 file:text-sm file:font-medium" />
            </div>
            <div class="grid gap-2">
              <Label>Макс. размер файла (МБ)</Label>
              <Input type="number" min="1" v-model="form.max_file_size_mb" />
            </div>
          </div>
          <DialogFooter>
            <Button @click="saveAssignment" :disabled="loading || !form.title || !form.group_id">
              {{ editingAssignment ? 'Сохранить' : 'Создать' }}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

    <div class="grid gap-4">
      <Card v-for="assignment in visibleAssignments" :key="assignment.id">
        <CardHeader>
          <div class="flex items-start justify-between">
            <div>
              <CardTitle>{{ assignment.title }}</CardTitle>
              <CardDescription>
                Группа: {{ groupName(assignment.group_id) }} | Код: {{ assignment.code }}
              </CardDescription>
            </div>
            <div class="flex gap-2">
              <Button variant="outline" size="sm" @click="openEditModal(assignment)">Редактировать</Button>
              <Button variant="destructive" size="sm" @click="deleteAssignment(assignment.id)">Удалить</Button>
            </div>
          </div>
        </CardHeader>
        <CardContent class="space-y-2">
          <div class="flex flex-wrap items-center gap-2">
            <Badge variant="secondary">{{ groupName(assignment.group_id) }}</Badge>
            <Badge v-if="assignment.allow_group_submissions" variant="outline">Групповая сдача</Badge>
          </div>
          <p class="text-sm">
            Дедлайн: {{ formatDate(assignment.deadline) }}
            <span v-if="assignment.is_hard_deadline" class="ml-2 text-destructive">(жёсткий)</span>
          </p>
          <p class="text-sm">Макс. размер: {{ assignment.max_file_size_mb }} МБ</p>
          <Button variant="outline" size="sm" as-child>
            <router-link :to="`/assignments/${assignment.id}`">Подробнее</router-link>
          </Button>
        </CardContent>
      </Card>

      <p v-if="!visibleAssignments.length" class="text-sm text-muted-foreground">
        {{ assignments.length ? 'В выбранной группе пока нет заданий.' : 'Заданий ещё нет — создайте первое.' }}
      </p>
    </div>
  </div>
</template>
