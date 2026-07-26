// The header's right-hand icon row, in render order, and the paths it leads to.
//
// One list, two consumers: AppHeader renders it, and FeatureTabs asks whether the current
// route is one of these pages. Those pages sit outside the /ebeam tree but still show the
// feature tabs, because the icon is the only way in — without the tabs there is no way back
// to the main pages.
//
// Deriving both from this array is the point. They used to be two hand-maintained lists in
// separate files, and a page added to the header but not to the allowlist silently lost its
// tabs — which happened three times (/intro + /endpoints + /activity + /settings, then
// /mag-pixel, then /chat). Adding an entry here is now the same act as allowing it.

export interface HeaderLink {
  // null = the target is computed at render time. live-alarm is fab-scoped, so it depends on
  // the remembered tool/fab rather than being a fixed path, and it is not an info path.
  to: string | null
  icon: string
  label: string
}

export const HEADER_LINKS: HeaderLink[] = [
  { to: '/intro', icon: 'i-lucide-panels-top-left', label: '소개' },
  { to: '/endpoints', icon: 'i-lucide-plug', label: 'API 리스트' },
  // scan-search: 스캔 프레임(FOV) 안의 돋보기(배율) — 이 페이지가 답하는
  // "패턴이 화면에 들어오는 한도에서 가장 높은 배율" 그 자체입니다. 자(ruler)는
  // 길이를 재는 뜻이라 배율·픽셀 선택과는 어긋났습니다. 헤더의 다른 돋보기
  // (search)는 항상 'Recipe 검색' 텍스트 필 안에 있어 아이콘만 있는 이
  // 묶음과 헷갈리지 않습니다.
  { to: '/mag-pixel', icon: 'i-lucide-scan-search', label: 'Mag/Pixel 가이드' },
  { to: '/chat', icon: 'i-lucide-message-square', label: '채팅' },
  { to: null, icon: 'i-lucide-radio', label: '라이브 알람' },
  { to: '/activity', icon: 'i-lucide-bar-chart-3', label: '사용 통계' },
  { to: '/settings', icon: 'i-lucide-settings', label: '세팅' }
]

// The fixed top-level pages the icon row leads to — the ones that keep the feature tabs.
export const HEADER_INFO_PATHS: string[]
  = HEADER_LINKS.flatMap(link => (link.to === null ? [] : [link.to]))

// Matches the page itself and anything nested under it, but never a longer sibling
// segment (`/chatroom` is not `/chat`).
export const isHeaderInfoPath = (path: string): boolean =>
  HEADER_INFO_PATHS.some(base => path === base || path.startsWith(`${base}/`))
