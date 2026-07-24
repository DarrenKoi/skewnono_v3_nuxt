# CD-SEM Mag / Pixel 가이드 설계

작성일: 2026-07-25
원본 데이터: `docs/datatables/cdsem_mag_pixel_table.txt`

## 배경

CD-SEM 엔지니어는 레시피를 셋업할 때 "이 패턴을 측정하려면 배율과 픽셀 수를
얼마로 잡아야 하는가"를 판단해야 합니다. 지금은 이 판단을 뒷받침하는 화면이
없고, 측정 데이터에 실려 오는 `meas_condition_mag`·`meas_condition_pixel`도
원값 그대로 노출될 뿐 물리적 의미(픽셀당 몇 nm인가)로 해석되지 않습니다.

이 문서는 두 가지를 설계합니다.

1. 배율·픽셀 수에서 픽셀당 실제 길이(nm/px)를 유도하는 순수 계산 레이어
2. 그 위에 얹는 셋업 가이드 화면과, 기존 이미지 뷰어의 파생값 표시

## 물리 모델

원본 문서가 정의한 관계는 두 줄입니다.

```text
FOV_µm      = 135000 / Mag
PixelSize_nm = FOV_µm × 1000 / N_pixels
```

`135000`은 1× 배율에서의 장비 화면폭입니다.

> **원본 문서 정정 필요 (1) — 상수의 단위**
> 원본 18행은 이 상수를 `screen width in nm`이라고 적었습니다. 그러나 `FOV`가
> µm으로 정의되어 있으므로(2행·14행) 상수도 µm이어야 합니다. 135,000 µm =
> **135 mm**로, 장비 화면폭으로 타당한 값입니다. nm으로 해석하면 FOV가
> 0.00054 nm이 되어 물리적으로 성립하지 않습니다. 문서를 `µm`으로 고칩니다.

검산 (Mag 250,000 · 512 px):
`FOV = 135000/250000 = 0.54 µm` → `0.54 × 1000 / 512 = 1.0547 nm/px`.

## Series (CG / GT)

MAG 범위가 장비 계열에 따라 다릅니다.

| Series | Mag 범위 | 행 수 | 비고 |
| --- | --- | --- | --- |
| CG | 1K ~ 500K | 23 | 전 구간 확인됨 |
| GT | 1K ~ 1000K | 28 | 600K~1000K 5행은 **가정값** |

GT의 500K 초과 구간은 원본 문서가 "단위가 어떻게 되는지 확인 안되지만,
100000단위로 가정"이라고 명시했습니다. 표에서 해당 행에 `가정` 배지를 붙여
확인된 값과 시각적으로 구분합니다. 근거 없는 숫자를 확정값처럼 보이게 두지
않습니다.

픽셀 설정은 CG·GT 공통으로 512 / 1024 / 2048 / 4096입니다.

> **원본 문서 정정 필요 (2) — MAG 목록의 `4900`**
> CG MAG Range의 `4900`은 `5000`의 오타입니다(사용자 확인, 2026-07-25).
> 문서를 `5000`으로 고칩니다.

### Series 판정은 반드시 접두사 기반

`back_dev_home/ebeam/hitachi/_tool_specs.py`의 `model_to_tool_type()`가
모델코드 **접두사**로 `CG*`/`GT*` → `cd-sem`, `TP*` → `hv-sem`을 판정하고,
프론트 `useSemListApi.ts`의 `classifyToolType()`가 이를 미러링합니다.
Series 판정도 같은 방식을 따릅니다.

`TOOL_SPECS.eqp_models` 목록(`CG6300`, `GT2000` 등)을 **분류에 사용해서는 안
됩니다.** 해당 목록은 mock 재료이며, 과거 이 목록으로 분류했다가 목록에 없는
실장비 8대가 오피스 화면에서 조용히 사라진 사고가 있었습니다(2026-07-24,
`_tool_specs.py` 독스트링 참조).

## 아키텍처

백엔드 변경 없음. 상수 하나에서 유도되는 순수 계산이므로 Flask 왕복이
필요하지 않습니다. `docs/datatables/cdsem_mag_pixel_table.txt`는 원본
기록으로 유지하되 위 두 정정을 반영합니다.

