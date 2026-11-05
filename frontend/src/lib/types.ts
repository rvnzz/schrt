export interface Student {
  id: number
  first_name: string
  last_name: string
}

/** Студент, выбранный на странице сдачи: из списка группы или введённый вручную. */
export interface PickedStudent {
  first_name: string
  last_name: string
  student_id: number | null
}

export function emptyPickedStudent(): PickedStudent {
  return { first_name: '', last_name: '', student_id: null }
}

export function studentFullName(student: { first_name: string; last_name: string }): string {
  return `${student.last_name} ${student.first_name}`.trim()
}

/** Имя и фамилия сдаются отдельными полями — пробелы внутри означают, что в одно поле вписали двух людей. */
export function hasExtraWords(value: string): boolean {
  return value.trim().split(/\s+/).length > 1
}

export function formatBytes(bytes: number): string {
  if (!bytes) return '0 Б'
  const units = ['Б', 'КБ', 'МБ', 'ГБ']
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1)
  return `${parseFloat((bytes / Math.pow(1024, index)).toFixed(2))} ${units[index]}`
}

/** Русская плюрализация: 1 работа, 2 работы, 5 работ. */
export function pluralRu(count: number, one: string, few: string, many: string): string {
  const mod10 = count % 10
  const mod100 = count % 100
  if (mod10 === 1 && mod100 !== 11) return one
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20)) return few
  return many
}
