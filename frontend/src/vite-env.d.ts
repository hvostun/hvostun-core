/// <reference types="vite/client" />

declare module "*.svg" {
  const src: string
  export default src
}

interface Window {
  __hvostunApi?: import("./api/client").HvostunApi
}
