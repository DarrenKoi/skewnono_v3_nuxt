"""cond.txt 좌표로 white box 테두리 / crosshair 선을 inpaint 해 지운다.

왜 지우나
--------
- rcp 의 **white box** 는 웨이퍼 위에 그려 넣은 주석(unique-area 표시)일 뿐
  실제 영상 내용이 아니다 ([[project_rcp_white_box_unique_area]]).
- msr 의 **crosshair** 는 CV matcher 의 distractor 라 매칭 전에 제거해야 한다
  ([[project_msr_crosshair_cv_distractor]]).

핵심 원칙
--------
**그려진 '선'만 마스크한다. white box 안쪽은 실제 내용이므로 절대 채우지 않는다.**
박스는 테두리 strip 만, crosshair 는 FOV 전체를 가로지르는 두 선만 마스크하고
cv2.inpaint(TELEA) 로 주변 픽셀로 메운다.

좌표계
------
cond.txt 의 cursor 좌표는 Pixel 의 **10배 oversample** 프레임이다 →
이미지 px = cursor / 10 (OVERSAMPLE). 1024-px 이미지 샘플이 아직 없어
이 비율은 오피스 실데이터에서 검증 필요 ([[project_align_cond_files_and_coords]]).
"""

import cv2
import numpy as np

from poc.workflow_3.align.cond_file import CondInfo, cond_for_image

# cursor 좌표 → 이미지 px 축소 비율 (cursor frame = Pixel × OVERSAMPLE).
OVERSAMPLE = 10
# 그려진 주석 선의 두께(px). 실선 코어는 얇으므로 1, halo 는 dilate 로 덮는다.
DEFAULT_THICKNESS = 1
# 선 코어 밖으로 마스크를 넓히는 여유(px). halo 를 덮되, 너무 키우면 inpaint 가
# 실제 texture 를 번지게(smear) 하니 작게 둔다. 실데이터 눈검증 결과 1 이 최적
# (3 은 over-inpaint 번짐). 흐릿하면 CLEAN_DILATE env 로 일시 상향.
DEFAULT_DILATE = 1
# inpaint 반경(px).
DEFAULT_INPAINT_RADIUS = 2


def cursor_to_image(xy, oversample=OVERSAMPLE):
    """cursor 프레임 좌표를 이미지 px 로 변환한다 (x/oversample, y/oversample)."""
    x, y = xy
    return x / float(oversample), y / float(oversample)


def build_removal_mask(
    shape_hw,
    *,
    box_ltrb=None,
    crosshair_xy=None,
    oversample=OVERSAMPLE,
    thickness=DEFAULT_THICKNESS,
    dilate=DEFAULT_DILATE,
):
    """지울 선(박스 테두리 + crosshair)만 255 로 칠한 uint8 마스크를 만든다.

    ``shape_hw`` 는 (height, width). box/crosshair 는 cursor 프레임 raw 좌표이며
    내부에서 oversample 로 나눠 이미지 px 로 변환한다. ``dilate`` 로 선 코어 밖을
    넓혀 anti-aliasing·JPEG halo 까지 덮는다(잔상 방지).
    """
    h, w = shape_hw[:2]
    mask = np.zeros((h, w), dtype=np.uint8)
    t = max(1, int(thickness))

    if box_ltrb is not None:
        left, top = cursor_to_image(box_ltrb[:2], oversample)
        r, b = cursor_to_image(box_ltrb[2:], oversample)
        # 테두리만(채우지 않음): thickness 두께의 사각형 outline.
        cv2.rectangle(mask, (round(left), round(top)), (round(r), round(b)), 255, t)

    if crosshair_xy is not None:
        cx, cy = cursor_to_image(crosshair_xy, oversample)
        cxi, cyi = round(cx), round(cy)
        cv2.line(mask, (cxi, 0), (cxi, h - 1), 255, t)     # 세로선 (높이 전체)
        cv2.line(mask, (0, cyi), (w - 1, cyi), 255, t)     # 가로선 (폭 전체)

    if dilate and dilate > 0:
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE,
                                      (2 * int(dilate) + 1, 2 * int(dilate) + 1))
        mask = cv2.dilate(mask, k)

    return mask


def clean_image(
    image,
    cond: CondInfo,
    *,
    oversample=OVERSAMPLE,
    thickness=DEFAULT_THICKNESS,
    dilate=DEFAULT_DILATE,
    inpaint_radius=DEFAULT_INPAINT_RADIUS,
):
    """CondInfo 의 box/crosshair 선을 inpaint 로 지운 이미지를 돌려준다.

    지울 게 없으면(box·crosshair 모두 None) 원본을 그대로 반환한다.
    cond.pixel 과 이미지 크기가 다르면 cursor 좌표를 로드 크기로 먼저 보정한다
    (cond_for_image — 멱등이라 상위 레이어가 이미 보정했어도 무해).
    """
    cond = cond_for_image(cond, image.shape[:2])
    mask = build_removal_mask(
        image.shape[:2],
        box_ltrb=cond.box_ltrb,
        crosshair_xy=cond.crosshair_xy,
        oversample=oversample,
        thickness=thickness,
        dilate=dilate,
    )
    if not mask.any():
        return image
    return cv2.inpaint(image, mask, inpaint_radius, cv2.INPAINT_TELEA)


def main():
    """합성 데모: anti-aliasing + JPEG halo 가 있는 주석을 dilate 유무로 비교.

    before | after(dilate=0, 잔상) | after(default, 잔상 제거) 를 가로로 저장한다.
    """
    import os

    out_dir = os.path.dirname(__file__)
    rng = np.random.default_rng(0)
    base = np.clip(110 + rng.integers(-12, 12, (512, 512)), 0, 255).astype(np.uint8)
    # 주석을 anti-aliased(LINE_AA) 로 그려 부드러운 shoulder 를 만든다.
    cv2.rectangle(base, (160, 160), (352, 352), 255, 2, cv2.LINE_AA)
    cv2.line(base, (210, 0), (210, 511), 255, 2, cv2.LINE_AA)
    cv2.line(base, (0, 256), (511, 256), 255, 2, cv2.LINE_AA)
    # JPEG 왕복으로 edge ringing/halo 추가 (실제 다운로드 이미지 흉내).
    ok, buf = cv2.imencode(".jpg", base, [cv2.IMWRITE_JPEG_QUALITY, 80])
    img = cv2.imdecode(buf, cv2.IMREAD_GRAYSCALE) if ok else base

    cond = CondInfo(scope="OM", pixel=(512, 512),
                    box_ltrb=(1600, 1600, 3520, 3520), crosshair_xy=(2100, 2560))
    no_dilate = clean_image(img, cond, dilate=0)
    with_dilate = clean_image(img, cond)             # DEFAULT_DILATE
    panel = np.hstack([img, no_dilate, with_dilate])
    dst = os.path.join(out_dir, "clean_align_dilate_demo.jpg")
    cv2.imwrite(dst, panel)
    print(f"[INFO] before | after(dilate=0) | after(dilate={DEFAULT_DILATE}): {dst}")


if __name__ == "__main__":
    main()
