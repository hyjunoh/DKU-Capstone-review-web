import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    watch: {
      usePolling: true,
      interval: 1000,
    },
    // 코드가 절대 URL(API_BASE 기본 localhost:8000)로 호출하므로 이 proxy는
    // VITE_API_BASE='' (상대경로) 로 빌드/실행할 때만 사용됨.
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})