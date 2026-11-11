import type { DogProfile } from "../api/types"

export function isoDate(date: Date): string {
  const month = String(date.getMonth() + 1).padStart(2, "0")
  const day = String(date.getDate()).padStart(2, "0")
  return `${date.getFullYear()}-${month}-${day}`
}

export function formatDate(iso: string): string {
  const [year, month, day] = iso.split("-")
  if (!year || !month || !day) return ""
  return `${day}.${month}.${year}`
}

export function profileErrors(
  profile: DogProfile,
  today = new Date(),
): Partial<Record<keyof DogProfile, string>> {
  const errors: Partial<Record<keyof DogProfile, string>> = {}
  const name = profile.name.trim()
  if (name.length < 1 || name.length > 30) errors.name = "Укажите кличку"
  if (!profile.age) errors.age = "Выберите возраст"
  if (!profile.sex) errors.sex = "Выберите пол"
  if (!profile.home_since) errors.home_since = "Укажите дату"
  else if (profile.home_since > isoDate(today)) errors.home_since = "Дата в будущем"
  if (!profile.origin) errors.origin = "Выберите, откуда собака"
  if (!profile.first_dog) errors.first_dog = "Выберите вариант"
  return errors
}
