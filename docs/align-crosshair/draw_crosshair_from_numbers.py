"""msr 파일의 숫자 2개로 crosshair(측정/align point)를 단일 이미지에 그린다.

box vs crosshair
----------------
- white box 는 **영역** → 숫자 4개(l,t,r,b).  `draw_white_box_single.py` 참고.
- crosshair 는 **점 하나** → 숫자 2개(cx, cy). 십자 두 선은 FOV 전체에 걸치므로
  교차점(cx, cy) 하나만 저장하면 된다(선 길이는 화면 전체로 암시).

좌표계
------
숫자는 box 와 **같은 native 프레임(NATIVE_SIZE, 기본 5120)** 의 px 로 가정한다.
실제로 보는 msr 이미지는 더 작을 수 있으므로(예: 512x512), 배경 크기에 맞게
자동 스케일한다. (2097,2561)@5120 → 512 이미지에서 (210,256) 처럼.

배경 두 가지
-----------
1) BACKGROUND_IMAGE 경로가 있으면 그 실제 msr 이미지(S=성공, crosshair 있음) 위에 그린다.
   → 그린 십자가 실제 십자에 겹치면 좌표계(NATIVE_SIZE) 확정.
2) 없으면 옅은 합성 배경(VIEW_SIZE)에 그린다 — 위치만 확인.

CLI 인자 없음. HARDCODE ZONE 만 고쳐서
`uv run python poc/workflow_2/draw_crosshair_from_numbers.py` 로 실행.
"""

import os

import cv2
import numpy as np

# ============================================================================
# HARDCODE ZONE — 여기만 고치면 됩니다
# ============================================================================
TWO_NUMBERS = (2097, 2561)     # msr 에서 찾은 crosshair 숫자 2개 (cx, cy)
NATIVE_SIZE = 5120             # 그 숫자가 사는 원본 프레임 한 변(px) — box 와 동일 가정
BACKGROUND_IMAGE = ""          # 실제 msr 이미지 경로(없으면 "" → 합성 배경)
VIEW_SIZE = 512                # 합성 배경일 때 저장(보기) 한 변(px) — msr 이미지 크기에 맞춤
# ============================================================================

OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "crosshair_single.jpg")


def make_synthetic_background(w, h):
    """합성 배경: 옅은 그라데이션 + 10% 그리드 + 중앙 기준 십자선(옅은 노랑)."""
    grad = np.linspace(40, 90, h, dtype=np.uint8).reshape(h, 1)
    img = cv2.cvtColor(np.repeat(grad, w, axis=1), cv2.COLOR_GRAY2BGR)
    for i in range(1, 10):
        x, y = round(w * i / 10.0), round(h * i / 10.0)
        cv2.line(img, (x, 0), (x, h - 1), (70, 70, 70), 1, cv2.LINE_AA)
        cv2.line(img, (0, y), (w - 1, y), (70, 70, 70), 1, cv2.LINE_AA)
    return img


def main():
    cx0, cy0 = (float(n) for n in TWO_NUMBERS)

    if BACKGROUND_IMAGE and os.path.exists(BACKGROUND_IMAGE):
        img = cv2.imread(BACKGROUND_IMAGE)
        if img is None:
            raise SystemExit(f"[ERROR] 이미지를 못 읽음: {BACKGROUND_IMAGE}")
        H, W = img.shape[:2]
        src = f"실제 msr 이미지 {os.path.basename(BACKGROUND_IMAGE)} ({W}x{H})"
    else:
        W = H = VIEW_SIZE
        img = make_synthetic_background(W, H)
        src = f"합성 배경 ({W}x{H}) — 실제 이미지 없음"

    sx, sy = W / float(NATIVE_SIZE), H / float(NATIVE_SIZE)
    cx, cy = cx0 * sx, cy0 * sy
    cxi, cyi = int(round(cx)), int(round(cy))

    inside = (0 <= cx <= W) and (0 <= cy <= H)
    fcx, fcy = W // 2, H // 2
    off_x, off_y = cx - fcx, cy - fcy      # 프레임 중심 대비 오프셋(=align target 위치)

    # crosshair: FOV 전체를 가로지르는 십자선(초록) — 실제 측정점 표시
    thick = max(1, W // 400)
    color = (0, 255, 0) if inside else (0, 0, 255)
    cv2.line(img, (cxi, 0), (cxi, H - 1), color, thick, cv2.LINE_AA)
    cv2.line(img, (0, cyi), (W - 1, cyi), color, thick, cv2.LINE_AA)
    cv2.circle(img, (cxi, cyi), max(3, W // 80), color, thick, cv2.LINE_AA)

    # 프레임 중심(빨강 마커)과의 오프셋을 눈으로 보이게
    cv2.drawMarker(img, (fcx, fcy), (0, 0, 255), cv2.MARKER_TILTED_CROSS,
                   W // 24, thick)

    cv2.rectangle(img, (0, 0), (W, 30), (20, 20, 20), -1)
    cap = (f"crosshair {TWO_NUMBERS}@{NATIVE_SIZE} -> ({cx:.0f},{cy:.0f}) on {W}px "
           f"| off-center=({off_x:+.0f},{off_y:+.0f})px {'' if inside else 'OUT!'}")
    cv2.putText(img, cap, (6, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.45,
                (255, 255, 255), 1, cv2.LINE_AA)

    cv2.imwrite(OUTPUT_PATH, img, [cv2.IMWRITE_JPEG_QUALITY, 92])
    print(f"[INFO] 배경: {src}")
    print(f"[INFO] crosshair@view=({cx:.1f},{cy:.1f})  frame-center=({fcx},{fcy})  "
          f"offset=({off_x:+.1f},{off_y:+.1f})px  inside={inside}")
    print(f"[INFO] 저장: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
