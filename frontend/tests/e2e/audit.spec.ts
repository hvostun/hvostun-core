import { expect, test, type Page } from "@playwright/test"

async function seed(page: Page, store: Record<string, unknown>) {
  await page.addInitScript((raw) => localStorage.setItem("hvostun.profile", raw), JSON.stringify(store))
}

const profile = { name: "Рекс", age: "1_3y", sex: "male", home_since: "2024-01-01", origin: "shelter", first_dog: "yes" }

function session(extra: Record<string, unknown> = {}) {
  return {
    session: true,
    profile,
    profile_status: "none",
    survey_status: "none",
    survey_step: 0,
    dog_name: null,
    confidence: null,
    greeted: false,
    messages: [],
    fault: "none",
    events: [],
    ...extra,
  }
}

async function fits(page: Page) {
  const report = await page.evaluate(() => {
    const root = document.documentElement
    const overflow = root.scrollWidth > root.clientWidth + 1
    const targets = [...document.querySelectorAll("button, a")]
      .map((element) => {
        const box = element.getBoundingClientRect()
        return { text: element.textContent?.trim() ?? "", width: box.width, height: box.height, right: box.right }
      })
      .filter((item) => item.width > 0 && (item.width < 44 || item.height < 44 || item.right > window.innerWidth + 1))
    return { overflow, targets }
  })
  expect(report.overflow, JSON.stringify(report.targets)).toBe(false)
  expect(report.targets, JSON.stringify(report.targets)).toEqual([])
}

test("экраны не разъезжаются и цели касания не меньше 44", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto("/welcome")
  await fits(page)
  await page.goto("/login")
  await fits(page)
  await seed(page, session())
  await page.goto("/")
  await fits(page)
  await page.goto("/profile/edit")
  await fits(page)
  await seed(page, session({ profile_status: "done", dog_name: "Рекс" }))
  await page.goto("/profile")
  await fits(page)
  await page.goto("/survey")
  await fits(page)
  await seed(page, session({ profile_status: "done", dog_name: "Рекс", survey_status: "started" }))
  await page.goto("/survey/confidence")
  await fits(page)
  await seed(page, session({ profile_status: "done", dog_name: "Рекс", survey_status: "done", survey_step: 20 }))
  await page.goto("/plan")
  await fits(page)
  await page.goto("/chat")
  await fits(page)
  await page.goto("/nowhere")
  await fits(page)
})
