<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ArrowDownUp, Search, Users, ClipboardList } from 'lucide-vue-next'
import { api, getErrorMessage } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
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
import { toast } from 'vue-sonner'

interface Group {
  id: number
  name: string
  created_at: string
  student_count: number
  assignment_count: number
}

type SortField = 'name' | 'students' | 'assignments' | 'created'

const SORT_STORAGE_KEY = 'groups.sort'
const SORT_LABELS: Record<SortField, string> = {
  name: 'По названию',
  students: 'По числу студентов',
  assignments: 'По числу заданий',
  created: 'По дате создания',
}

const groups = ref<Group[]>([])
const newName = ref('')
const loading = ref(false)
const open = ref(false)
const search = ref('')
const sortField = ref<SortField>(readStoredSort())
const sortDesc = ref(false)

function readStoredSort(): SortField {
  const stored = localStorage.getItem(SORT_STORAGE_KEY)
  return stored === 'name' || stored === 'students' || stored === 'assignments' || stored === 'created'
    ? stored
    : 'name'
}

watch(sortField, (value) => localStorage.setItem(SORT_STORAGE_KEY, value))

async function fetchGroups() {
  try {
    const response = await api.get('/groups')
    groups.value = response.data
  } catch (err) {
    toast.error(getErrorMessage(err))
  }
}

const visibleGroups = computed(() => {
  const term = search.value.trim().toLowerCase()
  const filtered = term
    ? groups.value.filter((group) => group.name.toLowerCase().includes(term))
    : [...groups.value]

  const direction = sortDesc.value ? -1 : 1
  return filtered.sort((a, b) => {
    switch (sortField.value) {
      case 'students':
        return direction * (a.student_count - b.student_count || a.name.localeCompare(b.name, 'ru'))
      case 'assignments':
        return direction * (a.assignment_count - b.assignment_count || a.name.localeCompare(b.name, 'ru'))
      case 'created':
        return direction * (new Date(a.created_at).getTime() - new Date(b.created_at).getTime())
      default:
        return direction * a.name.localeCompare(b.name, 'ru')
    }
  })
})

async function createGroup() {
  if (!newName.value.trim()) return
  loading.value = true
  try {
    await api.post('/groups', { name: newName.value.trim() })
    newName.value = ''
    open.value = false
    await fetchGroups()
    toast.success('Группа создана')
  } catch (err) {
    toast.error(getErrorMessage(err))
  } finally {
    loading.value = false
  }
}

async function deleteGroup(id: number) {
  if (!confirm('Удалить группу?')) return
  try {
    await api.delete(`/groups/${id}`)
    await fetchGroups()
    toast.success('Группа удалена')
  } catch (err) {
    toast.error(getErrorMessage(err))
  }
}

onMounted(fetchGroups)
</script>

<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between gap-2 flex-wrap">
      <h1 class="text-3xl font-bold">Группы</h1>
      <Dialog v-model:open="open">
        <DialogTrigger as-child>
          <Button>Создать группу</Button>
        </DialogTrigger>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Новая группа</DialogTitle>
            <DialogDescription>Введите название группы</DialogDescription>
          </DialogHeader>
          <div class="grid gap-4 py-4">
            <div class="grid gap-2">
              <Label for="name">Название</Label>
              <Input id="name" v-model="newName" />
            </div>
          </div>
          <DialogFooter>
            <Button @click="createGroup" :disabled="loading">Создать</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>

    <div class="flex flex-wrap items-end gap-3">
      <div class="grid min-w-[220px] flex-1 gap-1.5">
        <Label for="groupSearch">Поиск</Label>
        <div class="relative">
          <Search class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input id="groupSearch" v-model="search" class="pl-9" placeholder="Название группы" />
        </div>
      </div>
      <div class="grid w-56 gap-1.5">
        <Label for="groupSort">Сортировка</Label>
        <Select v-model="sortField">
          <SelectTrigger id="groupSort">
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
    </div>

    <p class="text-sm text-muted-foreground">
      Показано групп: {{ visibleGroups.length }} из {{ groups.length }}
    </p>

    <div class="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
      <Card v-for="group in visibleGroups" :key="group.id">
        <CardHeader>
          <div class="flex items-start justify-between gap-2">
            <CardTitle>{{ group.name }}</CardTitle>
            <div class="flex gap-1.5">
              <Badge variant="secondary" class="gap-1">
                <Users class="h-3 w-3" />
                {{ group.student_count }}
              </Badge>
              <Badge variant="secondary" class="gap-1">
                <ClipboardList class="h-3 w-3" />
                {{ group.assignment_count }}
              </Badge>
            </div>
          </div>
          <CardDescription>
            <router-link :to="`/groups/${group.id}`" class="text-primary hover:underline">
              Открыть
            </router-link>
          </CardDescription>
        </CardHeader>
        <CardContent class="flex gap-2">
          <Button variant="outline" size="sm" as-child>
            <router-link :to="`/groups/${group.id}`">Управление</router-link>
          </Button>
          <Button variant="destructive" size="sm" @click="deleteGroup(group.id)">Удалить</Button>
        </CardContent>
      </Card>
    </div>
  </div>
</template>
