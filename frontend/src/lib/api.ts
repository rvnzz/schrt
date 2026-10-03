import axios, { AxiosError } from 'axios'

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

export function isAxiosError(error: unknown): error is AxiosError<{ detail?: string }> {
  return axios.isAxiosError(error)
}

export function getErrorMessage(error: unknown): string {
  if (isAxiosError(error)) {
    const data = error.response?.data
    if (typeof data === 'string') return data
    if (data && typeof data === 'object' && 'detail' in data) return String(data.detail)
    return error.message
  }
  if (error instanceof Error) return error.message
  return 'Unknown error'
}
