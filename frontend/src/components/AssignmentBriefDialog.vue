<script setup lang="ts">
import { ref, watch } from 'vue'
import { Upload } from 'lucide-vue-next'
import { api, getErrorMessage } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { toast } from 'vue-sonner'

const props = defineProps<{
  open: boolean
  assignmentId: number | null
  assignmentTitle?: string
}>()

const emit = defineEmits<{
  (e: 'update:open', value: boolean): void
  (e: 'saved', enqueued: number): void
}>()

const brief = ref('')
const loading = ref(false)
const reading = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)

watch(
  () => [props.open, props.assignmentId],
  async ([open]) => {
    if (!open || props.assignmentId === null) return
    reading.value = true
    brief.value = ''
    try {
      const response = await api.get(`/assignments/${props.assignmentId}`)
      brief.value = response.data.brief_md || ''
    } catch (err) {
      toast.error(getErrorMessage(err))
    } finally {
      reading.value = false
    }
  },
  { immediate: true }
)

function onFileChange(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (!file) return
  const reader = new FileReader()
  reader.onload = () => {
    brief.value = String(reader.result || '')
  }
  reader.readAsText(file)
}

async function save() {
  if (props.assignmentId === null) return
  if (!brief.value.trim()) {
    toast.error('Текст задания пуст — AI нечего оценивать')
    return
  }

  loading.value = true
  try {
    await api.patch(`/assignments/${props.assignmentId}`, { brief_md: brief.value.trim() })

    // Перепроверка запускается сразу: работы без брифа эндпоинт сам пропустит
    const response = await api.post('/ai/enqueue', { assignment_id: props.assignmentId })
    const enqueued = response.data?.enqueued ?? 0
    toast.success(enqueued ? `Сохранено, в очередь поставлено работ: ${enqueued}` : 'Текст задания сохранён')
    emit('saved', enqueued)
    emit('update:open', false)
  } catch (err) {
    toast.error(getErrorMessage(err))
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <Dialog :open="open" @update:open="emit('update:open', $event)">
    <DialogContent class="max-w-2xl">
      <DialogHeader>
        <DialogTitle>Текст задания для AI</DialogTitle>
        <DialogDescription>
          {{ assignmentTitle || 'Задание' }} — этот текст видит только AI-агент, студентам он не показывается.
        </DialogDescription>
      </DialogHeader>

      <div class="grid gap-3 py-2">
        <Textarea
          v-model="brief"
          rows="12"
          :disabled="reading"
          placeholder="Критерии оценки, требования, формат ответа… (markdown)"
        />
        <div class="flex items-center justify-between gap-2 flex-wrap">
          <div class="flex items-center gap-2 text-sm text-muted-foreground">
            <Upload class="h-4 w-4" />
            <input
              type="file"
              accept=".md,.markdown,.txt"
              class="hidden"
              ref="fileInput"
              @change="onFileChange"
            />
            <Button type="button" variant="link" size="sm" class="h-auto p-0" @click="fileInput?.click()">
              Загрузить текст задания из .md
            </Button>
          </div>
          <p class="text-xs text-muted-foreground">Символов: {{ brief.trim().length }}</p>
        </div>
      </div>

      <DialogFooter>
        <Button variant="outline" :disabled="loading" @click="emit('update:open', false)">Отмена</Button>
        <Button :disabled="loading || reading" @click="save">
          {{ loading ? 'Сохранение…' : 'Сохранить' }}
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
