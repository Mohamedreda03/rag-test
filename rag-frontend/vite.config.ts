import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from "path"

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/traces-dashboard': 'http://127.0.0.1:8000',
      '/dashboard': 'http://127.0.0.1:8000',
      '/traces': 'http://127.0.0.1:8000',
      '/query': 'http://127.0.0.1:8000',
      '/api': 'http://127.0.0.1:8000',
    },
  },

})

