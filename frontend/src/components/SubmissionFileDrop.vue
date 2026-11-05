<script setup lang="ts">
import { computed, ref } from 'vue'
import { FileUp, Paperclip, X } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { formatBytes } from '@/lib/types'

const props = defineProps<{
  modelValue: File | null
  inputId: string
  maxFileSizeMb: number
  allowedExtensions?: string[] | null
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: File | null): void
  (e: 'error', message: string): void
}>()

const fileInput = ref<HTMLInputElement | null>(null)
const isDragging = ref(false)

const allowed = computed(() => (props.allowedExtensions ?? []).map((ext) => ext.toLowerCase()))
const accept = computed(() => (allowed.value.length ? allowed.value.map((ext) => `.${ext}`).join(',') : undefined))
const hint = computed(() =>
  allowed.value.length
    ? `Максимум ${props.maxFileSizeMb} МБ, форматы: ${allowed.value.join(', ')}`
    : `Максимум ${props.maxFileSizeMb} МБ`
)

function validate(file: File): boolean {
  if (file.size > props.maxFileSizeMb * 1024 * 1024) {
    emit('error', `Файл «${file.name}» больше ${props.maxFileSizeMb} МБ`)
    return false
  }
  if (allowed.value.length) {
    const extension = file.name.includes('.') ? file.name.split('.').pop()!.toLowerCase() : ''
    if (!allowed.value.includes(extension)) {
      emit('error', `Файл «${file.name}» недопустимого формата`)
      return false
    }
  }
  return true
}

function setFile(selected: File | null) {
  if (selected && !validate(selected)) return
  emit('update:modelValue', selected)
}

function onFileChange(event: Event) {
  const target = event.target as HTMLInputElement
  setFile(target.files?.[0] || null)
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
  if (dropped) setFile(dropped)
}

function openFilePicker() {
  fileInput.value?.click()
}

function clear() {
  emit('update:modelValue', null)
  if (fileInput.value) fileInput.value.value = ''
}
</script>

<template>
  <div class="grid gap-2">
    <div
      role="button"
      tabindex="0"
      class="flex min-h-[96px] cursor-pointer flex-col items-center justify-center rounded-md border border-dashed border-input bg-background px-4 py-4 text-sm text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
      :class="{ 'border-primary bg-primary/5 text-primary': isDragging, 'border-solid bg-muted/40 text-foreground': modelValue }"
      @dragover="handleDragOver"
      @dragleave="handleDragLeave"
      @drop="handleDrop"
      @click="openFilePicker"
      @keydown.enter="openFilePicker"
    >
      <template v-if="modelValue">
        <div class="flex items-center gap-2">
          <Paperclip class="h-4 w-4" />
          <span class="font-medium">{{ modelValue.name }}</span>
        </div>
        <p class="mt-1 text-xs text-muted-foreground">{{ formatBytes(modelValue.size) }}</p>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          class="mt-2 h-7 text-xs"
          @click.stop="clear"
        >
          <X class="mr-1 h-3.5 w-3.5" />
          Убрать файл
        </Button>
      </template>
      <template v-else>
        <FileUp class="mb-2 h-7 w-7" />
        <p class="text-center">Прикрепите отдельный файл этого студента</p>
        <p class="mt-1 text-center text-xs">{{ hint }}</p>
      </template>
    </div>
    <input :id="inputId" type="file" class="hidden" ref="fileInput" :accept="accept" @change="onFileChange" />
  </div>
</template>