```text
utils/magPixel.ts  (순수 함수, 백엔드 없음)
        │
   ┌────┴──────────────┐
   ▼                   ▼
pages/mag-pixel.vue    utils/skewvoirAnalysis/gallery.ts
(셋업 가이드 화면)      → ImageViewer.vue (실측 파생값)
```

## 1. 코어 — `front-dev-home/app/utils/magPixel.ts`

```text
SCREEN_WIDTH_UM = 135_000       // 135 mm

fovUm(mag)                  → number | null
fovNm(mag)                  → number | null
parsePixelSetting(text)     → { x, y } | null
pixelSizeNm(mag, pixels)    → number | null
pxPerCd(mag, pixels, cdNm)  → number | null
seriesFromModel(modelCd)    → 'CG' | 'GT' | null
magRange(series)            → readonly number[]
scanTimeFactor(pixels)      → (pixels / 512) ** 2
buildMagPixelTable(series)  → row[]
recommend(input)            → Recommendation
```

### null 규율

`msr_file/providers/mock.py:562`는 빈 row에 `meas_mag, meas_vac, meas_pixel =
0, 0, "0,0"`을 넣습니다. `135000 / 0`은 `Infinity`이고 `"0,0"` 파싱도 0이므로,
가드가 없으면 갤러리에 `Infinity nm/px`가 찍힙니다.

이 저장소는 이미 이 함정의 규율을 갖고 있습니다 — `useMsrFileApi.ts`의
`cd_value` 주석: *"NULLABLE ... Never coerce this to 0; gate it via
utils/msrRows."*

따라서 모든 계산 함수는 **유효하지 않은 입력에 `null`을 반환**하고 호출부가
null을 게이팅합니다. `Infinity`나 `NaN`을 반환 경로 밖으로 내보내지 않습니다.

- `mag <= 0` 또는 유한수가 아니면 → `null`
- `pixels <= 0` → `null`
- `parsePixelSetting`: `"0,0"`, 빈 문자열, 파싱 실패 → `null`

### 픽셀 설정 파싱

`meas_condition_pixel`은 `"512,512"` 형태의 문자열입니다. FOV는 **폭**이므로
`x`값을 계산에 씁니다. 정사각이 아닌 설정이 들어와도 `x` 기준임을 함수 주석에
명시합니다.

## 2. 셋업 가이드 화면 — `front-dev-home/app/pages/mag-pixel.vue`

경로 `/mag-pixel`. 헤더 우측 정보 페이지 계층(`/intro`, `/endpoints`,
`/activity`, `/settings`)에 아이콘 `i-lucide-ruler`로 추가합니다.
`FeatureTabs.vue`의 `INFO_PATHS`에 `/mag-pixel`을 넣어, 이 페이지에서도 feature
탭이 유지되어 원래 보던 화면으로 복귀할 수 있게 합니다.

fab·tool·기간과 무관한 순수 참고 화면입니다. API 호출 0회. `/endpoints`가 같은
성격의 선례입니다.

### 2.1 입력

| 입력 | 필수 | 기본 | 비고 |
| --- | --- | --- | --- |
| Series | ✓ | CG | CG / GT 토글 |
| CD (nm) | ✓ | — | 픽셀 제약을 결정 |
| Pitch (nm) | — | `CD × 2` | FOV 제약을 결정 |
| 패턴 수 | ✓ | 8 | 화면에 담을 pitch 주기 수 |
| 기준 px/CD | ✓ | 8 | **조정 가능**, 잠정값 |

Pitch를 비우면 `CD × 2`(bar:space 1:1)로 가정하고, 가정을 적용했다는 사실을
화면에 명시합니다. 실제 레시피에는 pitch가 있으므로 아는 경우 입력받는 쪽이
정확합니다.

**기준 px/CD는 하드코딩하지 않습니다.** 사내 계측 기준이 아직 정해지지
않았습니다(사용자 확인, 2026-07-25). 기본값 8을 쓰되 화면에 `잠정`으로 명시하고
입력으로 열어둡니다. 사내 기준이 확정되면 기본 상수 한 줄만 바꾸면 됩니다.

