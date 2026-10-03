<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { onClickOutside } from '@vueuse/core'
import { useRoute } from 'vue-router'
import { api, getErrorMessage } from '@/lib/api'
import { formatDate } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Upload } from 'lucide-vue-next'
import { toast } from 'vue-sonner'

interface Student {
  id: number
  first_name: string
  last_name: string
}

interface SubmitInfoData {
  title: string
  description: string | null
  deadline: string | null
  is_hard_deadline: boolean
  max_file_size_mb: number
  allowed_extensions: string[] | null
  students: Student[]
  is_closed: boolean
}

const route = useRoute()
const code = route.params.code as string
const info = ref<SubmitInfoData | null>(null)
const firstName = ref('')
const lastName = ref('')
const file = ref<File | null>(null)
const loading = ref(false)
const success = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)
const firstWrapper = ref<HTMLDivElement | null>(null)
const lastWrapper = ref<HTMLDivElement | null>(null)
const showFirstSuggestions = ref(false)
const showLastSuggestions = ref(false)
const isDragging = ref(false)

const firstNameSuggestions = computed(() => {
  if (!info.value) return []
  const term = firstName.value.trim().toLowerCase()
  if (!term) return []
  return info.value.students.filter((s) => s.first_name.toLowerCase().startsWith(term))
})

const lastNameSuggestions = computed(() => {
  if (!info.value) return []
  const term = lastName.value.trim().toLowerCase()
  if (!term) return []
  return info.value.students.filter((s) => s.last_name.toLowerCase().startsWith(term))
})

onClickOutside(firstWrapper, () => {
  showFirstSuggestions.value = false
})

onClickOutside(lastWrapper, () => {
  showLastSuggestions.value = false
})

async function fetchInfo() {
  try {
    const response = await api.get(`/submit/${code}`)
    info.value = response.data
  } catch (err) {
    toast.error(getErrorMessage(err))
  }
}

function selectStudent(student: Student) {
  firstName.value = student.first_name
  lastName.value = student.last_name
  showFirstSuggestions.value = false
  showLastSuggestions.value = false
}

function onFileChange(event: Event) {
  const target = event.target as HTMLInputElement
  setFile(target.files?.[0] || null)
}

function setFile(selected: File | null) {
  file.value = selected
}

function handleDragOver(event: DragEvent) {
  event.preventDefault()
  isDragging.value = true
}

function handleDragLeave(event: DragEvent) {
  event.preventDefault()
  isDragging.value = false
}

function handleDrop(event: DragEvent) {
  event.preventDefault()
  isDragging.value = false
  const dropped = event.dataTransfer?.files?.[0]
  if (dropped) {
    setFile(dropped)
  }
}

function openFilePicker() {
  fileInput.value?.click()
}

async function onSubmit() {
  if (!file.value) {
    toast.error('Выберите файл')
    return
  }
  if (!firstName.value.trim() || !lastName.value.trim()) {
    toast.error('Укажите имя и фамилию')
    return
  }

  const formData = new FormData()
  formData.append('first_name', firstName.value.trim())
  formData.append('last_name', lastName.value.trim())
  formData.append('file', file.value)

  loading.value = true
  try {
    await api.post(`/submit/${code}`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    success.value = true
  } catch (err) {
    toast.error(getErrorMessage(err))
  } finally {
    loading.value = false
  }
}

onMounted(fetchInfo)
</script>

<template>
  <div class="flex items-center justify-center py-12">
    <Card v-if="info" class="w-full max-w-md">
      <CardHeader>
        <CardTitle>{{ info.title }}</CardTitle>
        <CardDescription v-if="info.description">{{ info.description }}</CardDescription>
      </CardHeader>
      <CardContent class="space-y-4">
        <div class="space-y-1 text-sm">
          <p>
            Дедлайн: {{ formatDate(info.deadline) }}
            <span v-if="info.is_hard_deadline" class="ml-2 text-destructive">(жёсткий)</span>
          </p>
          <p>Макс. размер файла: {{ info.max_file_size_mb }} МБ</p>
        </div>

        <Badge v-if="info.is_closed" variant="destructive">Приём работ закрыт</Badge>

        <div v-if="success" class="rounded-md bg-green-50 p-4 text-green-800">
          Работа успешно сдана!
        </div>

        <form v-else @submit.prevent="onSubmit" class="space-y-4">
          <div ref="firstWrapper" class="grid gap-2 relative">
            <Label for="firstName">Имя</Label>
            <Input id="firstName" v-model="firstName" autocomplete="off" @focus="showFirstSuggestions = true" />
            <ul v-if="showFirstSuggestions && firstNameSuggestions.length" class="absolute top-full z-10 mt-1 w-full rounded-md border bg-popover shadow-sm">
              <li
                v-for="student in firstNameSuggestions"
                :key="student.id"
                class="cursor-pointer px-3 py-2 text-sm hover:bg-accent"
                @mousedown.prevent="selectStudent(student)"
              >
                {{ student.first_name }} {{ student.last_name }}
              </li>
            </ul>
          </div>

          <div ref="lastWrapper" class="grid gap-2 relative">
            <Label for="lastName">Фамилия</Label>
            <Input id="lastName" v-model="lastName" autocomplete="off" @focus="showLastSuggestions = true" />
            <ul v-if="showLastSuggestions && lastNameSuggestions.length" class="absolute top-full z-10 mt-1 w-full rounded-md border bg-popover shadow-sm">
              <li
                v-for="student in lastNameSuggestions"
                :key="student.id"
                class="cursor-pointer px-3 py-2 text-sm hover:bg-accent"
                @mousedown.prevent="selectStudent(student)"
              >
                {{ student.last_name }} {{ student.first_name }}
              </li>
            </ul>
          </div>

          <div class="grid gap-2">
            <Label for="file">Файл</Label>
            <div
              role="button"
              tabindex="0"
              class="flex min-h-[120px] cursor-pointer flex-col items-center justify-center rounded-md border border-dashed border-input bg-background px-4 py-6 text-sm text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
              :class="{ 'border-primary bg-primary/5 text-primary': isDragging }"
              @dragover="handleDragOver"
              @dragleave="handleDragLeave"
              @drop="handleDrop"
              @click="openFilePicker"
              @keydown.enter="openFilePicker"
            >
              <template v-if="file">
                <p class="font-medium text-foreground">{{ file.name }}</p>
                <p class="text-xs">{{ (file.size / 1024 / 1024).toFixed(2) }} МБ</p>
              </template>
              <template v-else>
                <Upload class="mb-2 h-8 w-8" />
                <p>Перетащите файл сюда или нажмите для выбора</p>
                <p class="text-xs">Максимум {{ info.max_file_size_mb }} МБ</p>
              </template>
            </div>
            <Input id="file" type="file" class="hidden" ref="fileInput" @change="onFileChange" />
          </div>

          <Button type="submit" class="w-full" :disabled="loading || info.is_closed">
            {{ loading ? 'Отправка...' : 'Сдать работу' }}
          </Button>
        </form>
      </CardContent>
    </Card>
  </div>
</template>
