// https://nuxt.com/docs/api/configuration/nuxt-config
const portFromEnv = Number.parseInt(import.meta.env.NUXT_PORT || '', 10)

export default defineNuxtConfig({
  devServer: {
    port: Number.isFinite(portFromEnv) ? portFromEnv : 3100
  },

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
      apiBase: import.meta.env.NUXT_PUBLIC_API_BASE || '/api'
    }
  },

  routeRules: {
    '/': { prerender: true }
  },

  compatibilityDate: '2025-01-15',

  nitro: {
    devProxy: {
      '/api': {
        target: import.meta.env.NUXT_API_TARGET || 'http://127.0.0.1:5000',
        changeOrigin: true,
        prependPath: true
      }
    }
  },

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
