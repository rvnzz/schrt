<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { Info, Plus, Trash2, Users } from 'lucide-vue-next'
import { api, getErrorMessage } from '@/lib/api'
import { formatDate } from '@/lib/utils'
import {
  emptyPickedStudent,
  hasExtraWords,
  pluralRu,
  studentFullName,
  type PickedStudent,
  type Student,
} from '@/lib/types'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Checkbox } from '@/components/ui/checkbox'
import { Label } from '@/components/ui/label'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import StudentPicker from '@/components/StudentPicker.vue'
import SubmissionFileDrop from '@/components/SubmissionFileDrop.vue'
import { toast } from 'vue-sonner'

interface SubmitInfoData {
  title: string
  description: string | null
  deadline: string | null
  is_hard_deadline: boolean
  allow_group_submissions: boolean
  max_file_size_mb: number
  allowed_extensions: string[] | null
  students: Student[]
  is_closed: boolean
}

interface WorkRow {
  key: number
  student: PickedStudent
  file: File | null
}

const route = useRoute()
const code = route.params.code as string
const info = ref<SubmitInfoData | null>(null)
const loading = ref(false)
const success = ref(false)
const submittedCount = ref(0)
const autoAdded = ref<string[]>([])
const isGroupWork = ref(false)

let keySeed = 1

function createRow(): WorkRow {
  return { key: keySeed++, student: emptyPickedStudent(), file: null }
}

const rows = ref<WorkRow[]>([createRow()])

const grouped = computed(() => info.value?.allow_group_submissions ?? false)

watch(isGroupWork, (value) => {
  if (value) {
    if (rows.value.length < 2) rows.value.push(createRow())
  } else {
    rows.value = rows.value.slice(0, 1)
  }
})

function addRow() {
  rows.value.push(createRow())
}

function removeRow(index: number) {
  rows.value.splice(index, 1)
  if (isGroupWork.value && rows.value.length < 2) {
    isGroupWork.value = false
  }
}

function validateRows(): string | null {
  for (let index = 0; index < rows.value.length; index += 1) {
    const row = rows.value[index]
    const position = index + 1
    const first = row.student.first_name.trim()
    const last = row.student.last_name.trim()

    if (!first || !last) {
      return `Выберите студента для работы №${position}`
    }
    if (hasExtraWords(first) || hasExtraWords(last)) {
      return `Работа №${position}: имя и фамилия — отдельные поля. Вписывать двух студентов в одно поле не нужно, добавьте их отдельными работами.`
    }
    if (!row.file) {
      return `Прикрепите отдельный файл для ${last} ${first}`
    }
  }

  const seen = new Set<string>()
  for (const row of rows.value) {
    const key = `${row.student.first_name.trim().toLowerCase()} ${row.student.last_name.trim().toLowerCase()}`
    if (seen.has(key)) {
      return `${studentFullName(row.student)} добавлен дважды — у каждого студента должен быть свой файл`
    }
    seen.add(key)
  }

  return null
}

async function fetchInfo() {
  try {
    const response = await api.get(`/submit/${code}`)
    info.value = response.data
  } catch (err) {
    toast.error(getErrorMessage(err))
  }
}

