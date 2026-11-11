import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { AppRouter } from "./router"
import { UserProvider } from "./state/UserState"
import "./styles/fonts.css"
import "./styles/tokens.css"
import "./styles/base.css"

const root = document.getElementById("root")
if (!root) throw new Error("root")

createRoot(root).render(
  <StrictMode>
    <UserProvider>
      <AppRouter />
    </UserProvider>
  </StrictMode>,
)
