export type ProfileStatus = "none" | "partial" | "done"
export type SurveyStatus = "none" | "started" | "done"
export type AgeCode = "under_6m" | "6_12m" | "1_3y" | "3_7y" | "over_7y" | "unknown"
export type SexCode = "male" | "female"
export type OriginCode = "shelter" | "foster" | "street" | "previous" | "breeder" | "other"
export type FirstDogCode = "yes" | "before" | "currently"
export type ChatKind = "answer" | "off_topic" | "no_answer" | "urgent"
export type ChatStatus = "sent" | "failed" | "timeout"
export type Rating = "up" | "down" | null
export type ApiErrorCode = "E2" | "E6" | "E14" | "E24"
export type Fault = "none" | "send" | "timeout"

export type Me = {
  profile_status: ProfileStatus
  survey_status: SurveyStatus
  survey_step: number
  dog_name: string | null
}

export type DogProfile = {
  name: string
  age: AgeCode | ""
  sex: SexCode | ""
  home_since: string
  origin: OriginCode | ""
  first_dog: FirstDogCode | ""
}

export type ChatMessage = {
  id: string
  role: "user" | "assistant"
  text: string
  kind: ChatKind | null
  status: ChatStatus
  client_id: string | null
  rating: Rating
  comment: string
}

export class ApiError extends Error {
  code: ApiErrorCode

  constructor(code: ApiErrorCode) {
    super(code)
    this.name = "ApiError"
    this.code = code
  }
}

export const ageOptions: { value: AgeCode; label: string }[] = [
  { value: "under_6m", label: "до 6 месяцев" },
  { value: "6_12m", label: "6–12 месяцев" },
  { value: "1_3y", label: "1–3 года" },
  { value: "3_7y", label: "3–7 лет" },
  { value: "over_7y", label: "старше 7 лет" },
  { value: "unknown", label: "не знаю точно" },
]

export const sexOptions: { value: SexCode; label: string }[] = [
  { value: "male", label: "мальчик" },
  { value: "female", label: "девочка" },
]

export const originOptions: { value: OriginCode; label: string }[] = [
  { value: "shelter", label: "из приюта" },
  { value: "foster", label: "с передержки" },
  { value: "street", label: "с улицы" },
  { value: "previous", label: "от прежних хозяев" },
  { value: "breeder", label: "от заводчика" },
  { value: "other", label: "другое" },
]

export const firstDogOptions: { value: FirstDogCode; label: string }[] = [
  { value: "yes", label: "да" },
  { value: "before", label: "нет, раньше были собаки" },
  { value: "currently", label: "нет, сейчас в доме есть и другие собаки" },
]

export function labelOf<T extends string>(
  options: { value: T; label: string }[],
  value: T | "",
): string {
  return options.find((option) => option.value === value)?.label ?? ""
}

export function emptyProfile(): DogProfile {
  return { name: "", age: "", sex: "", home_since: "", origin: "", first_dog: "" }
}

export function emptyMe(): Me {
  return { profile_status: "none", survey_status: "none", survey_step: 0, dog_name: null }
}
