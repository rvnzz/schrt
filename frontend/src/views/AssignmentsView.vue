<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api, getErrorMessage } from '@/lib/api'
import { formatDate } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
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
  max_file_size_mb: number
}

const assignments = ref<Assignment[]>([])
const groups = ref<Group[]>([])
const isOpen = ref(false)
const loading = ref(false)
const editingAssignment = ref<Assignment | null>(null)

const form = ref({
  title: '',
  description: '',
  group_id: '',
  deadline: '',
  is_hard_deadline: false,
  allow_group_submissions: false,
  max_file_size_mb: 10,
})

function resetForm() {
  form.value = {
    title: '',
    description: '',
    group_id: '',
    deadline: '',
    is_hard_deadline: false,
    allow_group_submissions: false,
    max_file_size_mb: 10,
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
    max_file_size_mb: assignment.max_file_size_mb,
  }
}

async function fetchData() {
  try {
    const [a, g] = await Promise.all([api.get('/assignments'), api.get('/groups')])
    assignments.value = a.data
    groups.value = g.data
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
  const payload = {
    title: form.value.title,
    description: form.value.description || null,
    group_id: Number(form.value.group_id),
    deadline: form.value.deadline || null,
    is_hard_deadline: form.value.is_hard_deadline,
    allow_group_submissions: form.value.allow_group_submissions,
    max_file_size_mb: Number(form.value.max_file_size_mb),
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

onMounted(fetchData)
</script>

<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <h1 class="text-3xl font-bold">Задания</h1>
      <Button @click="openCreateModal">Создать задание</Button>
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
                  <SelectItem v-for="group in groups" :key="group.id" :value="String(group.id)">
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
      <Card v-for="assignment in assignments" :key="assignment.id">
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
          <p class="text-sm">
            Дедлайн: {{ formatDate(assignment.deadline) }}
            <span v-if="assignment.is_hard_deadline" class="ml-2 text-destructive">(жёсткий)</span>
          </p>
          <p class="text-sm">
            Групповая сдача: {{ assignment.allow_group_submissions ? 'разрешена' : 'нет' }}
          </p>
          <p class="text-sm">Макс. размер: {{ assignment.max_file_size_mb }} МБ</p>
          <Button variant="outline" size="sm" as-child>
            <router-link :to="`/assignments/${assignment.id}`">Подробнее</router-link>
          </Button>
        </CardContent>
      </Card>
    </div>
  </div>
</template>
