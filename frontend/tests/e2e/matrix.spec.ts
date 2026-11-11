import { expect, test } from "@playwright/test"

function seed(status: string) {
  localStorage.setItem(
    "hvostun.profile",
    JSON.stringify({
      session: true,
      profile: { name: "Рекс", age: "1_3y", sex: "male", home_since: "2024-01-01", origin: "shelter", first_dog: "yes" },
      profile_status: status,
      survey_status: "none",
      survey_step: 0,
      dog_name: status === "done" ? "Рекс" : null,
      confidence: null,
      greeted: true,
      messages: [],
      fault: "none",
      events: [],
    }),
  )
}

const sizes = [
  { width: 360, height: 640 },
  { width: 390, height: 844 },
  { width: 768, height: 1024 },
  { width: 1280, height: 800 },
]

test("колонка держится на разных размерах и при крупном шрифте", async ({ page }) => {
  for (const size of sizes) {
    await page.setViewportSize(size)
    await page.goto("/welcome")
    const wide = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1)
    expect(wide, `${size.width}`).toBe(false)
  }
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto("/welcome")
  await page.evaluate(() => {
    document.documentElement.style.fontSize = "130%"
  })
  const scaled = await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1)
  expect(scaled).toBe(true)
})

test("поле чата видно при коротком окне", async ({ page }) => {
  await page.addInitScript(seed, "done")
  await page.setViewportSize({ width: 390, height: 360 })
  await page.goto("/chat")
  await expect(page.getByLabel("Сообщение")).toBeInViewport()
})

test("кнопка «Готово» видна при коротком окне", async ({ page }) => {
  await page.addInitScript(seed, "partial")
  await page.setViewportSize({ width: 390, height: 360 })
  await page.goto("/profile/edit")
  await expect(page.getByRole("button", { name: "Готово" })).toBeInViewport()
})
