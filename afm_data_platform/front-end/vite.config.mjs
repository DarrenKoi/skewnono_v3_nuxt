import { fileURLToPath, URL } from "node:url";
import Vue from "@vitejs/plugin-vue";
// Plugins
import AutoImport from "unplugin-auto-import/vite";
import Components from "unplugin-vue-components/vite";
// Utilities
import { defineConfig } from "vite";
import vueDevTools from "vite-plugin-vue-devtools";
import Vuetify, { transformAssetUrls } from "vite-plugin-vuetify";

// https://vitejs.dev/config/
export default defineConfig({
  base: process.env.VITE_BASE_URL || "/",
  plugins: [
    vueDevTools(),
    Vue({
      template: { transformAssetUrls },
    }),
    // https://github.com/vuetifyjs/vuetify-loader/tree/master/packages/vite-plugin#readme
    Vuetify({
      autoImport: true,
      styles: {
        configFile: "src/styles/settings.scss",
      },
    }),
    Components(),
    AutoImport({
      imports: [
        "vue",
        "vue-router",
        {
          pinia: ["defineStore", "storeToRefs"],
        },
      ],
      eslintrc: {
        enabled: true,
      },
      vueTemplate: true,
    }),
  ],
  optimizeDeps: {
    exclude: [
      "vuetify",
      "vue-router",
    ],
  },
  define: { "process.env": {} },
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("src", import.meta.url)),
    },
    extensions: [".js", ".json", ".jsx", ".mjs", ".ts", ".tsx", ".vue"],
  },
  server: {
    port: 3000,
  },
  css: {
    preprocessorOptions: {
      sass: {
        api: "modern-compiler",
      },
      scss: {
        api: "modern-compiler",
      },
    },
    postcss: {
      plugins: [],
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes("node_modules")) {
            if (id.includes("vuetify")) {
              return "vuetify";
            }
            if (id.includes("echarts")) {
              return "charts";
            }
            if (id.includes("@mdi/font")) {
              return "fonts";
            }
            if (id.includes("vue") || id.includes("pinia")) {
              return "vendor";
            }
          }
        },
        assetFileNames: (assetInfo) => {
          const fileName = assetInfo.names?.[0] || assetInfo.fileName || "";
          // Organize assets by type
          if (fileName.endsWith('.woff') || fileName.endsWith('.woff2') || fileName.endsWith('.ttf') || fileName.endsWith('.eot')) {
            return "assets/fonts/[name]-[hash][extname]";
          }
          if (fileName.endsWith('.png') || fileName.endsWith('.jpg') || fileName.endsWith('.jpeg') || 
              fileName.endsWith('.gif') || fileName.endsWith('.svg') || fileName.endsWith('.webp') || fileName.endsWith('.avif')) {
            return "assets/images/[name]-[hash][extname]";
          }
          if (fileName.endsWith('.css')) {
            return "assets/css/[name]-[hash][extname]";
          }
          return "assets/[name]-[hash][extname]";
        },
      },
    },
    chunkSizeWarningLimit: 600,
    target: 'es2015',
    sourcemap: false,
    minify: 'esbuild',
    esbuildOptions: {
      drop: ['console', 'debugger'],
    },
  },
});
