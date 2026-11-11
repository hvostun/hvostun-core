import { useLocation, useNavigate } from "react-router"
import { Icon, type IconName } from "../icons/Icon"
import { screenAccess, type MenuId } from "../state/access"
import { draftHandler } from "../state/draft"
import { useUser } from "../state/UserState"

const icons: Record<MenuId, IconName> = { home: "home", profile: "paw", plan: "plan", chat: "chat" }

export function BottomMenu() {
  const { me, refresh } = useUser()
  const { pathname } = useLocation()
  const navigate = useNavigate()
  if (!me) return null
  const { menu } = screenAccess(me, pathname)

  return (
    <nav className="menu" aria-label="Разделы">
      {menu.map((item) => {
        const active = item.id === "home" ? pathname === "/" : pathname === item.to || (item.id === "profile" && pathname.startsWith("/profile")) || (item.id === "plan" && (pathname === "/plan" || pathname.startsWith("/survey"))) || (item.id === "chat" && pathname === "/chat")
        return (
          <button
            key={item.id}
            type="button"
            className={item.enabled ? (active ? "on" : "") : "off"}
            aria-disabled={!item.enabled}
            onClick={() => {
              void (async () => {
                await draftHandler.current?.()
                await refresh()
                if (!item.enabled) return
                await navigate(item.to)
              })()
            }}
          >
            <span className="pill">
              <Icon name={icons[item.id]} />
            </span>
            {item.label}
          </button>
        )
      })}
    </nav>
  )
}
