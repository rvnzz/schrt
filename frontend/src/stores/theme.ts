import { computed, ref, watch } from 'vue'
import { defineStore } from 'pinia'

export type ThemeMode = 'light' | 'dark' | 'system'
export type ResolvedTheme = 'light' | 'dark'

const STORAGE_KEY = '***'

function readStoredMode(): ThemeMode {
  const value = localStorage.getItem(STORAGE_KEY)
  return value === 'light' || value === 'dark' || value === 'system' ? value : 'system'
}

function systemPrefersDark(): boolean {
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false
}

export const useThemeStore = defineStore('theme', () => {
  const mode = ref<ThemeMode>(readStoredMode())
  const systemDark = ref(systemPrefersDark())

  const resolved = computed<ResolvedTheme>(() =>
    mode.value === 'system' ? (systemDark.value ? 'dark' : 'light') : mode.value
  )

  function apply() {
    const root = document.documentElement
    root.classList.toggle('dark', resolved.value === 'dark')
    root.style.colorScheme = resolved.value
  }

  function setMode(next: ThemeMode) {
    mode.value = next
    localStorage.setItem(STORAGE_KEY, next)
    apply()
  }

  function toggle() {
    setMode(resolved.value === 'dark' ? 'light' : 'dark')
  }

  // Реагируем на смену системной темы, пока пользователь не выбрал тему вручную
  watch(resolved, apply)

  const media = window.matchMedia?.('(prefers-color-scheme: dark)')
  media?.addEventListener?.('change', (event) => {
    systemDark.value = event.matches
  })

  apply()

  return { mode, resolved, setMode, toggle }
})
