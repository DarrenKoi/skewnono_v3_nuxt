// https://nuxt.com/docs/api/configuration/nuxt-config
const portFromEnv = Number.parseInt(import.meta.env.NUXT_PORT || '', 10)
const apiTarget = import.meta.env.NUXT_API_TARGET
const apiBase = import.meta.env.NUXT_PUBLIC_API_BASE || (apiTarget ? '/api' : '/mock-api')

export default defineNuxtConfig({

  modules: [
    '@nuxt/eslint',
    '@nuxt/ui'
  ],

  devtools: {
    enabled: true
  },

  css: ['~/assets/css/main.css'],

  runtimeConfig: {
    public: {
      apiBase
    }
  },

  routeRules: {
    '/': { prerender: true }
  }, devServer: {
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
