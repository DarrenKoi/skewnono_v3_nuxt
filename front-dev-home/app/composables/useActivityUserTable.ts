import type { ComputedRef } from 'vue'
import {
  fetchUserHistory,
  type UserHistoryResponse,
  type UserListRow
} from '~/composables/useActivityApi'
import { activityFeatureLabel, userDisplayName, userSearchText } from '~/utils/activity'
import { copyTableToClipboard, downloadCsv } from '~/utils/csvDownload'
import { todayStamp } from '../utils/dateTime.ts'

type UserSort = 'requests' | 'days' | 'recent' | 'name'

export const useActivityUserTable = (rows: ComputedRef<readonly UserListRow[]>) => {
  const query = ref('')
  const featureFilter = ref('all')
  // 최근 활동 순 by default: the question that opens this table is almost
  // always "who is using it right now", not "who used it most over 30 days".
  // Three places hold this default — this ref, hasActiveControls and
  // resetControls — and they must agree, or the 초기화 button lights up on
  // first render and then resets to something that was never the default.
  const sort = ref<UserSort>('recent')
  const toast = useToast()

  const sortOptions = [
    { label: '요청 많은 순', value: 'requests' },
    { label: '활동일 많은 순', value: 'days' },
    { label: '최근 활동 순', value: 'recent' },
    { label: '사용자 이름 순', value: 'name' }
  ]

  const featureFilterOptions = computed(() => {
    const features = new Set(
      rows.value
        .map(row => row.favorite_feature)
        .filter((feature): feature is string => Boolean(feature))
    )
    return [
      { label: '모든 기능', value: 'all' },
      ...Array.from(features)
        .sort((left, right) => activityFeatureLabel(left).localeCompare(activityFeatureLabel(right), 'ko'))
        .map(feature => ({ label: activityFeatureLabel(feature), value: feature }))
    ]
  })

  const filteredRows = computed(() => {
    const term = query.value.trim().toLocaleLowerCase('ko-KR')
    const matched = rows.value.filter((row) => {
      if (featureFilter.value !== 'all' && row.favorite_feature !== featureFilter.value) return false
      if (!term) return true
      return [userSearchText(row), row.favorite_feature ?? '', activityFeatureLabel(row.favorite_feature)]
        .join(' ')
        .toLocaleLowerCase('ko-KR')
        .includes(term)
    })

    return [...matched].sort((left, right) => {
      if (sort.value === 'days') {
        return right.days_active_30d - left.days_active_30d
          || right.requests_30d - left.requests_30d
      }
      if (sort.value === 'recent') {
        return (right.last_seen ? Date.parse(right.last_seen) : 0)
          - (left.last_seen ? Date.parse(left.last_seen) : 0)
          // Ties are ordinary — several people last active in the same second,
          // and every row with a null last_seen scores 0. Without a tiebreak
          // their order is whatever the backend happened to send, which it
          // does not promise to keep stable between refreshes.
          || left.user_id.localeCompare(right.user_id)
      }
      // Sorts by the label the column actually shows, so a row with no
      // directory name files under its employee number rather than dropping
      // to the end. 'ko' collation because most of these are Korean names.
      if (sort.value === 'name') {
        return userDisplayName(left).localeCompare(userDisplayName(right), 'ko')
      }
      return right.requests_30d - left.requests_30d
        || left.user_id.localeCompare(right.user_id)
    })
  })

  const hasActiveControls = computed(() =>
    Boolean(query.value) || featureFilter.value !== 'all' || sort.value !== 'recent'
  )

  const resetControls = () => {
    query.value = ''
    featureFilter.value = 'all'
    sort.value = 'recent'
  }

  const tableData = () => ({
    // 이름 and 사번 are separate columns here, unlike the on-screen cell that
    // stacks them: an export is what gets pasted into a spreadsheet and
    // filtered on, and a merged "고대영 (2067928)" string cannot be.
    headers: ['이름', '사번', '팀', '요청 (30일)', '활동일 (30일)', '가장 많이 쓴 기능', '기능 키', '마지막 활동'],
    rows: filteredRows.value.map(row => [
      row.emp_nm ?? '',
      row.user_id,
      // The raw value, not userTeamLabel — a spreadsheet wants a blank cell to
      // filter on, not the em dash the screen shows.
      row.dept_nm ?? '',
      row.requests_30d,
      row.days_active_30d,
      activityFeatureLabel(row.favorite_feature),
      row.favorite_feature,
      row.last_seen
    ])
  })

  const download = () => {
    const date = todayStamp()
    const table = tableData()
    downloadCsv(`activity-users-${date}.csv`, table.headers, table.rows)
  }

  const copy = async () => {
    const table = tableData()
    const ok = await copyTableToClipboard(table.headers, table.rows)
    toast.add(ok
      ? { title: '클립보드에 복사됨', icon: 'i-lucide-check', color: 'success' }
      : { title: '복사에 실패했습니다', icon: 'i-lucide-x', color: 'error' })
  }

  const expandedUser = ref<string | null>(null)
  const userDetail = ref<UserHistoryResponse | null>(null)
  const userDetailLoading = ref(false)
  const userDetailError = ref<string | null>(null)

  const toggleUser = async (userId: string) => {
    if (expandedUser.value === userId) {
      expandedUser.value = null
      userDetail.value = null
      userDetailError.value = null
      return
    }
    expandedUser.value = userId
    userDetail.value = null
    userDetailError.value = null
    userDetailLoading.value = true
    try {
      userDetail.value = await fetchUserHistory(userId)
    } catch (error) {
      userDetailError.value = error instanceof Error ? error.message : String(error)
    } finally {
      userDetailLoading.value = false
    }
  }

  return {
    query,
    featureFilter,
    sort,
    sortOptions,
    featureFilterOptions,
    filteredRows,
    hasActiveControls,
    resetControls,
    download,
    copy,
    expandedUser,
    userDetail,
    userDetailLoading,
    userDetailError,
    toggleUser
  }
}
