// https://nuxt.com/docs/api/configuration/nuxt-config
const portFromEnv = Number.parseInt(import.meta.env.NUXT_PORT || '', 10)
const apiTarget = import.meta.env.NUXT_API_TARGET || 'http://localhost:5000'
const apiBase = import.meta.env.NUXT_PUBLIC_API_BASE || '/api'
const isDev = import.meta.dev

export default defineNuxtConfig({
  // Flask serves the built SPA in Phase 2/3 — no Node server, no SSR.
  modules: [
    '@nuxt/eslint',
    '@nuxt/ui'
  ],

  ssr: false,

  devtools: {
    enabled: isDev
  },

  app: {
    head: {
      title: 'SKEWNONO',
      link: [
        { rel: 'icon', href: '/favicon/favicon.ico', sizes: 'any' },
        { rel: 'icon', type: 'image/svg+xml', href: '/favicon/favicon.svg' },
        { rel: 'icon', type: 'image/png', sizes: '32x32', href: '/favicon/favicon-32.png' },
        { rel: 'icon', type: 'image/png', sizes: '16x16', href: '/favicon/favicon-16.png' },
        { rel: 'apple-touch-icon', sizes: '180x180', href: '/favicon/apple-touch-icon.png' },
        { rel: 'manifest', href: '/favicon/site.webmanifest' }
      ],
      meta: [
        { name: 'theme-color', content: '#f0eee9' }
      ]
    }
  },

  css: ['~/assets/css/main.css'],

  // Fonts are self-hosted via @fontsource/*; disable @nuxt/fonts auto-resolution
  // to avoid contacting fontshare/google/bunny/fontsource at dev and build time.
  ui: {
    fonts: false
  },

  runtimeConfig: {
    public: {
      apiBase
    }
  },

  devServer: {
    port: Number.isFinite(portFromEnv) ? portFromEnv : 3100
  },

  compatibilityDate: '2025-01-15',

  nitro: {
    devProxy: {
      // h3 strips the '/api' mount prefix before the proxy runs, so the /api
      // segment must live inside the target URL for Flask to receive it.
      '/api': {
        target: `${apiTarget.replace(/\/$/, '')}/api`,
        changeOrigin: true
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
