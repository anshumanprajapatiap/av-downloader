import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    tailwindcss()
  ],
  server: {
    host: '0.0.0.0',   // 👈 makes Vite accessible from outside Docker
    port: 5173,        // optional, just to be explicit
    strictPort: true,  // ensures Vite doesn't switch ports automatically
    watch: {
      usePolling: true // improves file change detection inside Docker
    },
    allowedHosts: ["fussily-subfractionary-irmgard.ngrok-free.dev"],
  }
})
