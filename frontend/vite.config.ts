import { defineConfig } from "vite";
export default defineConfig({
  base: "./",
  build: {
    outDir: "../apps/visual_component/build",
    emptyOutDir: true,
    sourcemap: false,
  },
  server: { host: "127.0.0.1" },
});
