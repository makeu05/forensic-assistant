import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// API_TARGET and WEB_PORT let a second instance run beside the dev one (end-to-end checks use 8001 and 5174).
const api = process.env.API_TARGET ?? "http://127.0.0.1:8000";
const port = Number(process.env.WEB_PORT ?? 5173);

export default defineConfig({
  plugins: [react()],
  resolve: {
    // MUI v5 icons ship a CommonJS build whose default export arrives wrapped ({ default: Icon }) with
    // this bundler, which blanks the page. Their ES-module build has a real default export.
    alias: [{ find: /^@mui\/icons-material\/(?!esm\/)(.+)$/, replacement: "@mui/icons-material/esm/$1" }],
  },
  server: { port, proxy: { "/api": api } },
});
