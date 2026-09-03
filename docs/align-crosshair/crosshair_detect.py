"""도구가 그린 crosshair 의 *기하 기반* 검출 — 흰 배경에 강건한 v2.

배경:
  기존 `align_point_correction._detect_existing_crosshair` 는 top-hat(국소 대비)에
  의존한다. crosshair 가 흰 배경 위에 있거나 배경이 매우 밝으면 "주변보다 밝지 않다"
  → top-hat 응답이 0 → 선이 사라진다. 실데이터에서 crosshair 가 있는데도 "없음"
  으로 나오던(no_crosshair_drawn 229/339) 구조적 원인.

v2 아이디어 — *밝기 대비* 가 아니라 *모양* 으로 찾는다:
  1. 절대 고임계 saturation mask: bright = (gray >= SAT_THRESH). crosshair 는 순백(255)에 가깝다.
  2. 방향성 형태학 opening:
       - 가로선: open(bright, kernel=(SPAN_RATIO·W, 1)) → 긴 가로 얇은 런만 생존(2D blob 사망).
       - 세로선: open(bright, kernel=(1, SPAN_RATIO·H)).
     배경이 부분적으로 밝아도 crosshair 는 프레임을 가로지르므로 살아남는다.
  3. opened mask 의 row/col coverage projection → argmax = 선 위치, 교점 = (cx, cy).
  4. 배경이 통째로 saturate(bright_fraction 큼)된 극단은 guard 로 "모호" 처리 — 진짜 없음(E)과 구분.

반환 시그니처는 기존 검출기와 동일: (xy|None, confidence, debug).
나중에 align_point_correction 에서 한 줄 교체로 swap 가능.

데이터를 Mac 으로 못 가져오므로([[feedback_no_office_data_to_mac]]), 검증은 디버그 덤프
하니스(probe)로 한다 — 오피스에서 실 msr 이미지에 대해 old vs v2 + 중간 mask 를 montage
JPEG 으로 덤프하고, 그걸 보고 SAT_THRESH / SPAN_RATIO 등을 튜닝한다.

실행:
    uv run python poc/workflow_3/align/diagnostics/crosshair_detect.py     # 실데이터 있으면 probe, 없으면 self-test
"""

import json
import time
from dataclasses import dataclass

import cv2
import numpy as np

from poc.workflow_3 import DEBUG_IMAGE_DIR

# ====================================================================
# 튜닝 상수 — CLAUDE.md 규칙상 argparse 미사용. probe 덤프 보고 실데이터로 조정.
# ====================================================================

# crosshair 를 순백으로 보는 절대 임계 (montage 표시/디버그용 대표값).
SAT_THRESH = 235
# 다중 임계 ladder — 밝은→어두운 순. full-span 선을 찾는 첫 임계를 채택(약간 어두운 crosshair 회수).
SAT_THRESH_LADDER = (235, 215, 195)
# 선으로 인정할 최소 span (프레임 한 변 대비). full-span 직선이라도 center gap 때문에 끊기므로 0.30.
SPAN_RATIO = 0.30
# center gap 등 선의 끊김을 메우는 close 커널 크기 (프레임 한 변 대비). opening 전에 적용.
GAP_BRIDGE_RATIO = 0.08
# 선 두께 상한(px) 근사 — coverage 가 이보다 두꺼운 band 면 blob 으로 의심(신뢰도 하락).
MAX_THICKNESS_PX = 6
# 배경 전체가 saturate 된 경우 — bright 비율이 이보다 크면 검출 모호(low conf).
MAX_BRIGHT_FRACTION = 0.45
# 스케일바/축라벨 영역 마스킹 (하단/좌측) — 가로선·세로선 오검출 방지.
BOTTOM_SCALEBAR_RATIO = 0.10
LEFT_AXIS_RATIO = 0.05

_BGR_GREEN = (80, 200, 80)
_BGR_RED = (60, 60, 220)
_BGR_WHITE = (240, 240, 240)


@dataclass
class CrosshairResult:
    xy: tuple[int, int] | None
    confidence: float
    debug: dict

    def as_tuple(self) -> tuple[tuple[int, int] | None, float, dict]:
        """기존 검출기와 동일한 (xy, conf, debug) 튜플."""
        return self.xy, self.confidence, self.debug


# ====================================================================
# 핵심 검출.
# ====================================================================


