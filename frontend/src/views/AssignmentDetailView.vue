<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import { api, getErrorMessage } from '@/lib/api'
import { formatDate } from '@/lib/utils'
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
import { toast } from 'vue-sonner'

interface Group {
  id: number
  name: string
}

interface Submission {
  id: number
  first_name: string
  last_name: string
  original_filename: string
  file_size: number
  submitted_at: string
  is_late: boolean
}

interface AssignmentDetail {
  id: number
  title: string
  description: string | null
  code: string
  group_id: number
  group: Group
  soft_deadline: string | null
  hard_deadline: string | null
  max_file_size_mb: number
  submissions: Submission[]
}

const route = useRoute()
const assignmentId = Number(route.params.id)
const assignment = ref<AssignmentDetail | null>(null)
const linkPrefix = import.meta.env.VITE_LINK_PREFIX || 'http://localhost:5173/s/'

const link = computed(() => (assignment.value ? `${linkPrefix}${assignment.value.code}` : ''))
const downloadAllUrl = computed(() => `${api.defaults.baseURL}/submissions/assignments/${assignmentId}/download-all`)

async function fetchAssignment() {
  try {
    const response = await api.get(`/assignments/${assignmentId}`)
    assignment.value = response.data
  } catch (err) {
    toast.error(getErrorMessage(err))
  }
}

async function downloadSingle(submissionId: number) {
  try {
    const response = await api.get(`/submissions/${submissionId}/download`)
    window.open(response.data.download_url, '_blank')
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

onMounted(fetchAssignment)
</script>

<template>
  <div v-if="assignment" class="space-y-6">
    <div class="flex items-start justify-between">
      <div>
        <h1 class="text-3xl font-bold">{{ assignment.title }}</h1>
        <p class="text-muted-foreground">Группа: {{ assignment.group.name }}</p>
      </div>
      <Button variant="outline" as-child>
        <a :href="downloadAllUrl" target="_blank">Скачать все работы</a>
      </Button>
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
        <p>Мягкий дедлайн: {{ formatDate(assignment.soft_deadline) }}</p>
        <p>Жёсткий дедлайн: {{ formatDate(assignment.hard_deadline) }}</p>
        <p>Макс. размер файла: {{ assignment.max_file_size_mb }} МБ</p>
        <p v-if="assignment.description">Описание: {{ assignment.description }}</p>
      </CardContent>
    </Card>

    <Card>
      <CardHeader>
        <CardTitle>Сданные работы ({{ assignment.submissions.length }})</CardTitle>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Фамилия</TableHead>
              <TableHead>Имя</TableHead>
              <TableHead>Файл</TableHead>
              <TableHead>Размер</TableHead>
              <TableHead>Время</TableHead>
              <TableHead>Статус</TableHead>
              <TableHead class="text-right">Действия</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow v-for="sub in assignment.submissions" :key="sub.id">
              <TableCell>{{ sub.last_name }}</TableCell>
              <TableCell>{{ sub.first_name }}</TableCell>
              <TableCell>{{ sub.original_filename }}</TableCell>
              <TableCell>{{ formatBytes(sub.file_size) }}</TableCell>
              <TableCell>{{ formatDate(sub.submitted_at) }}</TableCell>
              <TableCell>
                <Badge v-if="sub.is_late" variant="destructive">Просрочено</Badge>
                <Badge v-else variant="default">Вовремя</Badge>
              </TableCell>
              <TableCell class="text-right">
                <Button variant="outline" size="sm" @click="downloadSingle(sub.id)">Скачать</Button>
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  </div>
</template>
