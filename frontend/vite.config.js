import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      // 개발 중 CORS 문제를 백엔드 미들웨어 없이 Vite 프록시로 해결한다 (CLAUDE.md).
      // 프론트엔드에서 fetch('/api/...')로 호출하면 :8000 백엔드로 그대로 전달된다.
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})
