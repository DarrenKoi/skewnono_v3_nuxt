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
//
// Only big changes belong here. The history starts at the open beta (2026-08-10); the
// official release went out by mail on 2026-09-10. A page that was still hidden on the
// cloud when it changed (TTTM and 채팅 before 2026-09-01) gets its notice the day it
// became visible, not the day it was built.

/** 기능추가 = something new to use, 수정 = a fix to something that was wrong,
 *  공지 = news about the service itself (release, contact, schedule). */
export type NoticeCategory = '기능추가' | '수정' | '공지'

export interface NoticeSection {
  /** The page or area the changes are on, as users know it (e.g. '장비간 스큐(TTTM)'). */
  area: string
  items: string[]
}

export interface Notice {
  date: string
  category: NoticeCategory
  title: string
  sections: NoticeSection[]
  /** 중요: shown above the timeline on every page, whatever the filters' page. */
  pinned?: boolean
}

export const NOTICES: Notice[] = [
  {
    date: '2026-09-18',
    category: '기능추가',
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
  },
  {
    date: '2026-09-12',
    category: '기능추가',
    title: 'MSR 원본 일괄 다운로드 API 와 개인 방문 캘린더',
    sections: [
      {
        area: 'API 리스트',
        items: [
          '여러 측정의 MSR 원본(.MSR 또는 pickle)을 한 번의 요청으로 묶어 내려받을 수 있습니다. 한 번에 최대 100개까지 받을 수 있습니다.',
          'API 리스트에 스큐보아 그룹이 생겨, 측정 파일 관련 API 를 한곳에서 찾을 수 있습니다.'
        ]
      },
      {
        area: '사용 통계',
        items: [
          '최근 90일 동안 SKEWNONO 를 방문한 날을 달력으로 볼 수 있습니다.'
        ]
      }
    ]
  },
  {
    date: '2026-09-10',
    category: '공지',
    title: 'SKEWNONO v3 정식 출시',
    pinned: true,
    sections: [
      {
        area: '전체',
        items: [
          '9월 10일 메일 안내와 함께 SKEWNONO v3 를 정식으로 출시했습니다. 8월 10일부터 이어진 오픈 베타 기간에 의견을 주신 분들께 감사드립니다.',
          'CD-SEM · HV-SEM 약 400여 대의 운영 데이터와 계측 데이터를 한 서비스에서 조회하고 분석합니다.',
          '주요 기능은 CD-SEM · HV-SEM 통합 관리, Recipe 현황 · 라이브 알람, 디바이스 통계, 통합 분석 대시보드 스큐보아, 장비간 스큐(TTTM) · PM 튜닝, 계측 지식 AI 어시스턴트(채팅)입니다.',
          '사용 중 오류나 개선 의견은 담당자(최대영TL)에게 DM 또는 유선으로 알려 주시기 바랍니다.'
        ]
      },
      {
        area: '스큐보아',
        items: [
          'SEM Image 를 확대하면 갤러리 뷰어로 열리고, 오른쪽에서 웨이퍼 위치와 측정 정보를 함께 볼 수 있습니다.',
          '확대한 이미지에서 cond.txt 취득 조건을 클릭 한 번으로 확인할 수 있습니다.'
        ]
      }
    ]
  },
  {
    date: '2026-09-03',
    category: '기능추가',
    title: '이미지 십자선 표시와 MSR 원본 다운로드',
    sections: [
      {
        area: 'Recipe 검색',
        items: [
          'Recipe 를 열었을 때 이미지 위에 cond.txt 기준 십자선을 겹쳐 그립니다.',
          'Excel 다운로드에 측정 위치가 함께 들어갑니다.'
        ]
      },
      {
        area: '라이브 알람',
        items: [
          '정렬 기준 이미지에도 같은 십자선을 표시합니다.'
        ]
      },
      {
        area: '스큐보아',
        items: [
          '측정의 MSR 원본(.MSR 또는 pickle)을 버튼 하나로 내려받을 수 있습니다.',
          '측정 이미지는 십자선 없이 원본 그대로 보여 줍니다.'
        ]
      },
      {
        area: '디바이스 통계',
        items: [
          '파라미터 행과 Excel 워크북에 mother/son 을 Mother_Para 값 그대로 적고, mother 행을 강조합니다.'
        ]
      }
    ]
  },
  {
    date: '2026-09-01',
    category: '기능추가',
    title: '채팅(계측 지식 AI 어시스턴트)과 장비간 스큐(TTTM) 공개',
    sections: [
      {
        area: '채팅',
        items: [
          '계측 지식 AI 어시스턴트를 사용할 수 있습니다. 장비 매뉴얼과 Recipe 문서를 바탕으로 답하고, 인용 칩을 누르면 인용된 원문을 바로 볼 수 있습니다.'
        ]
      },
      {
        area: '장비간 스큐(TTTM)',
        items: [
          '실험실 메뉴에 장비간 스큐(TTTM)를 공개했습니다. 같은 조건에서 장비끼리 측정값이 얼마나 맞는지 비교합니다.',
          'PM 플래닝은 별도 페이지가 아니라 TTTM 안의 PM 튜닝으로 합쳐졌습니다.'
        ]
      },
      {
        area: '디바이스 통계',
        items: [
          '판정 결과를 상한 초과 표시와 함께 Excel 로 내려받을 수 있습니다.'
        ]
      },
      {
        area: '전체',
        items: [
          '데이터 사외 반출 금지 안내를 화면에 표시합니다.'
        ]
      }
    ]
  },
  {
    date: '2026-08-28',
    category: '기능추가',
    title: '기본 Fab 설정과 H/W 관리 BM/PM 보기',
    sections: [
      {
        area: '세팅',
        items: [
          '세팅 페이지에서 기본 Fab 을 골라 둘 수 있습니다. 여러 개를 고르면 첫 번째가 기본 Fab 이 됩니다.'
        ]
      },
      {
        area: 'H/W 관리',
        items: [
          'BM/PM 정보를 목록과 상세로 나누어 보여 줍니다.',
          '모델을 먼저 고르면 그 모델의 장비만 선택 줄에 나타나고, 모델은 여러 개를 함께 고를 수 있습니다.'
        ]
      }
    ]
  },
  {
    date: '2026-08-22',
    category: '기능추가',
    title: '라이브 알람 정렬 기준 이미지와 스큐보아 판정 블록',
    sections: [
      {
        area: '라이브 알람',
        items: [
          'Align Fail 알람에서 해당 Recipe 의 정렬 기준 이미지를 바로 볼 수 있습니다.'
        ]
      },
      {
        area: '스큐보아',
        items: [
          '측정 개요 상단의 카드 네 장을 판정 블록 하나로 합쳐, 검토가 필요한지 한눈에 보입니다.'
        ]
      },
      {
        area: '디바이스 통계',
        items: [
          '디바이스 선택 표를 열 기준으로 정렬할 수 있고, 카드 보기와 함께 기본 50행씩 보여 줍니다.'
        ]
      }
    ]
  },
  {
    date: '2026-08-16',
    category: '기능추가',
    title: '스큐보아 짧은 링크 공유와 측정 개요 CDU 카드',
    sections: [
      {
        area: '스큐보아',
        items: [
          '지금 보고 있는 화면을 짧은 링크로 복사해 전달할 수 있습니다.',
          '측정 개요에 CDU 카드가 생기고, 측정 실패를 원인별로 나누어 보여 줍니다.'
        ]
      }
    ]
  },
  {
    date: '2026-08-15',
    category: '기능추가',
    title: '헤더를 실험실 · App 정보 두 메뉴로 정리',
    sections: [
      {
        area: '전체',
        items: [
          '헤더 오른쪽의 아이콘 여덟 개를 이름이 붙은 두 메뉴(실험실, App 정보)로 묶었습니다.'
        ]
      },
      {
        area: '디바이스 통계',
        items: [
          'Lot 카드에 이상치 배지를 표시하고, 배지를 누르면 Lot 상세 창이 열립니다. 상세 창에서는 전체/초과만 필터로 볼 수 있습니다.'
        ]
      }
    ]
  },
  {
    date: '2026-08-10',
    category: '공지',
    title: 'SKEWNONO v3 오픈 베타 시작',
    sections: [
      {
        area: '전체',
        items: [
          'SKEWNONO v3 를 오픈 베타로 공개했습니다. 아직 다듬어야 할 부분이 남아 있을 수 있으니, 이상한 동작이나 오류를 발견하시면 담당자(최대영TL)에게 알려 주시기 바랍니다.'
        ]
      },
      {
        area: 'Recipe 현황',
        items: [
          'Recipe TAT 와 Align · Meas Fail 이슈를 장비별로 볼 수 있고, 장비별 표를 Excel 로 내려받을 수 있습니다.'
        ]
      },
      {
        area: '스큐보아',
        items: [
          'HV-SEM 의 한 측정점에 딸린 여러 이미지를 골라 볼 수 있습니다.',
          'TIFF 이미지를 내려받지 않고 화면에서 바로 미리 볼 수 있습니다.'
        ]
      }
    ]
  }
]
