import { screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it } from "vitest"
import { emptyProfile } from "../../src/api/types"
import { isoDate, profileErrors } from "../../src/state/profileRules"
import { renderAt, signedIn } from "./render"

describe("профиль", () => {
  it("после «Готово» показывает ошибки всех пустых полей и снимает ошибку заполненного", async () => {
    signedIn()
    const user = userEvent.setup()
    renderAt("/profile/edit")
    await user.click(await screen.findByRole("button", { name: "Готово" }))
    expect(screen.getByText("Укажите кличку")).toBeInTheDocument()
    expect(screen.getByText("Выберите возраст")).toBeInTheDocument()
    expect(screen.getByText("Выберите пол")).toBeInTheDocument()
    expect(screen.getByText("Укажите дату")).toBeInTheDocument()
    expect(screen.getByText("Выберите, откуда собака")).toBeInTheDocument()
    expect(screen.getByText("Выберите вариант")).toBeInTheDocument()
    await user.type(screen.getByLabelText("Кличка"), "Рекс")
    expect(screen.queryByText("Укажите кличку")).not.toBeInTheDocument()
    expect(screen.getByText("Выберите возраст")).toBeInTheDocument()
  })

  it("не принимает дату в будущем", () => {
    const tomorrow = new Date()
    tomorrow.setDate(tomorrow.getDate() + 1)
    expect(profileErrors({ ...emptyProfile(), home_since: isoDate(tomorrow) }).home_since).toBe("Дата в будущем")
  })

  it("«Назад» сохраняет черновик и главная становится A2", async () => {
    signedIn()
    const user = userEvent.setup()
    renderAt("/profile/edit")
    await user.type(await screen.findByLabelText("Кличка"), "Тучка")
    await user.click(screen.getByRole("button", { name: "Назад" }))
    expect(await screen.findByTestId("next-step")).toHaveTextContent("Продолжить заполнение")
  })
})
