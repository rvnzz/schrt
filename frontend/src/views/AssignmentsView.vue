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
  DialogTrigger,
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
  code: string
  group_id: number
  deadline: string | null
  is_hard_deadline: boolean
  max_file_size_mb: number
}

const assignments = ref<Assignment[]>([])
const groups = ref<Group[]>([])
const open = ref(false)
const loading = ref(false)

const form = ref({
  title: '',
  description: '',
  group_id: '',
  deadline: '',
  is_hard_deadline: false,
  max_file_size_mb: 10,
})

async function fetchData() {
  try {
    const [a, g] = await Promise.all([api.get('/assignments'), api.get('/groups')])
    assignments.value = a.data
    groups.value = g.data
  } catch (err) {
    toast.error(getErrorMessage(err))
  }
}

async function createAssignment() {
  loading.value = true
  try {
    await api.post('/assignments', {
      title: form.value.title,
      description: form.value.description || null,
      group_id: Number(form.value.group_id),
      deadline: form.value.deadline || null,
      is_hard_deadline: form.value.is_hard_deadline,
      max_file_size_mb: Number(form.value.max_file_size_mb),
    })
    open.value = false
    form.value = {
      title: '',
      description: '',
      group_id: '',
      deadline: '',
      is_hard_deadline: false,
      max_file_size_mb: 10,
    }
    await fetchData()
    toast.success('Задание создано')
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
      <Dialog v-model:open="open">
        <DialogTrigger as-child>
          <Button>Создать задание</Button>
        </DialogTrigger>
        <DialogContent class="max-w-lg">
          <DialogHeader>
            <DialogTitle>Новое задание</DialogTitle>
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
            <div class="grid gap-2">
              <Label>Макс. размер файла (МБ)</Label>
              <Input type="number" min="1" v-model="form.max_file_size_mb" />
            </div>
          </div>
          <DialogFooter>
            <Button @click="createAssignment" :disabled="loading || !form.title || !form.group_id">Создать</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>

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
            <Button variant="destructive" size="sm" @click="deleteAssignment(assignment.id)">Удалить</Button>
          </div>
        </CardHeader>
        <CardContent class="space-y-2">
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
    </div>
  </div>
</template>
