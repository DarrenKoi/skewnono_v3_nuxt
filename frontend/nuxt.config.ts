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
      // Chrome re-runs icon selection on every same-document history
      // navigation, and the analysis page rewrites the URL on every parameter
      // click (useSkewvoirRoute) — so a fetched icon is re-requested per click.
      // Cache headers only soften that, and only where they are set: Flask
      // sends max-age=86400 but the SPA mount is cloud-only, while the dev
      // server serves public/ as `max-age=0` (revalidate every time). The SVG
      // is therefore INLINED as a data: URI — 508 bytes in index.html that
      // resolve with no request, identically in dev, Nitro and Flask. Keep it
      // in sync with public/favicon/favicon.svg if the mark ever changes.
      //
      // favicon.ico stays as the pre-SVG fallback; it already embeds 16/32/48,
      // which is why the separate 16x16 and 32x32 PNG links are gone. Every
      // extra candidate is one more file Chrome walks when a fetch fails.
      link: [
        { rel: 'icon', type: 'image/svg+xml', href: 'data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 32 32%22 shape-rendering=%22geometricPrecision%22%3E%3Crect width=%2232%22 height=%2232%22 rx=%225%22 fill=%22%23f0eee9%22/%3E%3Crect x=%220.8%22 y=%220.8%22 width=%2230.4%22 height=%2230.4%22 rx=%224.5%22 fill=%22none%22 stroke=%22%23111214%22 stroke-width=%221.6%22/%3E%3Cline x1=%229%22 y1=%2224%22 x2=%2218%22 y2=%228%22 stroke=%22%23111214%22 stroke-width=%223.2%22 stroke-linecap=%22square%22/%3E%3Cline x1=%2216%22 y1=%2224%22 x2=%2225%22 y2=%228%22 stroke=%22%23c8321f%22 stroke-width=%223.2%22 stroke-linecap=%22square%22/%3E%3C/svg%3E' },
        { rel: 'icon', href: '/favicon/favicon.ico', sizes: 'any' },
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

  // *.test.ts files are node:test scripts (run via `npm test`), but they are
  // deliberately kept INSIDE the typecheck: many of them build inline
  // snake_case fixtures typed as real backend row types imported from the
  // use*Api composables (MeasHistRow, AfmDetailRow, AmpRow, …), so vue-tsc is
  // the only automated guard we have against a Phase 2 office adapter drifting
  // away from the shape the frontend expects. Excluding them, as we used to,
  // silently switched that guard off. `@types/node` is a devDependency so
  // `node:test`/`node:assert` resolve; it is picked up via TypeScript's
  // automatic @types inclusion rather than an explicit `types` array, which
  // would shadow Nuxt's own generated globals.
  typescript: {
    tsConfig: {
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
