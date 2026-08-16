// The header's right-hand menus, in render order, and the paths they lead to.
//
// One list, three consumers: NavLabMenu and NavAccountMenu each render their own slice,
// and FeatureTabs asks whether the current route is one of these pages. Those pages sit
// outside the /ebeam tree but still show the feature tabs, because the menu is the only
// way in — without the tabs there is no way back to the main pages.
//
// Deriving all three from this array is the point, and it survived the 2026-08-15 move
// from an eight-icon row to two menus. They used to be two hand-maintained lists in
// separate files, and a page added to the header but not to the allowlist silently lost
// its tabs — which happened three times (/intro + /endpoints + /activity + /settings,
// then /mag-pixel, then /chat). Adding an entry here is still the same act as allowing
// it: `group` decides which menu draws it, never whether it is derived from.

/** Which of the two header menus draws this entry.
 *  `lab` — 실험실: CD-SEM/HV-SEM 장비를 대상으로 하는 조회·계산 도구. 장비를 고르기 전인
 *  랜딩 허브에서는 메뉴 자체가 그려지지 않습니다 (`useToolScopedRoute`).
 *  `account` — App 정보: 앱 자신과 호출자에 관한 페이지. 장비와 무관하므로 어디서나 보입니다. */
export type HeaderMenuGroup = 'lab' | 'account'

export interface HeaderLink {
  // null = the target is computed at render time. live-alarm is fab-scoped, so it depends on
  // the remembered tool/fab rather than being a fixed path, and it is not an info path.
  to: string | null
  icon: string
  label: string
  group: HeaderMenuGroup
  // The 실험실 rows are two-line: each tool needs a word about what it answers, because the
  // labels alone ('Mag/Pixel 가이드', '라이브 알람') do not say. The App 정보 rows are
  // single-line — '세팅' needs no gloss — so the field is optional rather than filled with filler.
  description?: string
  // Only for `to: null` entries: the path fragment that marks this link as the current page.
  // It lives on the record so a dynamic link's identity and its active test stay together —
  // splitting them across headerNav and the menu components would reintroduce the drift this
  // file exists to prevent.
  activeMatch?: string
  // Only for `to: null` entries: which fab-scoped target the menu builds for this row.
  // Required once there is more than one dynamic row — LabMenu used to treat `to: null` as
  // "this is 라이브 알람", so a second one would have silently pointed at the alarm board.
  scope?: 'live-alarm' | 'tttm'
  // Draw a hairline above this row. 채팅 is the only user: the rows above it are things you
  // look up or compute, and it is a conversation — same menu, different kind, so the eye is
  // given the seam rather than left to find it.
  separated?: boolean
}

export const HEADER_LINKS: HeaderLink[] = [
  // scan-search: 스캔 프레임(FOV) 안의 돋보기(배율) — 이 페이지가 답하는
  // "패턴이 화면에 들어오는 한도에서 가장 높은 배율" 그 자체입니다. 자(ruler)는
  // 길이를 재는 뜻이라 배율·픽셀 선택과는 어긋났습니다. 기능 탭의 다른 돋보기
  // (search)는 'Recipe 검색' 텍스트 필 안에 있어, 라벨을 항상 함께 그리는
  // 실험실 메뉴 항목과는 헷갈리지 않습니다.
  { to: '/mag-pixel', icon: 'i-lucide-scan-search', label: 'Mag/Pixel 가이드', group: 'lab', description: '패턴이 들어오는 최대 배율 계산' },
  { to: null, icon: 'i-lucide-radio', label: '라이브 알람', group: 'lab', description: '실시간 알람 보드', activeMatch: '/live-alarm', scope: 'live-alarm' },
  // 실험실 rather than a feature tab: the estimator behind this page is not validated yet
  // (docs/research/2026-08-16-skew-tttm-feasibility.md), and 실험실 already means "계산 도구,
  // 아직 확정 아님". A feature tab would claim more than the numbers currently support.
  // CD-SEM only, so unlike 라이브 알람 it does not follow the remembered tool type.
  { to: null, icon: 'i-lucide-git-compare', label: '장비간 스큐(TTTM)', group: 'lab', description: '장비끼리 얼마나 맞는지 비교', activeMatch: '/tttm', scope: 'tttm' },
  { to: '/chat', icon: 'i-lucide-message-square', label: '채팅', group: 'lab', description: '데이터에 대해 물어보기', separated: true },

  { to: '/intro', icon: 'i-lucide-panels-top-left', label: '앱 소개', group: 'account' },
  // API 리스트 lists this app's own endpoints — it asks nothing of a CD-SEM or HV-SEM tool,
  // so it belongs with the pages about the app rather than in 실험실. Being here also keeps
  // it reachable on the landing hub, where the 실험실 trigger is not drawn at all.
  { to: '/endpoints', icon: 'i-lucide-plug', label: 'API 리스트', group: 'account' },
  // activity, not bar-chart-3: 기능 탭의 '디바이스 통계'가 이미 bar-chart-3 입니다.
  // 같은 아이콘이 헤더 안에서 두 곳을 가리키면 아이콘이 식별자 역할을 못 합니다.
  { to: '/activity', icon: 'i-lucide-activity', label: '사용 통계', group: 'account' },
  { to: '/settings', icon: 'i-lucide-settings', label: '세팅', group: 'account' }
]

/** One menu's rows, in declaration order. */
export const headerLinksIn = (group: HeaderMenuGroup): HeaderLink[] =>
  HEADER_LINKS.filter(link => link.group === group)

// The fixed top-level pages the menus lead to — the ones that keep the feature tabs.
export const HEADER_INFO_PATHS: string[]
  = HEADER_LINKS.flatMap(link => (link.to === null ? [] : [link.to]))

// Matches the page itself and anything nested under it, but never a longer sibling
// segment (`/chatroom` is not `/chat`).
export const isHeaderInfoPath = (path: string): boolean =>
  HEADER_INFO_PATHS.some(base => path === base || path.startsWith(`${base}/`))

/** Whether `path` is the page this link leads to. Dynamic links (`to: null`) match on the
 *  fragment they carry, since their full target depends on the remembered tool/fab. */
export const isHeaderLinkActive = (link: HeaderLink, path: string): boolean =>
  link.to === null
    ? !!link.activeMatch && path.includes(link.activeMatch)
    : path === link.to || path.startsWith(`${link.to}/`)
