import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react"
import { createApi, type HvostunApi } from "../api"
import { ApiError, type Me } from "../api/types"

type UserContextValue = {
  api: HvostunApi
  me: Me | null
  loading: boolean
  error: boolean
  refresh: () => Promise<void>
}

const UserContext = createContext<UserContextValue | null>(null)

export function UserProvider({ children }: { children: ReactNode }) {
  const api = useMemo(() => createApi(), [])
  const [me, setMe] = useState<Me | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)

  const refresh = useCallback(async () => {
    try {
      setMe(await api.me())
      setError(false)
    } catch (caught) {
      if (caught instanceof ApiError && caught.code === "E6") setError(true)
      else setMe(null)
    } finally {
      setLoading(false)
    }
  }, [api])

  useEffect(() => {
    void refresh()
  }, [refresh])

  const value = useMemo(() => ({ api, me, loading, error, refresh }), [api, me, loading, error, refresh])
  return <UserContext.Provider value={value}>{children}</UserContext.Provider>
}

export function useUser(): UserContextValue {
  const value = useContext(UserContext)
  if (!value) throw new Error("useUser вне UserProvider")
  return value
}
