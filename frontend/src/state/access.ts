import type { Me } from "../api/types"

export type HomeState = "A" | "A2" | "B" | "C" | "D"

export type NextStep = { text: string; to: string }

export type MenuId = "home" | "profile" | "plan" | "chat"

export type MenuEntry = { id: MenuId; label: string; to: string; enabled: boolean }

export function homeState(me: Me): HomeState {
  if (me.profile_status === "none") return "A"
  if (me.profile_status === "partial") return "A2"
  if (me.survey_status === "done") return "D"
  if (me.survey_status === "started") return "C"
  return "B"
}

export function nextStep(me: Me): NextStep | null {
  const state = homeState(me)
  if (state === "A") return { text: "Заполнить профиль", to: "/profile/edit" }
  if (state === "A2") return { text: "Продолжить заполнение", to: "/profile/edit" }
  if (state === "B") return { text: "Получить план", to: "/survey" }
  if (state === "C") return { text: "Продолжить анкету", to: "/survey/confidence" }
  return null
}

export function greeting(me: Me): string {
  if (me.profile_status === "done" && me.dog_name) return me.dog_name
  return "Привет!"
}

export function screenAccess(me: Me, path = "/") {
  const planTo = me.survey_status === "started" ? "/survey/confidence" : "/plan"
  const menu: MenuEntry[] = [
    { id: "home", label: "Главная", to: "/", enabled: true },
    {
      id: "profile",
      label: "Профиль",
      to: me.profile_status === "done" ? "/profile" : "/profile/edit",
      enabled: me.profile_status === "done" || path === "/profile/edit",
    },
    { id: "plan", label: "План адаптации", to: planTo, enabled: me.survey_status !== "none" },
    { id: "chat", label: "Чат", to: "/chat", enabled: me.profile_status === "done" },
  ]
  return { home: homeState(me), next: nextStep(me), menu }
}
