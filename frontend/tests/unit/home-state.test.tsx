import { screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import type { Me } from "../../src/api/types"
import { screenAccess } from "../../src/state/access"
import { renderAt, signedIn } from "./render"

function me(profile: Me["profile_status"], survey: Me["survey_status"], dog_name: string | null = null): Me {
  return { profile_status: profile, survey_status: survey, survey_step: survey === "started" ? 0 : survey === "done" ? 20 : 0, dog_name }
}

describe("screenAccess", () => {
  it.each([
    ["none", "none", "A", "Заполнить профиль"],
    ["partial", "none", "A2", "Продолжить заполнение"],
    ["done", "none", "B", "Получить план"],
    ["done", "started", "C", "Продолжить анкету"],
    ["done", "done", "D", null],
  ] as const)("profile %s survey %s → %s", (profile, survey, state, text) => {
    const access = screenAccess(me(profile, survey, profile === "done" ? "Рекс" : null))
    expect(access.home).toBe(state)
    expect(access.next?.text ?? null).toBe(text)
  })

  it("показывает следующий шаг на главной", async () => {
    signedIn()
    renderAt("/")
    expect(await screen.findByTestId("next-step")).toHaveTextContent("Заполнить профиль")
  })
})
