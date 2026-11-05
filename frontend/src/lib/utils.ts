import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatDate(value: string | Date | null | undefined): string {
  if (!value) return '-'
  const date = typeof value === 'string' ? new Date(value) : value
  return date.toLocaleString('ru-RU')
}

/** Сохраняет ответ API как файл (работает с Authorization-заголовками, в отличие от обычной ссылки). */
export function triggerDownload(blob: Blob, filename: string) {
  const url = window.URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  document.body.removeChild(anchor)
  window.URL.revokeObjectURL(url)
}
