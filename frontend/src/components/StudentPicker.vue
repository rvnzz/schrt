<script setup lang="ts">
import { computed, ref } from 'vue'
import { onClickOutside } from '@vueuse/core'
import { ArrowUpDown, Pencil, Search, Users } from 'lucide-vue-next'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { hasExtraWords, studentFullName, type PickedStudent, type Student } from '@/lib/types'

const props = defineProps<{
  modelValue: PickedStudent
  students: Student[]
  inputId: string
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: PickedStudent): void
}>()

const query = ref('')
const open = ref(false)
const wrapper = ref<HTMLElement | null>(null)
const manual = ref(props.modelValue.student_id === null && !!props.modelValue.first_name)
const firstName = ref(props.modelValue.first_name)
const lastName = ref(props.modelValue.last_name)

onClickOutside(wrapper, () => {
  open.value = false
})

const roster = computed(() =>
  [...props.students].sort((a, b) => studentFullName(a).localeCompare(studentFullName(b), 'ru'))
)

const selectedStudent = computed(
  () => props.students.find((student) => student.id === props.modelValue.student_id) ?? null
)

const suggestions = computed(() => {
  const term = query.value.trim().toLowerCase()
  if (!term) return roster.value.slice(0, 8)
  return roster.value
    .filter((student) =>
      [
        `${student.last_name} ${student.first_name}`,
        `${student.first_name} ${student.last_name}`,
      ].some((variant) => variant.toLowerCase().includes(term))
    )
    .slice(0, 8)
})

const manualNameError = computed(() => {
  if (hasExtraWords(firstName.value)) return 'В поле «Имя» должно быть одно слово'
  if (hasExtraWords(lastName.value)) return 'В поле «Фамилия» должно быть одно слово'
  return ''
})

const labelTarget = computed(() => (manual.value ? `${props.inputId}-first` : props.inputId))

function pick(student: Student) {
  emit('update:modelValue', {
    first_name: student.first_name,
    last_name: student.last_name,
    student_id: student.id,
  })
  manual.value = false
  open.value = false
  query.value = ''
}

function emitManual() {
  emit('update:modelValue', {
    first_name: firstName.value.trim(),
    last_name: lastName.value.trim(),
    student_id: null,
  })
}

function onManualInput() {
  emitManual()
}

function enableManual() {
  manual.value = true
  open.value = false
  const tokens = query.value.trim().split(/\s+/)
  if (tokens.length >= 2 && !firstName.value) {
    // Студенты обычно пишут «Фамилия Имя», но и обратный порядок не должен путаться
    const swapped = roster.value.find(
      (student) => student.last_name.toLowerCase() === tokens[0].toLowerCase()
    )
    if (swapped) {
      firstName.value = swapped.first_name
      lastName.value = swapped.last_name
    } else {
      lastName.value = tokens[0]
      firstName.value = tokens.slice(1).join(' ')
    }
    query.value = ''
    emitManual()
  }
}

function backToSearch() {
  manual.value = false
  firstName.value = ''
  lastName.value = ''
  query.value = ''
  emit('update:modelValue', { first_name: '', last_name: '', student_id: null })
}
</script>

<template>
  <div ref="wrapper" class="relative">
    <Label :for="labelTarget" class="mb-1.5 block text-sm">Студент</Label>

    <div v-if="selectedStudent" class="flex items-center justify-between gap-2 rounded-md border bg-muted/40 px-3 py-2">
      <div class="flex items-center gap-2">
        <Users class="h-4 w-4 text-muted-foreground" />
        <span class="text-sm font-medium">{{ studentFullName(selectedStudent) }}</span>
        <Badge variant="secondary" class="text-xs">из списка группы</Badge>
      </div>
      <Button type="button" variant="ghost" size="sm" @click="backToSearch">
        <ArrowUpDown class="mr-1 h-3.5 w-3.5" />
        Выбрать другого
      </Button>
    </div>

    <div v-else-if="manual" class="space-y-2">
      <div class="grid grid-cols-2 gap-2">
        <Input
          v-model="firstName"
          :id="`${inputId}-first`"
          placeholder="Имя"
          autocomplete="off"
          @input="onManualInput"
        />
        <Input
          v-model="lastName"
          :id="`${inputId}-last`"
          placeholder="Фамилия"
          autocomplete="off"
          @input="onManualInput"
        />
      </div>
      <p v-if="manualNameError" class="text-xs text-destructive">{{ manualNameError }}</p>
      <Button
        v-if="students.length"
        type="button"
        variant="link"
        size="sm"
        class="h-auto p-0 text-xs"
        @click="backToSearch"
      >
        Выбрать из списка группы
      </Button>
    </div>

    <div v-else class="space-y-2">
      <div class="relative">
        <Search class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          :id="inputId"
          v-model="query"
          class="pl-9"
          placeholder="Фамилия или имя из списка группы"
          autocomplete="off"
          @focus="open = true"
        />
      </div>
      <div class="flex items-center justify-between text-xs text-muted-foreground">
        <span>В списке группы: {{ students.length }}</span>
        <button type="button" class="inline-flex items-center gap-1 hover:text-foreground" @click="enableManual">
          <Pencil class="h-3 w-3" />
          Нет в списке — ввести вручную
        </button>
      </div>
      <ul
        v-if="open && suggestions.length"
        class="absolute left-0 right-0 top-full z-10 mt-1 max-h-60 overflow-auto rounded-md border bg-popover p-1 shadow-sm"
      >
        <li
          v-for="student in suggestions"
          :key="student.id"
          class="cursor-pointer px-3 py-2 text-sm hover:bg-accent"
          @mousedown.prevent="pick(student)"
        >
          {{ studentFullName(student) }}
        </li>
      </ul>
      <p v-else-if="open && query" class="text-xs text-muted-foreground">
        Никого не нашли по запросу «{{ query }}». Можно ввести имя и фамилию вручную.
      </p>
    </div>
  </div>
</template>
