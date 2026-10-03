<script setup lang="ts">
import { ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

const auth = useAuthStore()
const username = ref('')
const password = ref('')

async function onSubmit() {
  await auth.login(username.value, password.value)
}
</script>

<template>
  <div class="flex items-center justify-center py-12">
    <Card class="w-full max-w-sm">
      <CardHeader>
        <CardTitle class="text-2xl">Вход</CardTitle>
        <CardDescription>Введите логин и пароль преподавателя</CardDescription>
      </CardHeader>
      <CardContent>
        <form @submit.prevent="onSubmit" class="grid gap-4">
          <div class="grid gap-2">
            <Label for="username">Логин</Label>
            <Input id="username" v-model="username" required />
          </div>
          <div class="grid gap-2">
            <Label for="password">Пароль</Label>
            <Input id="password" type="password" v-model="password" required />
          </div>
          <p v-if="auth.error" class="text-sm text-destructive">{{ auth.error }}</p>
          <Button type="submit" :disabled="auth.loading" class="w-full">
            {{ auth.loading ? 'Вход...' : 'Войти' }}
          </Button>
        </form>
      </CardContent>
    </Card>
  </div>
</template>