def _centroid_around(signal: np.ndarray, idx: int, band: int = 3) -> float:
    """argmax 주변 ±band 가중 평균으로 sub-pixel 좌표."""
    lo = max(0, idx - band)
    hi = min(signal.shape[0], idx + band + 1)
    win = signal[lo:hi].astype(np.float64)
    if win.sum() <= 0:
        return float(idx)
    coords = np.arange(lo, hi, dtype=np.float64)
    return float((coords * win).sum() / win.sum())


def _line_from_opened(
    opened: np.ndarray, axis: str, span_min_px: float,
) -> tuple[float | None, dict]:
    """방향성 opening 결과에서 선 위치(sub-pixel)를 뽑는다.

    axis='h' → 가로선: 각 row 의 bright 픽셀 수(coverage) projection, argmax = y.
    axis='v' → 세로선: 각 col coverage projection, argmax = x.
    peak coverage 가 span_min_px 미만이면 선 없음(None). 고-coverage band 가 두꺼우면
    (blob 의심) thin_ok=False 로 debug 에 남긴다.
    """
    cov = opened.sum(axis=1) if axis == "h" else opened.sum(axis=0)
    cov = cov.astype(np.float32)
    idx = int(np.argmax(cov))
    peak = float(cov[idx])
    info = {"peak": peak, "argmax": idx, "span_min_px": span_min_px}
    if peak < span_min_px:
        info["reason"] = "below_span"
        return None, info
    band = int((cov >= 0.5 * peak).sum())  # 고-coverage 줄 수 ≈ 선 두께(px).
    info["band"] = band
    info["thin_ok"] = bool(band <= MAX_THICKNESS_PX * 3)
    sub = _centroid_around(cov, idx)
    return sub, info


def _detect_at_threshold(gray: np.ndarray, sat_thresh: int, span_ratio: float) -> tuple:
    """단일 saturation 임계에서 full-span 십자 검출 → (xy|None, confidence, info).

    opening 전에 *선 방향으로 close* 해서 center gap 등 끊김을 메운다 — full-span 직선이
    중앙에서 끊겨 longest-run 이 span 미달로 탈락하던 케이스(S 45장)를 회수.
    """
    h, w = gray.shape[:2]
    bright = (gray >= sat_thresh).astype(np.uint8)
    bright[int((1.0 - BOTTOM_SCALEBAR_RATIO) * h):, :] = 0  # 스케일바(하단) 제외.
    bright[:, : max(1, int(LEFT_AXIS_RATIO * w))] = 0        # 축라벨(좌측) 제외.

    bright_frac = float(bright.mean())
    info: dict = {"bright_fraction": bright_frac, "sat_thresh": sat_thresh}
    if bright_frac > MAX_BRIGHT_FRACTION:
        info["reason"] = "too_bright"
        return None, 0.0, info

    lh = max(15, int(span_ratio * w))
    lv = max(15, int(span_ratio * h))
    gap_h = max(3, int(GAP_BRIDGE_RATIO * w))
    gap_v = max(3, int(GAP_BRIDGE_RATIO * h))
    # 가로선: 가로로 close(gap 메움) → 가로로 open(긴 얇은 런만).
    bright_h = cv2.morphologyEx(bright, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (gap_h, 1)))
    h_mask = cv2.morphologyEx(bright_h, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (lh, 1)))
    bright_v = cv2.morphologyEx(bright, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (1, gap_v)))
    v_mask = cv2.morphologyEx(bright_v, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, lv)))

    cy, h_info = _line_from_opened(h_mask, "h", span_ratio * w)
    cx, v_info = _line_from_opened(v_mask, "v", span_ratio * h)
    info["h_line"] = h_info
    info["v_line"] = v_info
    if cy is None:
        info["reason"] = "no_h_line"
        return None, 0.0, info
    if cx is None:
        info["reason"] = "no_v_line"
        return None, 0.0, info

    h_cov = h_info["peak"] / max(w, 1)
    v_cov = v_info["peak"] / max(h, 1)
    thin_penalty = 1.0
    if not h_info.get("thin_ok", True):
        thin_penalty *= 0.5
    if not v_info.get("thin_ok", True):
        thin_penalty *= 0.5
    confidence = float(min(1.0, 0.5 * (h_cov + v_cov)) * thin_penalty)
    info["reason"] = "ok"
    info["sub_pixel"] = [cx, cy]
    return (int(round(cx)), int(round(cy))), confidence, info


