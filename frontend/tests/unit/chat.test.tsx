import { screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it } from "vitest"
import { LocalApi, seedStore } from "../../src/api/local"

function ready(api = new LocalApi()) {
  seedStore({ session: true, profile_status: "done", dog_name: "Рекс", profile: { name: "Рекс", age: "1_3y", sex: "male", home_since: "2024-01-01", origin: "shelter", first_dog: "yes" } })
  window.__hvostunApi = api
  return api
}

describe("чат", () => {
  it("показывает вид каждого ответа и оценку только у answer", async () => {
    ready()
    const { renderAt } = await import("./render")
    const user = userEvent.setup()
    renderAt("/chat")
    const box = await screen.findByLabelText("Сообщение")
    async function ask(text: string) {
      await user.clear(box)
      await user.type(box, text)
      await user.click(screen.getByRole("button", { name: "Отправить" }))
    }
    await ask("какая погода")
    expect(await screen.findByText("Кажется, вопрос не про собаку")).toBeInTheDocument()
    expect(screen.queryAllByRole("button", { name: "Полезно" })).toHaveLength(0)
    await ask("квантовая физика")
    expect(await screen.findByText(/В моих материалах нет ответа/)).toBeInTheDocument()
    await ask("у собаки кровь")
    const urgent = await screen.findByText("Это требует очной помощи. Обратитесь в ветеринарную клинику.")
    expect(urgent.className).toContain("urgent")
    await ask("как гулять")
    expect(await screen.findByRole("button", { name: "Полезно" })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Неполезно" })).toBeInTheDocument()
  })

  it("лист «Что не так?» принимает не больше 500 знаков", async () => {
    ready()
    const { renderAt } = await import("./render")
    const user = userEvent.setup()
    renderAt("/chat")
    await user.type(await screen.findByLabelText("Сообщение"), "как гулять")
    await user.click(screen.getByRole("button", { name: "Отправить" }))
    await user.click(await screen.findByRole("button", { name: "Неполезно" }))
    const dialog = await screen.findByRole("dialog", { name: "Что не так?" })
    const sheet = within(dialog).getByRole("textbox", { name: "Что не так?" })
    expect(within(dialog).getByRole("button", { name: "Отправить" })).toBeDisabled()
    await user.click(sheet)
    await user.paste("я".repeat(501))
    expect(sheet).toHaveValue("я".repeat(500))
  })

  it("C8 даёт повторить и удалить, C9 — повторить", async () => {
    const api = ready()
    const { renderAt } = await import("./render")
    const user = userEvent.setup()
    renderAt("/chat")
    const box = await screen.findByLabelText("Сообщение")
    api.setFault("send")
    await user.type(box, "первый")
    await user.click(screen.getByRole("button", { name: "Отправить" }))
    expect(await screen.findByText("Не отправлено")).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Удалить" }))
    expect(screen.queryByText("первый")).not.toBeInTheDocument()
    await user.type(box, "второй")
    await user.click(screen.getByRole("button", { name: "Отправить" }))
    expect(await screen.findByText("Не отправлено")).toBeInTheDocument()
    api.setFault("none")
    await user.click(screen.getByRole("button", { name: "Повторить" }))
    expect(await screen.findByText(/По материалам/)).toBeInTheDocument()

    api.setFault("timeout")
    await user.type(box, "третий")
    await user.click(screen.getByRole("button", { name: "Отправить" }))
    expect(await screen.findByText("Не удалось получить ответ")).toBeInTheDocument()
    api.setFault("none")
    await user.click(screen.getByRole("button", { name: "Повторить" }))
    expect(await screen.findAllByText(/По материалам/)).toHaveLength(2)
    expect(screen.queryByText("Не удалось получить ответ")).not.toBeInTheDocument()
  })

  it("пока помощник печатает, отправка закрыта", async () => {
    const api = ready()
    let release: () => void = () => undefined
    const gate = new Promise<void>((resolve) => {
      release = resolve
    })
    const send = api.sendMessage.bind(api)
    api.sendMessage = async (text) => {
      await gate
      return send(text)
    }
    const { renderAt } = await import("./render")
    const user = userEvent.setup()
    renderAt("/chat")
    await user.type(await screen.findByLabelText("Сообщение"), "как гулять")
    await user.click(screen.getByRole("button", { name: "Отправить" }))
    expect(await screen.findByText("Печатает…")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Отправить" })).toBeDisabled()
    release()
    expect(await screen.findByText(/По материалам/)).toBeInTheDocument()
  })
})
