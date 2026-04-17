// https://nuxt.com/docs/api/configuration/nuxt-config
const portFromEnv = Number.parseInt(import.meta.env.NUXT_PORT || '', 10)
const apiTarget = import.meta.env.NUXT_API_TARGET
const apiBase = import.meta.env.NUXT_PUBLIC_API_BASE || (apiTarget ? '/api' : '/mock-api')
const isDev = process.env.NODE_ENV === 'development'

export default defineNuxtConfig({
  // Flask serves the built SPA in Phase 2/3 — no Node server, no SSR.
  ssr: false,

  modules: [
    '@nuxt/eslint',
    '@nuxt/ui'
  ],

  // Fonts are self-hosted via @fontsource/*; disable @nuxt/fonts auto-resolution
  // to avoid contacting fontshare/google/bunny/fontsource at dev and build time.
  ui: {
    fonts: false
  },

  devtools: {
    enabled: isDev
  },

  css: ['~/assets/css/main.css'],

  runtimeConfig: {
    public: {
      apiBase
    }
  },

  devServer: {
    port: Number.isFinite(portFromEnv) ? portFromEnv : 3100
  },

  compatibilityDate: '2025-01-15',

  nitro: apiTarget
    ? {
        devProxy: {
          '/api': {
            target: apiTarget,
            changeOrigin: true,
            prependPath: true
          }
        }
      }
    : undefined,

  vite: {
    server: {
      allowedHosts: ['.trycloudflare.com']
    }
  },

  eslint: {
    config: {
      stylistic: {
        commaDangle: 'never',
        braceStyle: '1tbs'
      }
    }
  }
})