def detect_crosshair(
    gray: np.ndarray,
    *,
    sat_thresh_ladder: tuple = SAT_THRESH_LADDER,
    span_ratio: float = SPAN_RATIO,
) -> CrosshairResult:
    """기하 기반 full-span 십자 검출 — 다중 임계 ladder.

    밝은→어두운 임계 순으로 시도하여, 양 축 full-span 선을 찾는 첫 임계를 채택한다
    (약간 어두운 crosshair 회수). 어느 임계에서도 못 찾으면 미검출.
    debug.reason: "ok" | "no_line_any_thresh" | (마지막 임계의 사유).
    """
    attempts = []
    last_info: dict = {}
    for sat in sat_thresh_ladder:
        xy, conf, info = _detect_at_threshold(gray, sat, span_ratio)
        attempts.append({"sat": sat, "reason": info.get("reason"), "conf": round(conf, 3)})
        last_info = info
        if xy is not None:
            info["attempts"] = attempts
            return CrosshairResult(xy, conf, info)
    last_info["attempts"] = attempts
    last_info.setdefault("reason", "no_line_any_thresh")
    return CrosshairResult(None, 0.0, last_info)


# ====================================================================
# 디버그 덤프 하니스 (probe) — 오피스에서 실데이터로 튜닝.
# ====================================================================


def _panel(img_gray_or_bgr: np.ndarray, label: str, height: int) -> np.ndarray:
    """패널 한 장을 height 로 리사이즈하고 상단에 라벨을 얹어 BGR 로 반환."""
    img = img_gray_or_bgr
    if img.ndim == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    hh, ww = img.shape[:2]
    scale = height / float(hh)
    img = cv2.resize(img, (max(1, int(ww * scale)), height), interpolation=cv2.INTER_NEAREST)
    cv2.rectangle(img, (0, 0), (img.shape[1] - 1, 18), (0, 0, 0), -1)
    cv2.putText(img, label, (4, 13), cv2.FONT_HERSHEY_SIMPLEX, 0.45, _BGR_WHITE, 1, cv2.LINE_AA)
    return img


def _draw_full_lines(canvas: np.ndarray, xy, color) -> None:
    """프레임 전체를 가로지르는 가는 십자 보조선."""
    if xy is None:
        return
    x, y = xy
    h, w = canvas.shape[:2]
    cv2.line(canvas, (0, y), (w - 1, y), color, 1, cv2.LINE_AA)
    cv2.line(canvas, (x, 0), (x, h - 1), color, 1, cv2.LINE_AA)
    cv2.circle(canvas, (x, y), 4, color, 1, cv2.LINE_AA)


def build_probe_montage(
    gray: np.ndarray,
    *,
    v2: CrosshairResult,
    old_xy: tuple[int, int] | None,
) -> np.ndarray:
    """[원본+old(red)/v2(green) overlay | bright | h_mask | v_mask] montage 한 장."""
    overlay = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    _draw_full_lines(overlay, old_xy, _BGR_RED)        # 기존 검출기 결과(빨강).
    _draw_full_lines(overlay, v2.xy, _BGR_GREEN)       # v2 결과(초록).

    bright = (gray >= SAT_THRESH).astype(np.uint8) * 255
    lh = max(15, int(SPAN_RATIO * gray.shape[1]))
    lv = max(15, int(SPAN_RATIO * gray.shape[0]))
    h_mask = cv2.morphologyEx((gray >= SAT_THRESH).astype(np.uint8),
                              cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (lh, 1))) * 255
    v_mask = cv2.morphologyEx((gray >= SAT_THRESH).astype(np.uint8),
                              cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, lv))) * 255

    height = 260
    v2_str = f"v2={v2.xy} conf={v2.confidence:.2f} ({v2.debug.get('reason')})"
    old_str = f"old={old_xy}"
    panels = [
        _panel(overlay, f"{old_str} | {v2_str}", height),
        _panel(bright, f"bright>={SAT_THRESH} frac={v2.debug.get('bright_fraction', 0):.2f}", height),
        _panel(h_mask, "h_mask (open)", height),
        _panel(v_mask, "v_mask (open)", height),
    ]
    return np.hstack(panels)