검증: `pitch > CD`여야 합니다. 위배 시 입력 오류를 표시하고 계산하지 않습니다.

### 2.2 모식도

두 제약이 서로 반대 방향으로 당기므로, 각각을 담당하는 2단 구성입니다.

- **① 전체 FOV** — 가로 스트립에 bar/space를 패턴 수만큼 렌더. FOV 안에 다
  들어오는지(**FOV 제약**)를 보여줍니다.
- **② Pitch 1개 확대** — pitch 하나를 확대하고 픽셀 경계를 실제로 그립니다.
  CD 위에 픽셀이 몇 개 얹히는지(**픽셀 제약**)를 보여줍니다.

그 아래 **SEM 이미지 미리보기**를 접힌 토글로 둡니다. 펼치면 정사각 프레임에
촬영 결과를 시뮬레이션해서, 픽셀 수에 따른 계단현상을 눈으로 확인할 수 있게
합니다. 기본 접힘 — 세로 공간을 많이 쓰기 때문입니다.

### 2.3 통합 테이블

**조합 격자와 참조표를 하나의 테이블로 둡니다.** 둘은 같은 표이며, 격자는
참조표에 판정색을 얹은 것뿐입니다. 분리하면 같은 숫자를 두 번 렌더하고
사용자가 둘의 차이를 혼동합니다.

- **입력 없음** → 순수 참조표 (`Mag | FOV | 512 | 1024 | 2048 | 4096`,
  셀 값은 nm/px)
- **입력 있음** → 같은 셀에 판정색과 px/CD가 얹힘

컬럼 헤더에 **512 ×1 · 1024 ×4 · 2048 ×16 · 4096 ×64**를 상시 노출합니다.
스캔 시간은 픽셀 총량(X×Y)에 비례하므로 512 대비 `(N/512)²`입니다
(사용자 확인, 2026-07-25).

실사용은 512·1024가 대부분이므로 **2048·4096은 기본 숨김**이고, "전체 보기"
On/Off 토글로 펼칩니다.

판정 기호:

| 기호 | 의미 |
| --- | --- |
| ● | 기준 통과 |
| ✗ | 픽셀 부족 (px/CD < 기준) |
| ✗ FOV | 패턴이 화면을 벗어남 (FOV < 필요 FOV) |
| ★ | 추천 조합 |

### 2.4 추천 알고리즘

```text
requiredFovNm = 패턴 수 × pitch
후보 = magRange(series).filter(mag => fovNm(mag) >= requiredFovNm)
추천 Mag  = max(후보)                                   // 가장 타이트한 프레이밍
추천 pixels = 기준을 통과하는 가장 작은 픽셀 수          // 최소 스캔 시간
```

배율은 **높을수록** FOV가 좁아 px/CD가 커지므로, 패턴이 들어오는 한도 안에서
가장 높은 배율이 해상도상 최적입니다. 픽셀 수는 기준만 넘으면 더 키울 이유가
없고 스캔 시간만 제곱으로 늘어나므로 **가장 작은 값**을 고릅니다.

### 2.5 512 vs 1024 안내

실사용이 512·1024 두 가지이고 그 사이가 4배 차이이므로, 이 화면이 실제로
답하는 질문은 "몇 배율?"이 아니라 **"512로 되나, 1024로 올려야 하나?"**입니다.
추천 카드와 하단 배너 두 곳에서 이 결론을 명시적으로 제시하고 근거를 함께
줍니다.

| 상황 | 안내 |
| --- | --- |
| 512가 기준 통과 | "512로 충분합니다. 1024는 스캔 시간만 4배가 됩니다" + 여유 배수 |
| 512 미달, 1024 통과 | "1024가 필요합니다 — 스캔 시간 4배를 감수해야 합니다" |
| 1024도 미달 | "패턴 수를 줄이거나 기준 px/CD를 재검토하세요" |
| 성립 Mag 없음 | "최저 배율에서도 패턴이 들어오지 않습니다 — 패턴 수를 줄이세요" |

