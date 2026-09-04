import { defineConfig, loadEnv, type ProxyOptions } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, "..", "");
  const apiTarget = env.LUNARBIT_API_URL ?? "http://127.0.0.1:8000";
  const privateToken = env.LUNARBIT_PRIVATE_API_TOKEN;
  const proxy: ProxyOptions = {
    target: apiTarget,
    changeOrigin: true,
    headers: privateToken ? { authorization: `Bearer ${privateToken}` } : undefined,
    rewrite: (path) => path.replace(/^\/api\/private/, "/v1/private").replace(/^\/api\/public/, "/v1/public").replace(/^\/api\/query/, "/v1/query"),
    configure: (server) => {
      const proxyServer = server as unknown as { on: (event: string, listener: (proxyReq: { setHeader: (name: string, value: string) => void }, req: { url?: string }) => void) => void };
      proxyServer.on("proxyReq", (proxyReq, req) => {
        if (req.url?.startsWith("/api/private/") && privateToken) {
          proxyReq.setHeader("authorization", `Bearer ${privateToken}`);
        }
      });
    },
  };
  return {
  plugins: [react(), tailwindcss()],
  // Match API routes only; a broad `/api` key also captures Vite's `/api.ts`
  // module request and forwards it to FastAPI, preventing the app from booting.
  server: { port: 5173, strictPort: true, proxy: { "/api/": proxy } },
  build: { sourcemap: true },
  };
});
