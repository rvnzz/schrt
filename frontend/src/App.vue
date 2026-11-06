<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { Moon, Monitor, Sun } from 'lucide-vue-next'
import { useAuthStore } from '@/stores/auth'
import { useThemeStore, type ThemeMode } from '@/stores/theme'
import { Button } from '@/components/ui/button'
import { Toaster } from '@/components/ui/sonner'

const auth = useAuthStore()
const theme = useThemeStore()

const nextModeHint: Record<ThemeMode, string> = {
  light: 'Тёмная тема',
  dark: 'Как в системе',
  system: 'Светлая тема',
}

const nextMode: Record<ThemeMode, ThemeMode> = {
  light: 'dark',
  dark: 'system',
  system: 'light',
}

const themeTitle = computed(() => {
  const labels: Record<ThemeMode, string> = {
    light: 'Светлая тема',
    dark: 'Тёмная тема',
    system: 'Тема как в системе',
  }
  return `${labels[theme.mode]} → ${nextModeHint[theme.mode]}`
})

function cycleTheme() {
  theme.setMode(nextMode[theme.mode])
}

onMounted(() => {
  auth.fetchMe()
})
</script>

<template>
  <div class="flex min-h-screen flex-col bg-background">
    <header class="border-b">
      <div class="container flex h-14 items-center justify-between">
        <router-link to="/" class="font-semibold text-lg">schrt.ru</router-link>
        <div class="flex items-center gap-3">
          <nav v-if="auth.token" class="flex items-center gap-4">
            <router-link to="/groups" class="text-sm text-muted-foreground hover:text-foreground">Группы</router-link>
            <router-link to="/assignments" class="text-sm text-muted-foreground hover:text-foreground">Задания</router-link>
            <router-link to="/grading" class="text-sm text-muted-foreground hover:text-foreground">AI-проверка</router-link>
            <span class="text-sm text-muted-foreground">{{ auth.teacher?.username }}</span>
            <Button variant="outline" size="sm" @click="auth.logout">Выйти</Button>
          </nav>
          <Button
            variant="outline"
            size="icon"
            :title="themeTitle"
            :aria-label="themeTitle"
            @click="cycleTheme"
          >
            <Sun v-if="theme.mode === 'light'" class="h-4 w-4" />
            <Moon v-else-if="theme.mode === 'dark'" class="h-4 w-4" />
            <Monitor v-else class="h-4 w-4" />
          </Button>
        </div>
      </div>
    </header>
    <main class="container flex-1 py-6">
      <router-view />
    </main>
    <footer class="border-t py-4">
      <div class="container text-center text-sm text-muted-foreground">
        Made with ❤️ by
        <a
          href="https://github.com/rvnzz/schrt"
          target="_blank"
          rel="noopener noreferrer"
          class="font-medium underline underline-offset-4 hover:text-foreground"
        >
          ravonzz
        </a>
      </div>
    </footer>
    <Toaster position="bottom-right" :theme="theme.resolved" />
  </div>
</template>
