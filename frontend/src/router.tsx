import { createBrowserRouter, Navigate, Outlet, RouterProvider, useLocation } from "react-router"
import { BottomMenu } from "./components/BottomMenu"
import { Chat } from "./screens/Chat"
import { Confidence } from "./screens/Confidence"
import { Home } from "./screens/Home"
import { Login } from "./screens/Login"
import { NotFound } from "./screens/NotFound"
import { Plan } from "./screens/Plan"
import { ProfileForm } from "./screens/ProfileForm"
import { ProfileView } from "./screens/ProfileView"
import { ServiceDown } from "./screens/ServiceDown"
import { SurveyIntro } from "./screens/SurveyIntro"
import { Welcome } from "./screens/Welcome"
import { useUser } from "./state/UserState"
import type { RouteObject } from "react-router"

function Root() {
  const { error, loading, refresh } = useUser()
  if (loading) return null
  if (error) return <ServiceDown onRetry={() => void refresh()} />
  return <Outlet />
}

function Session() {
  const { me } = useUser()
  if (!me) return <Navigate to="/welcome" replace />
  return <Outlet />
}

function Shell() {
  const { pathname } = useLocation()
  const fixed = pathname === "/chat"
  return (
    <div className="app">
      <div className={fixed ? "screen screen-fixed" : "screen"}>
        <Outlet />
      </div>
      {pathname === "/survey/confidence" ? null : <BottomMenu />}
    </div>
  )
}

export const routes: RouteObject[] = [
  {
    element: <Root />,
    children: [
      { path: "/welcome", element: <Welcome /> },
      { path: "/login", element: <Login /> },
      {
        element: <Session />,
        children: [
          {
            element: <Shell />,
            children: [
              { path: "/", element: <Home /> },
              { path: "/profile/edit", element: <ProfileForm /> },
              { path: "/profile", element: <ProfileView /> },
              { path: "/survey", element: <SurveyIntro /> },
              { path: "/survey/confidence", element: <Confidence /> },
              { path: "/plan", element: <Plan /> },
              { path: "/chat", element: <Chat /> },
              { path: "*", element: <NotFound /> },
            ],
          },
        ],
      },
    ],
  },
]

export function AppRouter() {
  return <RouterProvider router={createBrowserRouter(routes)} />
}
