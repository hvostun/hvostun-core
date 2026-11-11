import type { HvostunApi } from "./client"
import { LocalApi } from "./local"

export function createApi(): HvostunApi {
  if (import.meta.env.MODE === "test" && window.__hvostunApi) return window.__hvostunApi
  return new LocalApi()
}

export type { HvostunApi } from "./client"
export { ApiError } from "./types"
