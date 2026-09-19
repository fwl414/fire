import { defineConfig } from "vite"
import vue from "@vitejs/plugin-vue"
import { fileURLToPath, URL } from "node:url"
import AutoImport from "unplugin-auto-import/vite"
import Components from "unplugin-vue-components/vite"
import { ElementPlusResolver } from "unplugin-vue-components/resolvers"

export default defineConfig(({ mode }) => {
  const isProd = mode === "production"
  const apiTarget = process.env.VITE_API_TARGET || "http://127.0.0.1:8000"

  return {
    resolve: {
      alias: {
        "@": fileURLToPath(new URL("./src", import.meta.url)),
      },
    },
    plugins: [
      vue(),
      AutoImport({
        imports: ["vue", "vue-router", "pinia"],
        resolvers: [ElementPlusResolver()],
        dts: false,
      }),
      Components({
        resolvers: [ElementPlusResolver()],
        dts: false,
      }),
    ],
    server: {
      port: 5173,
      host: "0.0.0.0",
      proxy: {
        // 后端地址可通过 VITE_API_TARGET 覆盖（staging / 端到端测试使用独立端口）
        "/api": {
          target: apiTarget,
          changeOrigin: true,
        },
        // 实时推送（WebSocket）走同一个后端，生产由 nginx 的 location /ws/ 转发
        "/ws": {
          target: apiTarget,
          changeOrigin: true,
          ws: true,
        },
        "/health": {
          target: apiTarget,
          changeOrigin: true,
        },
      }
    },
    build: {
      target: "es2015",
      sourcemap: !isProd,
      chunkSizeWarningLimit: 1500,
      rollupOptions: {
        output: {
          manualChunks: {
            "vue-vendor": ["vue", "vue-router", "pinia"],
            "element-plus": ["element-plus", "@element-plus/icons-vue"],
            "echarts": ["echarts"],
            "three": ["three"],
            "axios": ["axios"],
          },
          chunkFileNames: "assets/js/[name]-[hash].js",
          entryFileNames: "assets/js/[name]-[hash].js",
          assetFileNames: "assets/[ext]/[name]-[hash].[ext]",
        }
      },
      minify: "terser",
      terserOptions: {
        compress: {
          drop_console: isProd,
          drop_debugger: isProd,
          pure_funcs: isProd ? ["console.log", "console.info", "console.debug"] : [],
        },
        format: {
          comments: false,
        }
      },
      cssCodeSplit: true,
      reportCompressedSize: false,
    },
    optimizeDeps: {
      include: [
        "vue",
        "vue-router",
        "pinia",
        "element-plus",
        "axios",
        "echarts",
      ],
    },
  }
})
