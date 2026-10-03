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
  <div class="min-h-screen bg-background">
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
    <main class="container py-6">
      <router-view />
    </main>
    <Toaster position="bottom-right" />
  </div>
</template>
