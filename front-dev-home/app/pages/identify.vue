<script setup lang="ts">
/**
 * Self-identification. Shown to a caller the infrastructure could not name.
 *
 * Deliberately NOT a login screen, and worded so: there is no password, no
 * account, and the result is weaker than a cookie identity. Presenting it as
 * authentication would promise a guarantee this layer does not make — and
 * would invite someone to treat it as one.
 */
import { normalizeEmpno, validateIdentityInput } from '~/utils/identityInput'

const route = useRoute()
const router = useRouter()
const { identify } = useIdentity()

const empno = ref('')
const empNm = ref('')
const error = ref<string | null>(null)
const submitting = ref(false)

/**
 * Same-origin paths only. `next` arrives in the query string, so accepting an
 * absolute URL would make this form an open redirect — and `//host` is a
 * protocol-relative URL, which `startsWith('/')` alone would wave through.
 */
const nextPath = computed(() => {
  const raw = route.query.next
  const value = Array.isArray(raw) ? raw[0] : raw
  return typeof value === 'string' && value.startsWith('/') && !value.startsWith('//')
    ? value
    : '/'
})

const submit = async () => {
  error.value = validateIdentityInput(empno.value, empNm.value)
  if (error.value) return

  submitting.value = true
  error.value = await identify(normalizeEmpno(empno.value), empNm.value.trim())
  submitting.value = false

  if (!error.value) await router.replace(nextPath.value)
}
</script>

<template>
  <div class="flex min-h-screen items-center justify-center p-6">
    <UCard class="w-full max-w-md">
      <template #header>
        <h1 class="text-lg font-medium text-(--sk-ink)">
          사용자 확인
        </h1>
        <p class="mt-1 text-sm text-(--sk-ink-muted)">
          접속하신 분을 확인할 수 없습니다. 사번과 이름을 입력해 주세요.
        </p>
      </template>

      <form
        class="space-y-4"
        @submit.prevent="submit"
      >
        <UFormField
          label="사번"
          name="empno"
        >
          <UInput
            v-model="empno"
            autofocus
            autocomplete="off"
            placeholder="2067928"
            :disabled="submitting"
            class="w-full"
          />
        </UFormField>

        <UFormField
          label="이름"
          name="emp_nm"
        >
          <UInput
            v-model="empNm"
            autocomplete="off"
            placeholder="홍길동"
            :disabled="submitting"
            class="w-full"
          />
        </UFormField>

        <UAlert
          v-if="error"
          color="error"
          variant="subtle"
          :description="error"
        />

        <UButton
          type="submit"
          block
          :loading="submitting"
        >
          확인
        </UButton>
      </form>

      <template #footer>
        <p class="text-xs text-(--sk-ink-muted)">
          입력하신 정보는 활동 기록에 사용됩니다. 로그인 절차가 아니며,
          비밀번호는 필요하지 않습니다.
        </p>
      </template>
    </UCard>
  </div>
</template>
