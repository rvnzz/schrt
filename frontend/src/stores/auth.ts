import { ref } from 'vue'
import { defineStore } from 'pinia'
import { api, getErrorMessage } from '@/lib/api'
import router from '@/router'

export interface Teacher {
  id: number
  username: string
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem('token'))
  const teacher = ref<Teacher | null>(null)
  const error = ref('')
  const loading = ref(false)

  async function login(username: string, password: string) {
    loading.value = true
    error.value = ''
    try {
      const response = await api.post('/auth/login', { username, password })
      token.value = response.data.access_token
      localStorage.setItem('token', response.data.access_token)
      await fetchMe()
      router.push('/groups')
    } catch (err) {
      error.value = getErrorMessage(err)
    } finally {
      loading.value = false
    }
  }

  async function fetchMe() {
    if (!token.value) return
    try {
      const response = await api.get('/auth/me')
      teacher.value = response.data
    } catch {
      logout()
    }
  }

  function logout() {
    token.value = null
    teacher.value = null
    localStorage.removeItem('token')
    router.push('/login')
  }

  return { token, teacher, error, loading, login, fetchMe, logout }
})
