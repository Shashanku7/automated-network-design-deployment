import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: '0.0.0.0',
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
      },
      '/chat': {
        target: 'ws://localhost:8080',
        ws: true,
      },
    },
    allowedHosts: [
      'invitation-bids-questions-fountain.trycloudflare.com'
    ]  
  },
})