async function onSubmit() {
  if (!filePrecheck()) return

  const formData = new FormData()
  const participants = rows.value.map((row) => ({
    first_name: row.student.first_name.trim(),
    last_name: row.student.last_name.trim(),
  }))
  formData.append('first_name', participants[0].first_name)
  formData.append('last_name', participants[0].last_name)
  formData.append('is_group_work', String(isGroupWork.value))
  formData.append('participants', JSON.stringify(participants))
  rows.value.forEach((row) => formData.append('files', row.file as File))

  loading.value = true
  try {
    const response = await api.post(`/submit/${code}`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    submittedCount.value = response.data?.count ?? participants.length
    autoAdded.value = response.data?.auto_added ?? []
    // Обновляем список группы: сдающие студенты уже добавились в него
    await fetchInfo()
    success.value = true
  } catch (err) {
    toast.error(getErrorMessage(err))
  } finally {
    loading.value = false
  }
}

function filePrecheck(): boolean {
  const error = validateRows()
  if (error) {
    toast.error(error)
    return false
  }
  return true
}

function resetForm() {
  success.value = false
  submittedCount.value = 0
  autoAdded.value = []
  isGroupWork.value = false
  rows.value = [createRow()]
}

const submitLabel = computed(() => {
  if (loading.value) return 'Отправка...'
  if (!isGroupWork.value) return 'Сдать работу'
  return `Сдать ${rows.value.length} ${pluralRu(rows.value.length, 'работу', 'работы', 'работ')}`
})

const successLabel = computed(() => {
  if (submittedCount.value > 1) {
    return `Готово: сдано ${submittedCount.value} ${pluralRu(submittedCount.value, 'работа', 'работы', 'работ')}`
  }
  return 'Работа успешно сдана!'
})

onMounted(fetchInfo)
</script>

<template>
  <div class="flex items-center justify-center py-12">
    <Card v-if="info" class="w-full max-w-2xl">
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
          <p v-if="info.allowed_extensions?.length">Допустимые форматы: {{ info.allowed_extensions.join(', ') }}</p>
        </div>

        <Badge v-if="info.is_closed" variant="destructive">Приём работ закрыт</Badge>

        <div
          class="flex items-start gap-2 rounded-md border bg-muted/40 p-3 text-sm"
        >
          <Info class="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
          <p>
            Прикрепляйте <span class="font-medium">отдельный файл от каждого студента</span>.
            Нельзя вписывать два имени в одно поле и сдавать одну работу на всех —
            каждый участник сдаёт свой файл под своей фамилией.
            Если студента нет в списке группы, впишите имя и фамилию — он добавится в список сам.
          </p>
        </div>

        <div v-if="success" class="rounded-md border border-primary/30 bg-primary/10 p-4 text-sm text-primary">
          <p class="font-medium">{{ successLabel }}</p>
          <p class="mt-1 text-muted-foreground">
            {{ submittedCount > 1 ? 'Файлы отправлены преподавателю по каждому студенту.' : 'Файл отправлен преподавателю.' }}
          </p>
          <p v-if="autoAdded.length" class="mt-1 text-muted-foreground">
            {{ autoAdded.join(', ') }} {{ autoAdded.length > 1 ? 'добавлены' : 'добавлен' }} в список группы автоматически.
          </p>
          <Button variant="outline" size="sm" class="mt-3" @click="resetForm">Сдать ещё работу</Button>
        </div>

        <form v-else @submit.prevent="onSubmit" class="space-y-5">
          <div v-for="(row, index) in rows" :key="row.key" class="space-y-3 rounded-md border p-3">
            <div class="flex items-center justify-between gap-2">
              <p class="text-sm font-medium">
                Работа №{{ index + 1 }}
                <span v-if="index === 0" class="text-muted-foreground">— ваша</span>
                <span v-else class="text-muted-foreground">— участник</span>
              </p>
              <Button
                v-if="index > 0"
                type="button"
                variant="ghost"
                size="sm"
                @click="removeRow(index)"
              >
                <Trash2 class="mr-1 h-3.5 w-3.5" />
                Убрать
              </Button>
            </div>

            <StudentPicker
              v-model="row.student"
              :students="info.students"
              :input-id="`student-${row.key}`"
            />

            <SubmissionFileDrop
              v-model="row.file"
              :input-id="`file-${row.key}`"
              :max-file-size-mb="info.max_file_size_mb"
              :allowed-extensions="info.allowed_extensions"
            />
          </div>

          <template v-if="grouped">
            <div class="flex items-center gap-2">
              <Checkbox id="groupWork" v-model="isGroupWork" />
              <Label for="groupWork" class="text-sm font-normal">
                Делали работу вместе — сдаём файлы каждого участника
              </Label>
            </div>

            <div v-if="isGroupWork" class="space-y-2 rounded-md border border-dashed p-3">
              <div class="flex items-center justify-between gap-2">
                <p class="flex items-center gap-2 text-sm font-medium">
                  <Users class="h-4 w-4 text-muted-foreground" />
                  Участников: {{ rows.length }}
                </p>
                <Button type="button" variant="outline" size="sm" @click="addRow">
                  <Plus class="mr-1 h-4 w-4" />
                  Добавить студента
                </Button>
              </div>
              <p class="text-xs text-muted-foreground">
                Выберите каждого студента из списка группы и прикрепите его файл.
                Один файл на двоих преподаватель не увидит в отчёте.
              </p>
            </div>
          </template>

          <Button type="submit" class="w-full" :disabled="loading || info.is_closed">
            {{ submitLabel }}
          </Button>
        </form>
      </CardContent>
    </Card>
  </div>
</template>
