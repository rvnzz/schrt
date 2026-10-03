<script setup lang="ts">
import { ref, onMounted } from 'vue'
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
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { toast } from 'vue-sonner'

interface Group {
  id: number
  name: string
}

const groups = ref<Group[]>([])
const newName = ref('')
const loading = ref(false)
const open = ref(false)

async function fetchGroups() {
  try {
    const response = await api.get('/groups')
    groups.value = response.data
  } catch (err) {
    toast.error(getErrorMessage(err))
  }
}

async function createGroup() {
  if (!newName.value.trim()) return
  loading.value = true
  try {
    await api.post('/groups', { name: newName.value.trim() })
    newName.value = ''
    open.value = false
    await fetchGroups()
    toast.success('Группа создана')
  } catch (err) {
    toast.error(getErrorMessage(err))
  } finally {
    loading.value = false
  }
}

async function deleteGroup(id: number) {
  if (!confirm('Удалить группу?')) return
  try {
    await api.delete(`/groups/${id}`)
    await fetchGroups()
    toast.success('Группа удалена')
  } catch (err) {
    toast.error(getErrorMessage(err))
  }
}

onMounted(fetchGroups)
</script>

<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <h1 class="text-3xl font-bold">Группы</h1>
      <Dialog v-model:open="open">
        <DialogTrigger as-child>
          <Button>Создать группу</Button>
        </DialogTrigger>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Новая группа</DialogTitle>
            <DialogDescription>Введите название группы</DialogDescription>
          </DialogHeader>
          <div class="grid gap-4 py-4">
            <div class="grid gap-2">
              <Label for="name">Название</Label>
              <Input id="name" v-model="newName" />
            </div>
          </div>
          <DialogFooter>
            <Button @click="createGroup" :disabled="loading">Создать</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>

    <div class="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
      <Card v-for="group in groups" :key="group.id">
        <CardHeader>
          <CardTitle>{{ group.name }}</CardTitle>
          <CardDescription>
            <router-link :to="`/groups/${group.id}`" class="text-primary hover:underline">
              Открыть
            </router-link>
          </CardDescription>
        </CardHeader>
        <CardContent class="flex gap-2">
          <Button variant="outline" size="sm" as-child>
            <router-link :to="`/groups/${group.id}`">Управление</router-link>
          </Button>
          <Button variant="destructive" size="sm" @click="deleteGroup(group.id)">Удалить</Button>
        </CardContent>
      </Card>
    </div>
  </div>
</template>
