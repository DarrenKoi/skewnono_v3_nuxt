// https://nuxt.com/docs/api/configuration/nuxt-config
const portFromEnv = Number.parseInt(import.meta.env.NUXT_PORT || '', 10)
const apiTarget = import.meta.env.NUXT_API_TARGET || 'http://localhost:5050'
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
    port: Number.isFinite(portFromEnv) ? portFromEnv : 3000
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
      // Vite rejects unknown Host headers (anti-DNS-rebinding). Allow the
      // remote-preview hostnames: Tailscale MagicDNS (`npm run dev:remote`,
      // reached from the tablet) and cloudflared quick tunnels. Raw IPs are
      // permitted by Vite without being listed here.
      allowedHosts: ['.ts.net', '.trycloudflare.com']
    }
  },

  // *.test.ts files are node:test scripts (run via `npm test`), not browser app
  // code. Exclude them from the app typecheck so vue-tsc doesn't error on
  // `node:test` imports and `.ts` import extensions.
  typescript: {
    tsConfig: {
      // Path is relative to the generated config in `.nuxt/`, mirroring its
      // `../app/**/*` include — a bare `**/*.test.ts` would only match `.nuxt/`.
      exclude: ['../app/**/*.test.ts'],
      compilerOptions: {
        // anomaly utils/tests import siblings with explicit .ts extensions (node --test needs them)
        allowImportingTsExtensions: true
      }
    }
  },

  eslint: {
    config: {
      stylistic: {
        commaDangle: 'never',
        braceStyle: '1tbs'
      }
    }
  },

  // The SPA (ssr:false) is served by Flask with no Nitro server at runtime, so
  // icons must be embedded into the client JS at build time. Without this the
  // client falls back to the network Iconify API (blocked on the internal
  // office network) and icons render blank.
  icon: {
    // Hard-disable the runtime Iconify API fallback. On the offline office
    // network those requests fail silently, so we never want them: any icon not
    // bundled below simply won't render (and makes no network call), which also
    // surfaces exactly which icons still need adding.
    fallbackToApi: false,
    clientBundle: {
      // Scan both our own source AND Nuxt UI's compiled components, so the
      // component-default icons (close=x, search, menu, sun, settings, chevrons)
      // that live in node_modules get auto-detected instead of leaking to the API.
      scan: {
        globInclude: ['app/**/*.{vue,ts,js}', 'node_modules/@nuxt/ui/dist/**/*.{vue,js,mjs}'],
        globExclude: ['node_modules/**/node_modules/**']
      },
      // Raised well above the 256KB default since the scanned set exceeds it.
      sizeLimitKb: 2048,
      // Dynamically-named icons that scan can't see as literal strings. Format is
      // `lucide:<name>`, not the `i-lucide-<name>` template form.
      icons: [
        'lucide:x',
        'lucide:layout-dashboard',
        'lucide:timer',
        'lucide:triangle-alert',
        'lucide:search',
        'lucide:cpu',
        'lucide:radio',
        'lucide:bar-chart-3',
        'lucide:git-compare',
        'lucide:eye',
        'lucide:sparkles',
        'lucide:panels-top-left',
        'lucide:plug',
        'lucide:settings',
        'lucide:sun',
        'lucide:menu'
      ]
    }
  }
})
