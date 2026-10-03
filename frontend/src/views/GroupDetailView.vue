<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import { api, getErrorMessage } from '@/lib/api'
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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { toast } from 'vue-sonner'

interface Student {
  id: number
  first_name: string
  last_name: string
}

interface Assignment {
  id: number
  title: string
  code: string
  submissions: { student_id: number; is_late: boolean }[]
}

interface GroupDetail {
  id: number
  name: string
  students: Student[]
  assignments: Assignment[]
}

const route = useRoute()
const groupId = Number(route.params.id)
const group = ref<GroupDetail | null>(null)
const fileInput = ref<HTMLInputElement | null>(null)

const reportUrl = computed(() => `${api.defaults.baseURL}/submissions/groups/${groupId}/report`)

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

function submissionStatus(studentId: number, assignment: Assignment) {
  const sub = assignment.submissions.find((s) => s.student_id === studentId)
  if (!sub) return '—'
  return sub.is_late ? '⚠️' : '✅'
}

onMounted(fetchGroup)
</script>

<template>
  <div v-if="group" class="space-y-6">
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-3xl font-bold">{{ group.name }}</h1>
        <p class="text-muted-foreground">Управление группой и отчётность</p>
      </div>
      <Button variant="outline" as-child>
        <a :href="reportUrl" target="_blank">Выгрузить отчёт</a>
      </Button>
    </div>

    <Card>
      <CardHeader>
        <CardTitle>Студенты</CardTitle>
        <CardDescription>Загрузите список студентов из CSV</CardDescription>
      </CardHeader>
      <CardContent class="space-y-4">
        <div class="flex items-end gap-4">
          <div class="grid gap-2">
            <Label for="csv">CSV файл</Label>
            <Input id="csv" type="file" accept=".csv" ref="fileInput" @change="handleCsvUpload" />
          </div>
        </div>

        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Фамилия</TableHead>
              <TableHead>Имя</TableHead>
              <TableHead class="text-right">Действия</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow v-for="student in group.students" :key="student.id">
              <TableCell>{{ student.last_name }}</TableCell>
              <TableCell>{{ student.first_name }}</TableCell>
              <TableCell class="text-right">
                <Button variant="destructive" size="sm" @click="deleteStudent(student.id)">Удалить</Button>
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </CardContent>
    </Card>

    <Card>
      <CardHeader>
        <CardTitle>Таблица сдач</CardTitle>
        <CardDescription>Студенты × задания</CardDescription>
      </CardHeader>
      <CardContent>
        <div class="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Фамилия</TableHead>
                <TableHead>Имя</TableHead>
                <TableHead v-for="assignment in group.assignments" :key="assignment.id">
                  {{ assignment.title }}
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow v-for="student in group.students" :key="student.id">
                <TableCell>{{ student.last_name }}</TableCell>
                <TableCell>{{ student.first_name }}</TableCell>
                <TableCell v-for="assignment in group.assignments" :key="assignment.id">
                  {{ submissionStatus(student.id, assignment) }}
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </div>
      </CardContent>
    </Card>
  </div>
</template>