def probe(limit_per_recipe: int | None = None) -> str:
    """실 align_images msr 이미지에 대해 old vs v2 검출을 montage 로 덤프 + 요약 텍스트.

    출력: DEBUG_IMAGE_DIR/crosshair_probe/<ts>/<recipe_tag>/<msr>_probe.jpg + summary.txt
    """
    from poc.workflow_3.align.assets import (
        iter_msr_images,
        iter_recipe_dirs,
        load_gray,
        resolve_assets,
    )
    # 기존 검출기 — 비교 baseline (lazy import: align_point_correction 가 VLM client 등을 끌어옴).
    from poc.workflow_3.util import image_utils  # noqa: F401  (import 경로 sanity)
    from poc.workflow_3.align.diagnostics.align_point_correction import _detect_existing_crosshair

    leaves = iter_recipe_dirs()
    if not leaves:
        print("[ERROR] align_images 아래 recipe 가 없습니다 - probe 불가.")
        return "no_assets"

    ts = time.strftime("%Y%m%d_%H%M%S")
    out_root = DEBUG_IMAGE_DIR / "crosshair_probe" / ts
    out_root.mkdir(parents=True, exist_ok=True)

    # 전역 카운트 + S/E 분리(라벨별). E 는 ground truth 상 crosshair 없음 →
    # E 에서 검출되면 false positive. union = old∨v2 (ensemble ceiling).
    from poc.workflow_3.align.diagnostics.align_point_correction import _tool_label
    cnt = {lab: {"n": 0, "v2": 0, "old": 0, "union": 0} for lab in ("S", "E", "?")}
    n_total = n_v2 = n_old = n_both = n_neither = n_union = 0
    reason_counts: dict[str, int] = {}
    safe = lambda s: (s or "_").replace("/", "_").replace("\\", "_")  # noqa: E731

    for leaf in leaves:
        assets = resolve_assets(leaf)
        tag = safe(f"{assets.eqp_id}__{assets.class_name}__{assets.recipe_id}")
        recipe_dir = out_root / tag
        msr_images = iter_msr_images(assets)
        if limit_per_recipe is not None:
            msr_images = msr_images[:limit_per_recipe]
        for msr_path in msr_images:
            try:
                gray = load_gray(msr_path)
                v2 = detect_crosshair(gray)
                old_xy, _old_conf, _old_dbg = _detect_existing_crosshair(gray)
            except Exception as exc:
                print(f"[WARNING] {msr_path.name}: probe 실패 - {type(exc).__name__}: {exc}")
                continue
            n_total += 1
            lab = _tool_label(msr_path.name)
            lab = lab if lab in ("S", "E") else "?"
            has_v2 = v2.xy is not None
            has_old = old_xy is not None
            n_v2 += int(has_v2)
            n_old += int(has_old)
            n_both += int(has_v2 and has_old)
            n_neither += int(not has_v2 and not has_old)
            n_union += int(has_v2 or has_old)
            cnt[lab]["n"] += 1
            cnt[lab]["v2"] += int(has_v2)
            cnt[lab]["old"] += int(has_old)
            cnt[lab]["union"] += int(has_v2 or has_old)
            reason_counts[v2.debug.get("reason", "?")] = reason_counts.get(v2.debug.get("reason", "?"), 0) + 1

            recipe_dir.mkdir(parents=True, exist_ok=True)
            montage = build_probe_montage(gray, v2=v2, old_xy=old_xy)
            cv2.imwrite(str(recipe_dir / f"{msr_path.stem}_probe.jpg"), montage,
                        [int(cv2.IMWRITE_JPEG_QUALITY), 88])

    summary = {
        "ts": ts, "total": n_total,
        "v2_detected": n_v2, "old_detected": n_old, "union_detected": n_union,
        "both_detected": n_both, "neither_detected": n_neither,
        "v2_only": n_v2 - n_both, "old_only": n_old - n_both,
        "by_label": cnt,
        "v2_reason_counts": reason_counts,
        "params": {"SAT_THRESH_LADDER": list(SAT_THRESH_LADDER), "SPAN_RATIO": SPAN_RATIO,
                   "GAP_BRIDGE_RATIO": GAP_BRIDGE_RATIO,
                   "MAX_THICKNESS_PX": MAX_THICKNESS_PX, "MAX_BRIGHT_FRACTION": MAX_BRIGHT_FRACTION},
    }
    (out_root / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[INFO] crosshair probe 완료 → {out_root}")
    print(f"[INFO] total={n_total}  v2={n_v2}  old={n_old}  union(old∨v2)={n_union}  "
          f"both={n_both}  v2_only={n_v2 - n_both}  old_only={n_old - n_both}  neither={n_neither}")
    for lab in ("S", "E", "?"):
        c = cnt[lab]
        if c["n"]:
            print(f"[INFO]   {lab}: n={c['n']}  v2={c['v2']}  old={c['old']}  union={c['union']}")
    print(f"[INFO] v2 reason counts: {reason_counts}")
    print("[INFO] 기대: S 의 union 이 n 에 가까울수록(검출↑), E 의 v2/old 는 0 에 가까울수록(false positive↓) 좋다.")
    print("[INFO] montage 패널: [원본+old(red)/v2(green) | bright | h_mask | v_mask]")
    return "success"


# ====================================================================
# 합성 self-test (Mac).
# ====================================================================


def _make_test_image(*, bg: int, draw_cross: bool, cross_val: int = 255,
                     cx: int = 200, cy: int = 150) -> np.ndarray:
    """배경 bg 의 gray 이미지에 (옵션) 흰 crosshair 를 그린다. 약간의 텍스처 추가."""
    img = np.full((300, 400), bg, dtype=np.uint8)
    # 약한 텍스처 — 균일 배경에서 Otsu 등 엣지케이스 회피.
    img = cv2.add(img, (np.random.RandomState(0).randint(0, 12, img.shape)).astype(np.uint8))
    if draw_cross:
        img[cy - 1:cy + 2, :] = cross_val   # 가로선 (두께 3)
        img[:, cx - 1:cx + 2] = cross_val   # 세로선
    return img


def _self_test() -> bool:
    """3 케이스: (1) 어두운 배경+crosshair, (2) 밝은 배경+crosshair, (3) crosshair 없음."""
    ok = True

    # (1) 어두운 배경 — 검출되고 위치 정확해야.
    img1 = _make_test_image(bg=40, draw_cross=True, cx=200, cy=150)
    r1 = detect_crosshair(img1)
    assert r1.xy is not None, "(1) 어두운 배경 crosshair 미검출"
    assert abs(r1.xy[0] - 200) <= 3 and abs(r1.xy[1] - 150) <= 3, f"(1) 위치 오차 큼: {r1.xy}"
    print(f"[INFO] (1) dark bg: detected {r1.xy} conf={r1.confidence:.2f}  ← top-hat 도 되던 쉬운 케이스")

    # (2) 밝은 배경(200) — top-hat 이 죽던 케이스. v2 는 절대임계라 crosshair(255)가 bright mask 에 남아 검출돼야.
    img2 = _make_test_image(bg=200, draw_cross=True, cx=200, cy=150)
    r2 = detect_crosshair(img2)
    if r2.xy is not None and abs(r2.xy[0] - 200) <= 3 and abs(r2.xy[1] - 150) <= 3:
        print(f"[INFO] (2) bright bg(200): detected {r2.xy} conf={r2.confidence:.2f}  ← top-hat 이 실패하던 핵심 케이스 통과")
    else:
        print(f"[ERROR] (2) bright bg: v2 도 실패 {r2.xy} (reason={r2.debug.get('reason')})")
        ok = False

    # (3) crosshair 없음 — None 이어야 (false positive 없어야).
    img3 = _make_test_image(bg=40, draw_cross=False)
    r3 = detect_crosshair(img3)
    if r3.xy is None:
        print(f"[INFO] (3) no crosshair: None (reason={r3.debug.get('reason')})  ← false positive 없음")
    else:
        print(f"[ERROR] (3) no crosshair 인데 검출됨: {r3.xy}")
        ok = False

    # montage 생성도 예외 없이 되는지.
    _ = build_probe_montage(img2, v2=r2, old_xy=(190, 140))

    print("[INFO] self-test 통과." if ok else "[ERROR] self-test 일부 실패.")
    return ok


def run() -> str:
    # align_images 가 있으면(오피스) probe, 없으면(Mac) self-test.
    try:
        from poc.workflow_3.align.assets import iter_recipe_dirs
        has_data = bool(iter_recipe_dirs())
    except Exception:
        has_data = False
    if has_data:
        return probe()
    print("[WARNING] align_images 데이터 없음 - 합성 self-test 로 대체합니다.\n")
    return "success" if _self_test() else "selftest_failed"


if __name__ == "__main__":
    raise SystemExit(0 if run() == "success" else 1)
