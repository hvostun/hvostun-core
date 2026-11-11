import react from "@vitejs/plugin-react"
import { defineConfig } from "vitest/config"

export default defineConfig({
  plugins: [react()],
  build: {
    assetsInlineLimit: 0,
    modulePreload: { polyfill: false },
  },
  server: {
    fs: { allow: [".", "design/illustrations"] },
  },
  test: {
    environment: "jsdom",
    setupFiles: "tests/setup.ts",
    include: ["tests/unit/**/*.test.tsx"],
  },
})
