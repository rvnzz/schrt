<script setup lang="ts">
import { onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { Button } from '@/components/ui/button'
import { Toaster } from '@/components/ui/sonner'

const auth = useAuthStore()

onMounted(() => {
  auth.fetchMe()
})
</script>

<template>
  <div class="flex min-h-screen flex-col bg-background">
    <header class="border-b">
      <div class="container flex h-14 items-center justify-between">
        <router-link to="/" class="font-semibold text-lg">schrt.ru</router-link>
        <nav v-if="auth.token" class="flex items-center gap-4">
          <router-link to="/groups" class="text-sm text-muted-foreground hover:text-foreground">Группы</router-link>
          <router-link to="/assignments" class="text-sm text-muted-foreground hover:text-foreground">Задания</router-link>
          <span class="text-sm text-muted-foreground">{{ auth.teacher?.username }}</span>
          <Button variant="outline" size="sm" @click="auth.logout">Выйти</Button>
        </nav>
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
    <Toaster position="bottom-right" />
  </div>
</template>
