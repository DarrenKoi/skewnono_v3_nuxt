# align 기준 이미지 404 (align-image-404)

작성 2026-08-22. 요구사항은 대화에서 확정되었으며, 아래 "사용자가 요구한 것" 은
사용자가 말한 내용을 그대로 옮긴 것입니다. 구현 diff 에서 역으로 유추한 항목은
없습니다.

## 사용자가 요구한 것

1. **production 의 `recipe-search/recipe-image` 404 원인을 찾는다.**
   > "I found that there are many 404 errors in the production mode where
   > recipe-search/recipe-image. can you find the possible root-cause?"

2. **찾았으면 고친다.**
   > "go fix"

요구는 이 두 줄이 전부입니다. 범위는 "production 에서 다수 발생하는 404 를
없앤다" 이며, 그 이상은 요구되지 않았습니다.

## 진단 (구현 전에 확정된 것)

`recipe-image` 라우트의 404 는 출처가 하나뿐입니다 — `fetch_recipe_image` 의
`LookupError`, 즉 **장비 FTP 에 그 파일이 없다**는 뜻입니다
(`back_dev_home/ebeam/recipe_search/routes.py`). 따라서 404 한 건은 백엔드가
브라우저에게 없는 파일 이름을 내려보냈다는 뜻입니다.

이름을 내려보내는 경로는 두 갈래입니다.

| 경로 | 이름의 출처 | 검증 |
| --- | --- | --- |
| `param-detail` | `_list_raw_dirs` 의 폴더 listing | 검증됨 (listing 실패 시 파생 이름으로 폴백) |
| `align-images` | `rawfiles.align_reference_images()` 의 계산 | **검증 안 됨** |

`align_reference_images()` 는 `ALIGN_OPTICS` 를 그대로 돌려주어 응답이 언제나
`IMAP0001.jpeg` + `IMAP0002.jpeg` 두 장이었습니다. 그러나 align point 가 1
하나뿐인 recipe 가 존재합니다 — `docs/datatables/hitachi/recipe_idp.txt` 의
"align point 는 보통 1 과 2 두 개이고, 1 하나만 있는 recipe 도 있습니다" 이며,
같은 사실이 `rawfiles.align_optics` 의 docstring 에도 적혀 있습니다. 그런 recipe
마다 `IMAP0002.jpeg` 는 확정적으로 404 입니다.

home 에서 보이지 않은 이유는 `providers/mock.py` 의 `fetch_recipe_image` 가
**어떤 이름을 받아도** SVG 를 돌려주었기 때문입니다. 없는 파일이라는 값 자체가
home 의 value domain 에 없었으므로, 이 404 를 낼 수 있는 실행 경로가 아예
없었습니다.

재현 루프(HTTP 라우트를 실제로 태우고, 폴더에 있는 파일만 주는 가짜 장비를
붙인 것)에서 수정 전 코드가 red 임을 확인했습니다:
`MONITOR/CD_TOP_09 published IMAP0002.jpeg, which the tool answered 404 for`.

## 고쳐야 하는 것

1. **확인하지 않은 이름을 화면에 내려보내지 않는다.** align 이미지 이름도
   `param-detail` 과 같이 폴더 listing 에서 찾습니다.
2. **listing 을 못 한 경우와 이미지가 없는 경우를 구분한다.** ALIGNMENT FAIL
   화면에서 "장비가 답을 안 했다" 를 "이 recipe 는 align 이미지가 없다" 로
   보고하면 엔지니어가 있지도 않은 recipe 결함을 찾게 됩니다.
3. **home 이 이 404 를 재현할 수 있게 한다.** mock 이 없는 파일을 표현할 수
   없는 한, 같은 종류의 결함은 계속 production 이 알려 줄 때까지 보이지 않습니다.
4. **회귀 테스트는 화면이 실제로 하는 왕복이어야 한다** — `align-images` 가
   내려준 모든 이름이 `recipe-image` 에서 200 인가.

## 범위 밖 (명시적으로)

이번 변경이 세운 규칙 — **파일 이름을 화면에 내려보내는 쪽이 그 파일의 존재를
확인한다** — 을 아직 지키지 않는 자리가 두 곳 남아 있습니다. 둘 다 의도적으로
남겼으며, 이유는 아래와 같습니다.

### 1. `slot_sources` 의 listing 실패 폴백 (`param-detail`)

`rawfiles.slot_sources` 는 listing 을 선택 인자로 받고, 없으면 파생 이름
`{stem}.jpeg` 로 폴백합니다. HV-SEM 의 `img_meas1` 은 `IMMS0001-U.jpeg` 처럼
쪼개져 있으므로 그 파생 이름은 존재하지 않고, `ParamSettings.vue` ·
`CompareMatrix.vue` · `RecipeOpenView.vue` 가 그대로 `<img>` 로 만들어 404 가
됩니다. align 건과 같은 결함입니다.

남긴 이유는 **폴백을 없애는 쪽도 공짜가 아니기** 때문입니다. CD-SEM 에서는
파생 이름이 정답이므로, listing 이 한 번 실패했다고 슬롯을 통째로 버리면
멀쩡히 보이던 이미지가 사라집니다. 제대로 고치려면 `get_param_detail` 이
tool_type 을 받아 "CD-SEM 이면 파생, HV-SEM 이면 포기" 로 갈라야 하는데,
이는 양쪽 provider 와 라우트와 계약을 함께 바꾸는 일입니다. 게다가 office 에서
listing 이 실제로 실패하고 있다는 증거가 아직 없습니다.

확인 방법: `/admin-logs` 에서 status 404 · path 에 `recipe-image` 인 행의
`query_string` 을 읽어 `name` 이 `IMMS####.jpeg`(suffix 없는 bare stem)인지
봅니다. 그런 행이 있으면 이 항목이 실재하는 것이고, 그때는 tool_type 을
넘기는 쪽으로 고칩니다. 앱 로그의 `raw-folder listing failed` 도 같은 신호입니다.

### 2. `get_align_detail` 의 파생 이름

`AlignPoint["image"]` 는 여전히 `rawfiles.align_names(p_no)[0]` 로 계산됩니다
(`AlignPopup.vue` 가 소비). P.No 자체는 `wafer_align_info` 에서 온 실제 값이라
align-images 만큼 위험하지는 않지만, **이번 변경이 두 화면을 어긋나게
만들었습니다**: 장비가 align 이미지를 쪼갠다면 align-images 는 찾아내고
align-detail 은 404 입니다.

남긴 이유는 계약 변경이 필요하기 때문입니다. `AlignPoint["image"]` 는 파일
하나(`str | None`)인데 point 하나가 파일 여러 개일 수 있다면 목록이 되어야 하고,
`AlignPopup.vue` 도 따라 바뀝니다. 쪼개짐 자체가 아직 OFFICE-VERIFY 이고 이
경로에서 404 가 보고된 적은 없으므로, 근거가 생길 때 함께 하는 편이 낫습니다.

### 3. 그 밖

- align 이미지의 recipe 버전 대조. 2026-08-21 에 사용자가 철회했습니다.
