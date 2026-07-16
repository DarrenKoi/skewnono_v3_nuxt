export type SkewnonoHistoryFeature = {
  title: string
  description?: string
  icon: string
}

export type SkewnonoHistoryVersion = {
  version: string
  releasedAt: string
  summary: string
  features: SkewnonoHistoryFeature[]
  current?: boolean
}

export const skewnonoHistory = [
  {
    version: 'v1',
    releasedAt: '2024',
    summary: 'SKEWNONO의 첫 버전으로 장비와 측정 상태를 한곳에서 확인하기 시작했습니다.',
    features: [
      { title: '장비 상태', icon: 'i-lucide-monitor-check' },
      { title: '측정 이력', icon: 'i-lucide-history' },
      { title: 'FDC Sharpness', icon: 'i-lucide-activity' }
    ]
  },
  {
    version: 'v2',
    releasedAt: '2025',
    summary: '약 270대의 CD-SEM을 대상으로 장비와 Recipe 운영 정보를 더 폭넓게 연결했습니다.',
    features: [
      { title: 'CD-SEM 약 270대', icon: 'i-lucide-microscope' },
      { title: '장비 운영 정보', icon: 'i-lucide-gauge' },
      { title: 'Recipe · 측정 이력', icon: 'i-lucide-file-clock' }
    ]
  },
  {
    version: 'v3',
    releasedAt: '2026.07',
    current: true,
    summary: 'E-Beam 장비 운영과 측정 데이터를 통합하고 분석 기능을 강화한 현재 버전입니다.',
    features: [
      {
        title: 'CD-SEM · HV-SEM 통합 관리',
        description: 'CD-SEM 약 270대와 HV-SEM 약 50대, 총 약 320대의 장비 상태와 운영 정보를 한곳에서 확인합니다.',
        icon: 'i-lucide-microscope'
      },
      {
        title: 'Hardware · Calibration 분석',
        description: 'Hardware 상태, FDC, Beam Calibration, BM/PM 정보를 측정 결과와 연결해 장비 간 차이와 변화 원인을 확인합니다.',
        icon: 'i-lucide-cpu'
      },
      {
        title: 'Device Statistics 강화',
        description: 'DRAM, NAND, New Memory의 Device와 CD Step별 Recipe·Parameter 현황, 계측 룰 위반, 기간별 변화 추이를 분석합니다.',
        icon: 'i-lucide-table-properties'
      },
      {
        title: 'Skewvoir 분석',
        description: '측정 결과, Wafer 분포, 시간 변화, 상관관계, 측정 이미지를 연결해 이상 징후와 원인을 분석합니다.',
        icon: 'i-lucide-scan-search'
      }
    ]
  }
] satisfies SkewnonoHistoryVersion[]
