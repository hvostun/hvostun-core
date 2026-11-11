import { consentVersion } from "../config"
import type { HvostunApi } from "./client"
import {
  ApiError,
  emptyProfile,
  type ChatKind,
  type ChatMessage,
  type DogProfile,
  type Fault,
  type Me,
  type Rating,
} from "./types"
import { profileErrors } from "../state/profileRules"

export const STORAGE_KEY = "hvostun.profile"

const GREETING =
  "Привет! Я ИИ-помощник по вопросам ухода за питомцем. Помогу разобраться в вашем вопросе. Что вас интересует?"

type Store = {
  session: boolean
  profile: DogProfile
  profile_status: Me["profile_status"]
  survey_status: Me["survey_status"]
  survey_step: number
  dog_name: string | null
  confidence: number | null
  greeted: boolean
  messages: ChatMessage[]
  fault: Fault
  events: { name: string; screen: string; payload?: unknown }[]
}

export function blankStore(): Store {
  return {
    session: false,
    profile: emptyProfile(),
    profile_status: "none",
    survey_status: "none",
    survey_step: 0,
    dog_name: null,
    confidence: null,
    greeted: false,
    messages: [],
    fault: "none",
    events: [],
  }
}

export function writeStore(store: Store): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(store))
}

export function seedStore(patch: Partial<Store> = {}): Store {
  const store = { ...blankStore(), ...patch }
  writeStore(store)
  return store
}

function readStore(): Store {
  const raw = localStorage.getItem(STORAGE_KEY)
  if (!raw) return blankStore()
  try {
    const parsed: unknown = JSON.parse(raw)
    if (!parsed || typeof parsed !== "object" || !("profile" in parsed)) throw new Error("bad")
    return parsed as Store
  } catch (error) {
    if (error instanceof ApiError) throw error
    throw new ApiError("E6")
  }
}

function meOf(store: Store): Me {
  return {
    profile_status: store.profile_status,
    survey_status: store.survey_status,
    survey_step: store.survey_step,
    dog_name: store.dog_name,
  }
}

function reply(text: string): { kind: ChatKind; text: string } {
  const value = text.toLowerCase()
  if (value.includes("погод")) return { kind: "off_topic", text: "Кажется, вопрос не про собаку" }
  if (value.includes("нет в материалах") || value.includes("квант")) {
    return {
      kind: "no_answer",
      text: "В моих материалах нет ответа на этот вопрос. Лучше уточнить у ветеринара или кинолога.",
    }
  }
  if (value.includes("кров") || value.includes("срочн")) {
    return { kind: "urgent", text: "Это требует очной помощи. Обратитесь в ветеринарную клинику." }
  }
  return {
    kind: "answer",
    text: "По материалам, которые у меня есть, начните со спокойного знакомства с домом и коротких прогулок.",
  }
}

function message(partial: Pick<ChatMessage, "role" | "text"> & Partial<ChatMessage>): ChatMessage {
  return {
    id: crypto.randomUUID(),
    role: partial.role,
    text: partial.text,
    kind: partial.kind ?? null,
    status: partial.status ?? "sent",
    client_id: partial.client_id ?? null,
    rating: partial.rating ?? null,
    comment: partial.comment ?? "",
  }
}

export class LocalApi implements HvostunApi {
  setFault(fault: Fault): void {
    const store = readStore()
    store.fault = fault
    writeStore(store)
  }

  async login(login: string, password: string, consent: boolean): Promise<void> {
    if (!login.trim() || !password || !consent) throw new ApiError("E2")
    const store = readStore()
    store.session = true
    store.events.push({ name: "login", screen: "S2", payload: { consent_version: consentVersion } })
    writeStore(store)
  }

  async logout(): Promise<void> {
    const store = readStore()
    store.session = false
    writeStore(store)
  }

  async me(): Promise<Me | null> {
    const store = readStore()
    return store.session ? meOf(store) : null
  }

  async getProfile(): Promise<DogProfile> {
    return readStore().profile
  }

  async saveDraft(profile: DogProfile): Promise<Me> {
    const store = readStore()
    if (store.profile_status === "done") return meOf(store)
    store.profile = profile
    const filled = Object.values(profile).some((value) => value !== "")
    store.profile_status = filled ? "partial" : "none"
    store.dog_name = null
    writeStore(store)
    return meOf(store)
  }

  async saveProfile(profile: DogProfile): Promise<Me> {
    if (Object.keys(profileErrors(profile)).length > 0) throw new ApiError("E6")
    const store = readStore()
    store.profile = { ...profile, name: profile.name.trim() }
    store.profile_status = "done"
    store.dog_name = store.profile.name
    writeStore(store)
    return meOf(store)
  }

  async startSurvey(): Promise<Me> {
    const store = readStore()
    if (store.profile_status !== "done") throw new ApiError("E6")
    store.survey_status = "started"
    store.survey_step = 0
    writeStore(store)
    return meOf(store)
  }

  async saveAnswer(value: number): Promise<Me> {
    const store = readStore()
    store.confidence = value
    if (store.survey_status === "none") store.survey_status = "started"
    writeStore(store)
    return meOf(store)
  }

  async finishSurvey(): Promise<Me> {
    const store = readStore()
    if (store.confidence === null) throw new ApiError("E6")
    store.survey_status = "done"
    store.survey_step = 20
    writeStore(store)
    return meOf(store)
  }

  async listMessages(): Promise<ChatMessage[]> {
    const store = readStore()
    if (!store.greeted) {
      store.greeted = true
      store.messages.unshift(message({ role: "assistant", text: GREETING }))
      writeStore(store)
    }
    return store.messages
  }

  async sendMessage(text: string): Promise<ChatMessage[]> {
    const store = readStore()
    const status = store.fault === "send" ? "failed" : store.fault === "timeout" ? "timeout" : "sent"
    store.messages.push(message({ role: "user", text, status, client_id: crypto.randomUUID() }))
    if (status === "sent") {
      const answer = reply(text)
      store.messages.push(message({ role: "assistant", text: answer.text, kind: answer.kind }))
    }
    writeStore(store)
    return store.messages
  }

  async deleteMessage(id: string): Promise<ChatMessage[]> {
    const store = readStore()
    store.messages = store.messages.filter((item) => item.id !== id)
    writeStore(store)
    return store.messages
  }

  async setFeedback(id: string, rating: Rating, comment = ""): Promise<void> {
    const store = readStore()
    const item = store.messages.find((entry) => entry.id === id)
    if (!item) throw new ApiError("E6")
    item.rating = rating
    item.comment = comment.slice(0, 500)
    writeStore(store)
  }

  async track(name: string, screen: string, payload?: unknown): Promise<void> {
    const store = readStore()
    store.events.push({ name, screen, payload })
    writeStore(store)
  }
}

