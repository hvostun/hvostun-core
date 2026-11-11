import { defineConfig } from "@playwright/test"

const ci = "process" in globalThis && Boolean((globalThis as { process?: { env?: { CI?: string } } }).process?.env?.CI)

export default defineConfig({
  testDir: "tests/e2e",
  use: { baseURL: "http://127.0.0.1:4173" },
  webServer: {
    command: "npm run build && npm run preview -- --host 127.0.0.1 --port 4173 --strictPort",
    url: "http://127.0.0.1:4173",
    reuseExistingServer: !ci,
    timeout: 120000,
  },
})
