import { screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import type { Me } from "../../src/api/types"
import { screenAccess } from "../../src/state/access"
import { renderAt, signedIn } from "./render"

function access(profile: Me["profile_status"], survey: Me["survey_status"], path = "/") {
  return screenAccess({ profile_status: profile, survey_status: survey, survey_step: 0, dog_name: null }, path)
}

describe("меню", () => {
  it("на главной без профиля открыта только главная", () => {
    const menu = access("none", "none").menu
    expect(menu.map((item) => [item.label, item.enabled])).toEqual([
      ["Главная", true],
      ["Профиль", false],
      ["План адаптации", false],
      ["Чат", false],
    ])
  })

  it("при заполнении формы профиль доступен как текущий экран", () => {
    expect(access("partial", "none", "/profile/edit").menu.find((item) => item.id === "profile")?.enabled).toBe(true)
  })

  it("план ведёт на шкалу, пока анкета начата, и на план, когда она готова", () => {
    expect(access("done", "started").menu.find((item) => item.id === "plan")).toMatchObject({
      enabled: true,
      to: "/survey/confidence",
    })
    expect(access("done", "done").menu.find((item) => item.id === "plan")).toMatchObject({ enabled: true, to: "/plan" })
  })

  it("серый пункт не уходит со страницы", async () => {
    signedIn()
    renderAt("/")
    const chat = await screen.findByRole("button", { name: "Чат" })
    expect(chat).toHaveAttribute("aria-disabled", "true")
    chat.click()
    expect(await screen.findByTestId("next-step")).toBeInTheDocument()
  })
})
