import { render } from "@testing-library/react"
import { createMemoryRouter, RouterProvider } from "react-router"
import { seedStore } from "../../src/api/local"
import { routes } from "../../src/router"
import { UserProvider } from "../../src/state/UserState"
import type { Me } from "../../src/api/types"

export function renderAt(path: string) {
  const router = createMemoryRouter(routes, { initialEntries: [path] })
  return render(
    <UserProvider>
      <RouterProvider router={router} />
    </UserProvider>,
  )
}

export function signedIn(me: Partial<Me> = {}) {
  seedStore({
    session: true,
    profile_status: me.profile_status ?? "none",
    survey_status: me.survey_status ?? "none",
    survey_step: me.survey_step ?? 0,
    dog_name: me.dog_name ?? null,
  })
}
