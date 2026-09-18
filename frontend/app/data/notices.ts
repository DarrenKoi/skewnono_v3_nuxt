// 공지사항 — what changed in SKEWNONO, newest first. Rendered at /notices (App 정보 menu).
//
// A notice ships with the code it describes: the entry lands in the same deploy as the
// change, so users never read about a feature the running build does not have yet. That is
// why this is a frontend data file and not the `announcements` banner feed, which is
// operational (Redis at the office, editable without a deploy) and for urgent notes.
//
// Adding an entry is the whole act of publishing: the header's N badge compares each `date`
// against the newest date this browser has seen (useNotices), so a new date lights it up
// for everyone. `date` is therefore the id — one notice per date, ISO `YYYY-MM-DD` so string
// comparison is date order. A second change on the same day goes into that day's `sections`.
// notices.test.ts guards the format and the order.

export interface NoticeSection {
  /** The page or area the changes are on, as users know it (e.g. '장비간 스큐(TTTM)'). */
  area: string
  items: string[]
}

export interface Notice {
  date: string
  title: string
  sections: NoticeSection[]
}

export const NOTICES: Notice[] = [
  {
    date: '2026-09-18',
    title: '장비간 스큐(TTTM) 개편과 스큐보아 바로가기',
    sections: [
      {
        area: '장비간 스큐(TTTM)',
        items: [
          '장비 그룹 배치도에서 장비를 클릭하면 바로 튜닝 대상으로 선택됩니다. 별도의 PM 튜닝 선택 바는 없어졌습니다.',
          '튜닝 목표 카드가 허용 오차와 관계없이 파라미터별 이동량을 항상 보여 줍니다. 기준은 선택한 장비를 뺀 나머지 그룹 장비의 평균입니다.',
          'PARAMETER 를 버튼으로 고르고, 트렌드 차트는 점 그래프로 표시합니다.'
        ]
      },
      {
        area: '스큐보아',
        items: [
          '장비 리스트, Recipe 현황, Recipe 검색에서 스큐보아 버튼으로 해당 장비·Recipe 의 검색 결과로 바로 이동할 수 있습니다.',
          '측정 개요 Radius Plot 의 확대 창을 한국어로 정리하고, 각 지표에 (i) 설명을 붙였습니다.',
          '이미지 갤러리의 "이미지 있음" 토글 이름이 "이미지 없음 제외"로 바뀌었습니다.',
          '여러 Recipe 를 묶어 열 때 Time-Series 화면이 "공유하는 파라미터가 없습니다"로 비던 문제를 고쳤습니다.'
        ]
      },
      {
        area: '디바이스 통계',
        items: [
          'Lot 요약 팝업의 단계별 링크 아이콘을 없애 팝업이 더 빨리 열립니다.'
        ]
      }
    ]
  }
]
