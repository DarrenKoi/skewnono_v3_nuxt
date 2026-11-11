// 공지사항 — what changed in SKEWNONO, newest first. Rendered at /notices (App 정보 menu).
//
// A notice ships with the code it describes: the entry lands in the same deploy as the
// change, so users never read about a feature the running build does not have yet. That is
// why this is a frontend data file and not the `announcements` banner feed, which is
// operational (Redis at the office, editable without a deploy) and for urgent notes.
//
// Adding an entry is the whole act of publishing: /notices compares each `date` against the
// newest date this browser has seen (useNotices), so a new date reads as unread for
// everyone. `date` is therefore the id — one notice per date, ISO `YYYY-MM-DD` so string
// comparison is date order. A second change on the same day goes into that day's `sections`.
// notices.test.ts guards the format and the order.
//
// Only big changes belong here. The history starts at the open beta (2026-08-10); the
// official release went out by mail on 2026-09-10. A page that was still hidden on the
// cloud when it changed (TTTM and 채팅 before 2026-09-01) gets its notice the day it
// became visible, not the day it was built.
//
// Keep it short or nobody reads it: one sentence per item, about five items per notice at
// most. Say what the user can now do; leave out how it works and every option it has.

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
    date: '2026-11-03',
    category: '기능추가',
    title: 'Recipe 검색 — 비교하기 정식 지원',
    sections: [
      {
        area: 'Recipe 검색 · 비교하기',
        items: [
          '검색 결과에서 recipe 를 2개 이상 체크하고 비교하기를 누르면, 장비의 실제 설정값으로 비교합니다.',
          '차이만 보기로 값이 다른 항목만 남길 수 있고, 결과는 Excel 로 내려받습니다.',
          '장비에서 열지 못한 recipe 는 비교에서 빠지고, 화면 위쪽에 이유가 표시됩니다.',
          'recipe 가 10개를 넘으면 오래 걸리거나 연결이 끊길 수 있으니 10개 이하로 비교해 주시기 바랍니다.'
        ]
      }
    ]
  },
  {
    date: '2026-10-29',
    category: '기능추가',
    title: 'Recipe 검색 — 측정 이미지에 측정 박스 표시',
    sections: [
      {
        area: 'Recipe 검색 · 열어 보기',
        items: [
          '이미지 + 설정 탭의 측정 이미지 위에 측정 박스를 겹쳐 보여 주어, 파라미터가 어디를 재는지 바로 확인할 수 있습니다.',
          '이미지 오른쪽 위의 측정 박스 버튼으로 켜고 끕니다. HV-SEM 의 -U · -T · -M · -L 이미지에도 표시됩니다.',
          '계산식(Formula) 파라미터는 직접 재는 위치가 없어 표시하지 않습니다.'
        ]
      }
    ]
  },
  {
    date: '2026-10-26',
    category: '공지',
    title: 'VeritySEM · Provision 장비 연결 1차 작업 완료',
    sections: [
      {
        area: '전체',
        items: [
          'AMAT VeritySEM · Provision 장비를 SKEWNONO 에서 확인할 수 있습니다. 홈 화면과 왼쪽 메뉴의 버튼으로 장비 리스트에 들어갑니다.',
          '장비 상태의 FTP 접속 탭에서 두 장비의 파일도 열람 · 다운로드할 수 있습니다.',
          'Recipe 관련 서비스와 스큐보아는 준비되는 대로 순차적으로 확장할 예정입니다.',
          '사용 중 오류나 개선 의견은 담당자(최대영TL)에게 DM 또는 유선으로 알려 주시기 바랍니다.'
        ]
      }
    ]
  },
  {
    date: '2026-10-22',
    category: '기능추가',
    title: 'Recipe 검색 — 계산식(Formula) 해석',
    sections: [
      {
        area: 'Recipe 검색 · 열어 보기',
        items: [
          '계산식(Formula) 파라미터를 고르면 AMP 탭에 원본 수식과, $N 을 파라미터 이름으로 바꾼 해석을 함께 보여 줍니다. Excel 다운로드에도 Formula 시트가 추가되었습니다.',
          '이름 없는 파라미터는 (이름 없음) 으로 표시하며, 측정 위치도 확인할 수 있습니다.',
          '파라미터 목록은 Region → SEQ 순서로 열리고, 오른쪽 위의 컬럼 버튼으로 보고 싶은 컬럼만 고를 수 있습니다.'
        ]
      },
      {
        area: 'Recipe 검색',
        items: [
          '최근 검색 칸이 검색어 길이에 맞춰 넓어져, 긴 recipe 이름도 한 줄로 보입니다.'
        ]
      }
    ]
  },
  {
    date: '2026-10-20',
    category: '기능추가',
    title: 'FTP 접속 오픈 — 장비 파일 열람 · 다운로드',
    sections: [
      {
        area: '장비 상태 · FTP 접속',
        items: [
          '장비 상태의 FTP 접속 탭에서 CD-SEM · HV-SEM 장비의 폴더와 파일을 FTP 프로그램 없이 바로 열어 볼 수 있습니다.',
          'DRAM MI개발, NAND MI개발, DRAM Metrology기술, NAND Metrology기술, 기반기술전략 팀은 신청 없이 이용합니다. 그 밖의 팀은 탭의 안내 화면에서 개인 권한을 신청해 주시기 바랍니다.',
          '파일은 하나씩 받거나 여러 개를 체크해 zip 으로 받습니다. "다른 다운로드가 진행 중" 안내가 뜨면 잠시 후 다시 시도해 주시기 바랍니다.',
          '주소 링크를 복사하면 같은 폴더를 그대로 공유할 수 있습니다.',
          '장비 리스트의 파일 열기 버튼은 이 탭으로 옮겼습니다.'
        ]
      }
    ]
  },
  {
    date: '2026-10-13',
    category: '수정',
    title: '디바이스 통계 · Recipe 횡전개 표시 수정',
    sections: [
      {
        area: '디바이스 통계',
        items: [
          '저장된 필터가 목록을 좁히고 있으면 "저장된 필터 적용 중" 표시가 뜹니다. 찾는 디바이스가 없으면 먼저 초기화를 눌러 보시기 바랍니다.',
          '측정 상위 필터에 20 을 추가했습니다(10 / 20 / 25 / 50).',
          '원본에 스텝이 없는 디바이스는 "스텝 원본 자료 없음", 목록에 없는 디바이스는 "카탈로그에 없는 디바이스" 로 구분해 알립니다.',
          'R 계열 디바이스 일부에서 카테고리(DRAM / NAND)가 빠지던 문제를 고쳤습니다.'
        ]
      },
      {
        area: 'Recipe 횡전개',
        items: [
          '보유 판정의 원본 데이터 오류가 수정되어, 최근에 측정하지 않은 장비도 recipe 를 갖고 있으면 보유로 표시됩니다. 원본은 장비 점검 때마다 순서대로 고쳐지므로 한동안은 예전처럼 보일 수 있습니다.',
          '버전이 달라진 장비는 버전별 표에서 자기 버전 아래에 나타납니다.',
          '점검 때 보유 여부를 확인하지 못한 장비는 미보유 탭에서 "확인 불가" 배지로 구분합니다.'
        ]
      }
    ]
  },
  {
    date: '2026-10-09',
    category: '수정',
    title: 'AFM 측정 목록 응답 경량화',
    sections: [
      {
        area: 'AFM',
        items: [
          '측정 목록 응답 크기를 크게 줄여, 이력이 쌓여도 화면이 느려지지 않습니다. 화면 내용은 그대로입니다.'
        ]
      },
      {
        area: 'API 리스트',
        items: [
          '/api/afm/files 에 compact=1 을 붙이면 파일 목록이 빠진 가벼운 응답을 받습니다. 붙이지 않으면 이전과 같습니다.'
        ]
      }
    ]
  },
  {
    date: '2026-10-08',
    category: '기능추가',
    title: 'AFM 페이지 오픈',
    sections: [
      {
        area: 'AFM',
        items: [
          'AFM 측정 데이터를 볼 수 있습니다. 첫 화면의 AFM Metrology 카드에서 장비(MAP608 · MAPC01 · 5EAP1501)를 고르면 열립니다.',
          '측정 결과: Lot ID · Recipe · 날짜로 검색해 포인트 표, 분포 차트, 프로파일과 이미지를 봅니다. Excel 다운로드와 링크 공유가 됩니다.',
          '시계열 비교: 체크한 측정을 묶어 추세와 관리선, 그룹 통계를 봅니다.',
          '팁 모니터링: 장착된 팁의 Tip Width 추이를 정상 · 주의 · 이상으로 판정합니다.',
          '가동 현황 · Recipe 현황: 일별 측정 건수와 Recipe 별 측정 이력을 정리합니다.'
        ]
      }
    ]
  },
  {
    date: '2026-09-30',
    category: '기능추가',
    title: 'H/W 관리 기간 선택, 시점별 측정 Recipe 보기, MDC 비교 개선',
    sections: [
      {
        area: 'H/W 관리',
        items: [
          '조회 기간을 고를 수 있습니다. FDC · Sharpness 는 2 ~ 4주, BSM · Reso Center · MDC · SCE 는 30 ~ 90일 또는 달력으로 지정합니다.',
          'FDC 차트나 Sharpness 툴팁에서 한 시점을 고르면 그 앞뒤 30분 동안 측정한 Recipe 를 보여 줍니다.',
          'MDC 는 보정값이 바뀐 시점을 변경 이력 표로 정리하고, 비교에서는 선택 장비와 fab 중앙값의 차이(ppm)를 요약합니다.',
          'HV-SEM 의 MDC 비교에 CD-SEM 장비가 섞이던 문제와 BM/PM 표시가 범례와 겹치던 문제를 고쳤습니다.'
        ]
      }
    ]
  },
  {
    date: '2026-09-28',
    category: '기능추가',
    title: 'H/W 관리 FDC fab 전체 보기와 SCE 비교 개선',
    sections: [
      {
        area: 'H/W 관리',
        items: [
          'FDC 탭에서 장비 / fab 전체를 전환할 수 있습니다. fab 전체에서는 척 온도, LaserPower, Contactpin, 카운터 증가율을 장비 그룹 전체로 비교합니다. 처음 며칠은 비어 보일 수 있습니다.',
          'SCE 는 장비 그룹 전체에서 값이 다른 설정만 보여 줍니다.',
          '기록이 많은 장비에서 FDC 데이터를 불러오지 못하던 문제와 Reso Center · BSM · Sharpness 의 표시 오류를 고쳤습니다.'
        ]
      },
      {
        area: '스큐보아',
        items: [
          'recipe: 로 검색하면 이름이 정확히 일치하는 Recipe 가 먼저 나옵니다.'
        ]
      },
      {
        area: 'Recipe 검색',
        items: [
          '열어 보기 · 횡전개 · 측정 이력 화면에서도 스큐보아 버튼으로 바로 이동할 수 있습니다.'
        ]
      }
    ]
  },
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
