import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
// Using 127.0.0.1 instead of "localhost" for proxy targets — on Windows,
// Node.js resolves "localhost" to ::1 (IPv6) while Python/uvicorn listens
// on 127.0.0.1 (IPv4) by default. Using the explicit IP avoids the mismatch.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      // More specific WS path must come BEFORE the generic /api catch-all
      "/api/detection/ws": {
        target: "ws://127.0.0.1:8000",
        ws: true,
        changeOrigin: true,
      },
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});
