# 01 — Restore TIFF download on preview failure

**What to build:** when server-side TIFF → WebP preview conversion fails (corrupt or unsupported office TIFF), the skewvoir dashboard image card (`SemImage`) and the gallery grid (`EvidenceCard` via `views/Gallery`) must still offer a download link for the original TIFF — the parity that `ImageViewer`'s rail link and `SiteEvidenceDrawer` already have. Today the download anchor sits inside the success branch, so once the `<img>` errors, the failure branch shows only "이미지 없음" with no way to fetch the original — contradicting the behavior `msr_image/preview.py`'s docstring promises ("the frontend's `<img>` error state then shows 이미지 없음 **with the download link**").

**Why:** review Standards axis, hard violation, and the branch's merge blocker. The pre-branch TIFF card always offered the original download; this branch's failure branch removes it, so a corrupt office TIFF leaves the user with no way to fetch the original at all — a regression introduced exactly where the backend docstring stakes the opposite design constraint. `ImageViewer` and `SiteEvidenceDrawer` prove the intended pattern already exists in the same diff.

**Blocked by:** None — can start immediately.

**Status:** done (2026-08-09) — c9812af0 — 브라우저로 실패 경로 확인 완료

- [ ] `SemImage`'s load-failed / "이미지 없음" state renders the TIFF download anchor whenever the measured name is a TIFF
- [ ] Gallery's `EvidenceCard` offers the same download affordance on image error, not only a badge
- [ ] Behavior verified against a forced preview failure (e.g. mock serving `image/tiff` with undecodable bytes)
- [ ] `preview.py`'s documented promise matches the actual frontend behavior
