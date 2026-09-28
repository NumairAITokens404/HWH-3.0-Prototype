import { defineConfig } from 'vitest/config'

export default defineConfig({
  test: { environment: 'jsdom', setupFiles: './src/test/setup.ts', css: true, env: { VITE_API_MODE: 'mock' } },
})
