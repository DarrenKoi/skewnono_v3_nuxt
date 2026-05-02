import { VueQueryPlugin } from '@tanstack/vue-query'

// Vue Query configuration
const vueQueryConfig = {
  queryClientConfig: {
    defaultOptions: {
      queries: {
        // Cache data for 25 minutes before considering it stale (data updates every 30min)
        staleTime: 25 * 60 * 1000,
        // Keep unused data in cache for 35 minutes
        cacheTime: 35 * 60 * 1000,
        // Retry failed requests 2 times
        retry: 2,
        // Don't refetch on window focus by default (can be overridden per query)
        refetchOnWindowFocus: false,
        // Refetch on reconnect
        refetchOnReconnect: true,
      },
      mutations: {
        // Retry failed mutations once
        retry: 1,
      },
    },
  },
}

export { VueQueryPlugin, vueQueryConfig }