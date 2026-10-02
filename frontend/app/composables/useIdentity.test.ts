import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import { runInNewContext } from 'node:vm'
import ts from 'typescript'
import { computed, ref } from 'vue'
import { createInFlightSlot, payloadCacheOnInitial } from '../utils/asyncDataCache.ts'

test('identity changes discard both the activity payload and settled request cache', async () => {
  const payload: Record<string, unknown> = {}
  const state = new Map()
  let current = { user_id: 'anonymous', identity_source: 'anonymous' }
  let meRequests = 0
  const context = {
    ref,
    computed,
    createInFlightSlot,
    payloadCacheOnInitial,
    useRuntimeConfig: () => ({ public: { apiBase: '/api' } }),
    useState: (key: string, initial: () => unknown) => {
      if (!state.has(key)) state.set(key, ref(initial()))
      return state.get(key)
    },
    clearNuxtData: (keys: string[]) => keys.forEach(key => Reflect.deleteProperty(payload, key)),
    $fetch: async (url: string, options?: { method: string, body?: { empno: string } }) => {
      if (url === '/api/identify') {
        current = options?.method === 'DELETE'
          ? { user_id: 'anonymous', identity_source: 'anonymous' }
          : { user_id: options!.body!.empno, identity_source: 'declared' }
      }
      if (url === '/api/activity/me') meRequests++
      return { ...current }
    },
    useAsyncData: async (key: string, loader: () => Promise<unknown>) => {
      payload[key] ??= await loader()
      return { data: ref(payload[key]) }
    }
  }
  const load = (filename: string, imports: Record<string, unknown> = {}) => {
    const source = readFileSync(new URL(filename, import.meta.url), 'utf8')
    const code = ts.transpileModule(source, {
      compilerOptions: { module: ts.ModuleKind.CommonJS }
    }).outputText
    const exports: Record<string, (...args: never[]) => unknown> = {}
    runInNewContext(code, { ...context, exports, require: (name: string) => imports[name] })
    return exports
  }
  const activity = load('./useActivityApi.ts', {
    '~/utils/apiPath': { joinApiPath: (base: string, path: string) => base + path }
  })
  const { useIdentity } = load('./useIdentity.ts', { '~/composables/useActivityApi': activity })
  assert.ok(useIdentity)
  const { useActivityMe } = activity
  assert.ok(useActivityMe)
  const identity = useIdentity() as {
    refresh: () => Promise<void>
    identify: (empno: string, name: string) => Promise<string | null>
    signOut: () => Promise<void>
  }
  const fetchMe = async () => {
    const result = await useActivityMe() as { data: { value: { user_id: string } } }
    return result.data.value.user_id
  }

  // app.vue loads activity-me before the middleware resolves /api/me.
  assert.equal(await fetchMe(), 'anonymous')
  await identity.refresh()
  assert.equal(await identity.identify('1234567', '홍길동'), null)
  assert.equal(await fetchMe(), '1234567')
  assert.equal(await identity.identify('7654321', '김철수'), null)
  assert.equal(await fetchMe(), '7654321')
  await identity.signOut()
  assert.equal(await fetchMe(), 'anonymous')
  assert.equal(meRequests, 4)
})