무조건 512를 권하는 것이 아니라 트레이드오프를 수치와 함께 제시합니다.

## 3. 갤러리 인라인 파생값

`utils/skewvoirAnalysis/gallery.ts`가 이미 엔트리에 `mag`·`pixel`을 원값으로
싣고 있습니다(237-239행). 여기에 `pixelSizeNm`을 파생 필드로 추가하고
`ImageViewer.vue`에서 표시합니다.

```text
현재:  mag: 250030   pixel: "512,512"
변경:  Mag 250,030 · 512×512 · ≈ 1.055 nm/px
빈 row: mag 0 → 파생값 렌더 안 함 (null 게이팅)
```

**실측 mag를 그대로 계산에 씁니다.** mock의 `200015 / 250030 / 250044`처럼
실제 데이터는 공칭값(200K/250K)에서 미세하게 어긋나 있습니다. 이는 장비별
캘리브레이션 차이이고 그 차이 자체가 skew 신호이므로, 공칭값으로 반올림해
뭉개지 않습니다.

## 4. 테스트 — `front-dev-home/app/utils/magPixel.test.ts`

기존 `utils/*.test.ts` 규약(node:test + assert)을 따릅니다.

- 알려진 값: Mag 250,000 · 512 px → 1.0547 nm/px (허용 오차 내)
- FOV: Mag 180,000 → 750 nm
- null 가드: `mag = 0`, 음수, `NaN`, `Infinity`
- `parsePixelSetting`: `"512,512"` → `{x:512,y:512}`, `"0,0"` → null,
  빈 문자열 → null, 형식 오류 → null
- 접두사 판정: `"GT2000S"` → `'GT'`, `"cg6300"` → `'CG'` (소문자·공백 정규화),
  `"TP3000"` → null
- 행 수: CG 23, GT 28. CG 목록에 `5000`이 있고 `4900`이 없을 것
- `scanTimeFactor`: 512→1, 1024→4, 2048→16, 4096→64
- 추천: 성립 Mag 없음 / 512 통과 / 512 미달·1024 통과 / 둘 다 미달 4개 분기

## 명시적 가정

**FOV 여유 마진을 두지 않습니다.** `FOV >= 필요 FOV`만 만족하면 성립으로
봅니다. 실제 레시피는 스테이지 배치 오차나 어드레싱 오프셋을 위한 마진이
필요할 수 있으나, 사내 기준이 없어 임의의 계수를 도입하지 않았습니다. 마진이
필요한 사용자는 **패턴 수를 1~2개 늘려 입력**하는 것으로 우회할 수 있습니다.
사내 기준이 정해지면 마진 계수를 입력으로 추가하는 것이 자연스러운 확장입니다.

## 범위에서 제외 (YAGNI)

- 역방향 조회: "원하는 nm/px → 필요 배율"
- 배율 비교 차트
- 백엔드 엔드포인트 및 저장 기능
- 레시피 데이터(`AmpRow.Mag`, `"50.0K"` 문자열 포맷)와의 연동 —
  표기 체계가 msr 쪽과 달라 별도 정규화가 필요하며, 이번 범위 밖입니다

## 변경 파일 요약

| 파일 | 변경 |
| --- | --- |
| `docs/datatables/cdsem_mag_pixel_table.txt` | 정정 2건 (단위 nm→µm, 4900→5000) |
| `front-dev-home/app/utils/magPixel.ts` | 신규 — 순수 계산 레이어 |
| `front-dev-home/app/utils/magPixel.test.ts` | 신규 |
| `front-dev-home/app/pages/mag-pixel.vue` | 신규 — 셋업 가이드 화면 |
| `front-dev-home/app/components/nav/AppHeader.vue` | 헤더 우측 아이콘 추가 |
| `front-dev-home/app/components/nav/FeatureTabs.vue` | `INFO_PATHS`에 `/mag-pixel` |
| `front-dev-home/app/utils/skewvoirAnalysis/gallery.ts` | `pixelSizeNm` 파생 필드 |
| `front-dev-home/app/components/ebeam/skewvoir/gallery/ImageViewer.vue` | 파생값 표시 |
