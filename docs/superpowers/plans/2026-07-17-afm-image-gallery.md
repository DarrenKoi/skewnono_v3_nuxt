# AFM Additional-Image Gallery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a tabbed gallery (Align / Tip / Capture / Result) of supplementary images to the AFM measurement detail page, backed by mock-generated placeholder SVGs served through the provider seam so Phase 2/3 can swap in real files unchanged.

**Architecture:** Backend gets two new provider-seam functions (`list_analysis_images`, `get_analysis_image_svg`) implemented in the mock (deterministic placeholder SVGs, mirroring `get_profile_image_svg`) and stubbed in office; the mock also populates `capture_dir_list`. Two new routes expose list + bytes. Frontend adds a `fetchAnalysisImages` composable method and an `AnalysisImages.vue` gallery (UTabs + thumbnail strip + UModal lightbox + per-image download), rendered on the detail page.

**Tech Stack:** Flask (backend, `pytest` 9.1.1 + `test_client`), Nuxt 4 + NuxtUI v4.6.1 (`UTabs`, `UModal`, `UCard`), TypeScript.

## Global Constraints

- Backend paths are repo-root-relative; run `pytest` from repo root: `.venv/bin/pytest back_dev_home/afm -q`.
- Frontend root is `front-dev-home/`; run `npm` there. Frontend tests: `npm run test` (node --test); gates: `npm run typecheck`, `npm run lint`.
- Four image types only: `align`, `tip`, `capture`, `tiff`. Anything else → route 404 / `[]` / `None`.
- The provider seam is sacred: every new data function lives in `data.py` delegating to `_provider()`, is implemented in `providers/mock.py`, and is stubbed in `providers/office.py` as `_not_connected()`. Never call a provider module directly from routes.
- Mock image bytes are `image/svg+xml` placeholders even though listed filenames end `.png`/`.tiff`/`.webp`. Determinism: seed every generated SVG via `_seed_for(...)` so repeated calls are byte-identical.
- Reuse existing utilities/idioms: composable methods mirror `fetchImage` (`joinApiPath(base, path)` + `{ query }` + in-flight `Map` de-dup); the lightbox mirrors the repo's `UModal` idiom (`defineModel('open')`, `#content` slot, `:ui` sizing); the per-image download mirrors `ProfileImage.vue`'s blob-download.
- Work on `main` (project convention); commit per task; do NOT push. The tree has UNRELATED concurrent user WIP (`.remember/`, `docs/` deletions, a "chat" feature). Each task `git add`s ONLY its explicit files — never `git add -A`, `git add .`, or `git stash`.
- Every commit message ends with the trailer:

  ```text
  Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01NHWMRqfxSYaLcagApFG1tB
  ```

---

### Task 1: Backend data layer — analysis-image functions + capture population

**Files:**
- Modify: `back_dev_home/afm/providers/mock.py`
- Modify: `back_dev_home/afm/data.py`
- Modify: `back_dev_home/afm/providers/office.py`
- Test: `back_dev_home/afm/tests/test_analysis_images.py` (create)

**Interfaces:**
- Produces (in `data.py`, delegating to `_provider()`):
  - `list_analysis_images(filename: str, image_type: str, tool_name: str | None = None) -> list[dict[str, str]]` — `[{"name","url"}]`, `[]` for unknown type / missing measurement / sentinel.
  - `get_analysis_image_svg(filename: str, image_type: str, name: str, tool_name: str | None = None) -> str | None` — SVG string or `None`.
- Produces (in `mock.py`): the two implementations, plus module constant `IMAGE_TYPE_FIELDS: dict[str, str]`.

- [ ] **Step 1: Write the failing test**

Create `back_dev_home/afm/tests/test_analysis_images.py`:

```python
"""Analysis-image gallery data-layer tests (active provider via data.py)."""

from back_dev_home.afm import data
from back_dev_home.afm.providers import mock


def _row_with(image_type):
    field = mock.IMAGE_TYPE_FIELDS[image_type]
    for row in data.list_afm_files(None):
        names = [n for n in row.get(field, []) if n != "no files"]
        if names:
            return row, names
    raise AssertionError(f"no mock measurement has {image_type} images")


def test_capture_dir_list_populated_for_every_row():
    for row in data.list_afm_files(None):
        assert row["capture_dir_list"]
        assert row["capture_dir_list"][0] != "no files"


def test_list_analysis_images_returns_entries_for_capture():
    row, names = _row_with("capture")
    images = data.list_analysis_images(row["filename"], "capture", row["tool_name"])
    assert [img["name"] for img in images] == names
    assert all("/images/capture/" in img["url"] for img in images)
    assert all(img["url"].startswith("/api/afm/files/") for img in images)


def test_list_analysis_images_unknown_type_is_empty():
    row = data.list_afm_files(None)[0]
    assert data.list_analysis_images(row["filename"], "bogus", row["tool_name"]) == []


def test_list_analysis_images_skips_sentinel():
    for row in data.list_afm_files(None):
        if row["align_dir_list"] == ["no files"]:
            assert data.list_analysis_images(row["filename"], "align", row["tool_name"]) == []
            return


def test_get_analysis_image_svg_valid_for_all_types():
    for image_type in ("align", "tip", "capture", "tiff"):
        row, names = _row_with(image_type)
        svg = data.get_analysis_image_svg(row["filename"], image_type, names[0], row["tool_name"])
        assert isinstance(svg, str)
        assert svg.startswith("<svg")


def test_get_analysis_image_svg_rejects_bad_inputs():
    row, names = _row_with("capture")
    assert data.get_analysis_image_svg(row["filename"], "bogus", names[0], row["tool_name"]) is None
    assert data.get_analysis_image_svg(row["filename"], "capture", "not-real.png", row["tool_name"]) is None
    assert data.get_analysis_image_svg("no-such-file.csv", "capture", names[0], row["tool_name"]) is None


def test_get_analysis_image_svg_is_deterministic():
    row, names = _row_with("capture")
    a = data.get_analysis_image_svg(row["filename"], "capture", names[0], row["tool_name"])
    b = data.get_analysis_image_svg(row["filename"], "capture", names[0], row["tool_name"])
    assert a == b
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest back_dev_home/afm/tests/test_analysis_images.py -q`
Expected: FAIL — `AttributeError: module 'back_dev_home.afm.data' has no attribute 'list_analysis_images'` (and `mock.IMAGE_TYPE_FIELDS` missing).

- [ ] **Step 3: Populate `capture_dir_list` in the mock row builder**

In `back_dev_home/afm/providers/mock.py`, find the row dict where `"capture_dir_list": ["no files"],` is set (~line 406) and replace it with a populated list (the `clean_filename` and `sites` locals are already in scope there):

```python
            "capture_dir_list": [f"{clean_filename}_{sites[0]}_capture.png"],
```

- [ ] **Step 4: Add the `urllib.parse.quote` import and the type map + accent map**

In `mock.py`, add to the imports at the top (after the existing stdlib imports):

```python
from urllib.parse import quote
```

Then add these module-level constants near the other constants (e.g. after `STATE_CODES`):

```python
IMAGE_TYPE_FIELDS: dict[str, str] = {
    "align": "align_dir_list",
    "tip": "tip_dir_list",
    "capture": "capture_dir_list",
    "tiff": "tiff_dir_list",
}

_IMAGE_TYPE_ACCENT: dict[str, str] = {
    "align": "#2563eb",
    "tip": "#d97706",
    "capture": "#7c3aed",
    "tiff": "#0f766e",
}
```

- [ ] **Step 5: Implement the two mock functions**

In `mock.py`, add both functions after `get_profile_image_svg` (near line 292):

```python
def list_analysis_images(
    filename: str,
    image_type: str,
    tool_name: str | None = None,
) -> list[dict[str, str]]:
    field = IMAGE_TYPE_FIELDS.get(image_type)
    if field is None:
        return []

    row = _find_measurement(filename, tool_name)
    if row is None:
        return []

    tool = normalize_tool(tool_name)
    encoded_filename = quote(row["filename"], safe="")
    encoded_tool = quote(tool, safe="")

    images: list[dict[str, str]] = []
    for name in row.get(field, []):
        if not name or name == "no files":
            continue
        encoded_name = quote(name, safe="")
        images.append({
            "name": name,
            "url": (
                f"/api/afm/files/{encoded_filename}/images/{image_type}/{encoded_name}"
                f"?tool={encoded_tool}"
            ),
        })
    return images


def get_analysis_image_svg(
    filename: str,
    image_type: str,
    name: str,
    tool_name: str | None = None,
) -> str | None:
    field = IMAGE_TYPE_FIELDS.get(image_type)
    if field is None:
        return None

    row = _find_measurement(filename, tool_name)
    if row is None:
        return None

    names = [n for n in row.get(field, []) if n and n != "no files"]
    if name not in names:
        return None

    rng = random.Random(
        _seed_for("analysis-image", row["tool_name"], row["filename"], f"{image_type}:{name}")
    )
    accent = _IMAGE_TYPE_ACCENT.get(image_type, "#0f766e")
    shapes = "\n".join(
        "<circle "
        f"cx=\"{rng.randint(30, 610)}\" cy=\"{rng.randint(45, 285)}\" "
        f"r=\"{rng.randint(10, 46)}\" "
        f"fill=\"rgba(255,255,255,{rng.uniform(0.04, 0.16):.2f})\" />"
        for _ in range(18)
    )
    title = html.escape(f"{image_type.upper()} · {row['tool_name']} {row['lot_id']}")
    subtitle = html.escape(name)

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="640" height="360" viewBox="0 0 640 360">
  <rect width="640" height="360" fill="#0f172a" />
  <rect x="20" y="20" width="600" height="280" rx="10" fill="{accent}" fill-opacity="0.85" />
  {shapes}
  <text x="32" y="330" fill="#f8fafc" font-family="Arial, sans-serif" font-size="18" font-weight="700">{title}</text>
  <text x="32" y="351" fill="#cbd5e1" font-family="Arial, sans-serif" font-size="12">{subtitle}</text>
</svg>"""
```

- [ ] **Step 6: Export from `mock.py`'s `__all__`**

Add `"list_analysis_images"` and `"get_analysis_image_svg"` to the `__all__` list in `mock.py`.

- [ ] **Step 7: Add the seam functions in `data.py`**

In `back_dev_home/afm/data.py`, add both names to `__all__`, and add the delegating functions (after `get_profile_image_svg`, before `list_user_activities`):

```python
def list_analysis_images(
    filename: str,
    image_type: str,
    tool_name: str | None = None,
) -> list[dict[str, str]]:
    return _provider().list_analysis_images(filename, image_type, tool_name)


def get_analysis_image_svg(
    filename: str,
    image_type: str,
    name: str,
    tool_name: str | None = None,
) -> str | None:
    return _provider().get_analysis_image_svg(filename, image_type, name, tool_name)
```

- [ ] **Step 8: Add office stubs**

In `back_dev_home/afm/providers/office.py`, add (after `get_profile_image_svg`):

```python
def list_analysis_images(*args, **kwargs):
    return _not_connected()


def get_analysis_image_svg(*args, **kwargs):
    return _not_connected()
```

- [ ] **Step 9: Run tests to verify they pass**

Run: `.venv/bin/pytest back_dev_home/afm/tests/test_analysis_images.py -q`
Expected: PASS (7 tests). Also run `.venv/bin/pytest back_dev_home/afm -q` to confirm the existing contract tests still pass.

- [ ] **Step 10: Commit**

```bash
git add back_dev_home/afm/providers/mock.py back_dev_home/afm/data.py back_dev_home/afm/providers/office.py back_dev_home/afm/tests/test_analysis_images.py
git commit  # message below (append the standard trailer)
```

Message: `feat(afm): analysis-image data layer + mock capture population`

---

### Task 2: Backend routes — list + serve analysis images

**Files:**
- Modify: `back_dev_home/afm/routes.py`
- Test: `back_dev_home/afm/tests/test_analysis_routes.py` (create)

**Interfaces:**
- Consumes: `data.list_analysis_images`, `data.get_analysis_image_svg` (Task 1).
- Produces: two routes:
  - `GET /afm/files/<path:filename>/images/<image_type>?tool=` → `{success, data:[{name,url}], count, tool, message}` (200; unknown type → 404).
  - `GET /afm/files/<path:filename>/images/<image_type>/<path:name>?tool=` → `image/svg+xml` bytes (unknown type or missing image → 404).

- [ ] **Step 1: Write the failing test**

Create `back_dev_home/afm/tests/test_analysis_routes.py`:

```python
"""Route tests for the analysis-image gallery (Flask test_client)."""

from urllib.parse import quote

import pytest
from flask import Flask

from back_dev_home.afm import data
from back_dev_home.afm.providers import mock
from back_dev_home.afm.routes import bp


@pytest.fixture
def client():
    app = Flask(__name__)
    app.register_blueprint(bp, url_prefix="/api")
    return app.test_client()


def _capture_row():
    field = mock.IMAGE_TYPE_FIELDS["capture"]
    for row in data.list_afm_files(None):
        names = [n for n in row.get(field, []) if n != "no files"]
        if names:
            return row, names
    raise AssertionError("no capture row")


def test_list_route_returns_images(client):
    row, names = _capture_row()
    fn = quote(row["filename"], safe="")
    r = client.get(f"/api/afm/files/{fn}/images/capture?tool={row['tool_name']}")
    assert r.status_code == 200
    body = r.get_json()
    assert body["success"] is True
    assert body["count"] == len(names)
    assert [img["name"] for img in body["data"]] == names
    assert body["tool"] == row["tool_name"]


def test_list_route_unknown_type_404(client):
    row, _ = _capture_row()
    fn = quote(row["filename"], safe="")
    r = client.get(f"/api/afm/files/{fn}/images/bogus?tool={row['tool_name']}")
    assert r.status_code == 404


def test_serve_route_returns_svg(client):
    row, names = _capture_row()
    fn = quote(row["filename"], safe="")
    nm = quote(names[0], safe="")
    r = client.get(f"/api/afm/files/{fn}/images/capture/{nm}?tool={row['tool_name']}")
    assert r.status_code == 200
    assert r.mimetype == "image/svg+xml"
    assert r.get_data(as_text=True).startswith("<svg")


def test_serve_route_missing_name_404(client):
    row, _ = _capture_row()
    fn = quote(row["filename"], safe="")
    r = client.get(f"/api/afm/files/{fn}/images/capture/not-real.png?tool={row['tool_name']}")
    assert r.status_code == 404


def test_serve_route_unknown_type_404(client):
    row, names = _capture_row()
    fn = quote(row["filename"], safe="")
    nm = quote(names[0], safe="")
    r = client.get(f"/api/afm/files/{fn}/images/bogus/{nm}?tool={row['tool_name']}")
    assert r.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest back_dev_home/afm/tests/test_analysis_routes.py -q`
Expected: FAIL — the routes 404 for the *list* case too (routes not defined yet) so `test_list_route_returns_images` fails on `status_code == 200`.

- [ ] **Step 3: Add the imports and route constant**

In `back_dev_home/afm/routes.py`, extend the `from back_dev_home.afm.data import (...)` block with the two new names:

```python
from back_dev_home.afm.data import (
    get_afm_file_detail,
    get_analysis_image_svg,
    get_profile_image_svg,
    get_profile_points,
    get_tools,
    get_user_analytics,
    list_afm_files,
    list_analysis_images,
    list_user_activities,
    normalize_tool
)
```

Add a module constant after `bp = Blueprint(...)`:

```python
_VALID_IMAGE_TYPES = ("align", "tip", "capture", "tiff")
```

- [ ] **Step 4: Add the two routes**

In `routes.py`, add after the existing `afm_image_file` route (~line 136), before `afm_activities`:

```python
@bp.get("/afm/files/<path:filename>/images/<image_type>")
def afm_analysis_images(filename: str, image_type: str):
    tool_name = _tool_name()
    if image_type not in _VALID_IMAGE_TYPES:
        return jsonify({
            "success": False,
            "error": "Invalid image type",
            "message": f"Unknown image type '{image_type}'",
            "tool": tool_name
        }), 404

    decoded_filename = unquote(filename)
    images = list_analysis_images(decoded_filename, image_type, tool_name)
    return jsonify({
        "success": True,
        "data": images,
        "count": len(images),
        "tool": tool_name,
        "message": f"Found {len(images)} {image_type} images for {decoded_filename}"
    })


@bp.get("/afm/files/<path:filename>/images/<image_type>/<path:name>")
def afm_analysis_image_file(filename: str, image_type: str, name: str):
    if image_type not in _VALID_IMAGE_TYPES:
        return "Invalid image type", 404

    tool_name = _tool_name()
    decoded_filename = unquote(filename)
    decoded_name = unquote(name)
    svg = get_analysis_image_svg(decoded_filename, image_type, decoded_name, tool_name)

    if svg is None:
        return "Image file not found", 404

    return Response(svg, mimetype="image/svg+xml")
```

Note: the static `images` segment plus the non-`path` `<image_type>` converter (one segment, no slash) means the 2-segment list route and 3-segment serve route are unambiguous, and neither collides with the existing `image`/`image-file` routes. AFM filenames contain no `/`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/pytest back_dev_home/afm/tests/test_analysis_routes.py -q`
Expected: PASS (5 tests). Then `.venv/bin/pytest back_dev_home/afm -q` — all afm tests green.

- [ ] **Step 6: Commit**

```bash
git add back_dev_home/afm/routes.py back_dev_home/afm/tests/test_analysis_routes.py
git commit  # message below (append the standard trailer)
```

Message: `feat(afm): routes to list and serve analysis images`

---

### Task 3: Frontend gallery — composable method, component, page wiring

**Files:**
- Modify: `front-dev-home/app/composables/useAfmDetailApi.ts`
- Create: `front-dev-home/app/components/afm/detail/AnalysisImages.vue`
- Modify: `front-dev-home/app/pages/afm/[tool]/[filename].vue`

**Interfaces:**
- Consumes: Task 2 routes; `useAfmDetailApi` internals (`joinApiPath`, `base`, in-flight `Map` pattern).
- Produces (composable): `type AfmImageType`, `interface AfmAnalysisImage`, `interface AfmAnalysisImagesResponse`, and `fetchAnalysisImages(toolName, filename, imageType)`.

> No unit test — `.vue` + `$fetch` wiring. Gate: `npm run typecheck` + `npm run lint`, plus in-app verification in Task 4.

- [ ] **Step 1: Add types + `fetchAnalysisImages` to the composable**

In `front-dev-home/app/composables/useAfmDetailApi.ts`, add these type exports near the other interfaces (e.g. after `AfmImageResponse`, ~line 97):

```ts
export type AfmImageType = 'align' | 'tip' | 'capture' | 'tiff'

export interface AfmAnalysisImage {
  name: string
  url: string
}

export interface AfmAnalysisImagesResponse {
  success: boolean
  data: AfmAnalysisImage[]
  count: number
  tool: string
}
```

Add a module-level in-flight map next to the others (~line 118):

```ts
const inFlightAnalysis = new Map<string, Promise<AfmAnalysisImagesResponse>>()
```

Inside `useAfmDetailApi()`, add the method after `fetchImage` (~line 216):

```ts
  const fetchAnalysisImages = async (
    toolName: string,
    filename: string,
    imageType: AfmImageType
  ): Promise<AfmAnalysisImagesResponse> => {
    const cacheKey = `${toolName}::${filename}::${imageType}`
    const existing = inFlightAnalysis.get(cacheKey)
    if (existing) return await existing

    const path = `/afm/files/${encodeURIComponent(filename)}/images/${imageType}`
    const request = $fetch<AfmAnalysisImagesResponse>(
      joinApiPath(base, path),
      { query: { tool: toolName } }
    ).finally(() => inFlightAnalysis.delete(cacheKey))

    inFlightAnalysis.set(cacheKey, request)
    return await request
  }
```

Add `fetchAnalysisImages` to the object returned by `useAfmDetailApi` (the `return { ... }` at ~line 224):

```ts
  return {
    fetchFiles,
    useAfmFiles,
    fetchDetail,
    fetchProfile,
    fetchImage,
    fetchAnalysisImages,
    useAfmDetail
  }
```

- [ ] **Step 2: Create the gallery component**

Create `front-dev-home/app/components/afm/detail/AnalysisImages.vue`:

```vue
<template>
  <UCard
    class="dashboard-surface rounded-2xl"
    :ui="{ body: 'p-4 sm:p-5', header: 'px-4 sm:px-5 py-3' }"
  >
    <template #header>
      <div class="flex items-center gap-2">
        <UIcon
          name="i-lucide-images"
          class="h-4 w-4 text-(--sk-ink-muted)"
        />
        <h2 class="sk-title">
          Analysis images
        </h2>
      </div>
    </template>

    <UTabs
      v-model="activeType"
      :items="tabItems"
      class="w-full"
    >
      <template #content="{ item }">
        <div
          v-if="stateFor(item.value).pending"
          class="flex h-56 items-center justify-center sk-body"
        >
          <UIcon
            name="i-lucide-loader-circle"
            class="mr-2 h-4 w-4 animate-spin"
          />
          Loading images…
        </div>
        <div
          v-else-if="stateFor(item.value).images.length === 0"
          class="flex h-56 flex-col items-center justify-center text-center sk-body"
        >
          <UIcon
            name="i-lucide-image-off"
            class="mb-2 h-8 w-8 text-(--sk-ink-muted)"
          />
          No {{ item.label }} images available
        </div>
        <div
          v-else
          class="flex gap-4 overflow-x-auto pb-2"
        >
          <button
            v-for="image in stateFor(item.value).images"
            :key="image.name"
            type="button"
            class="group shrink-0 overflow-hidden rounded-xl border border-zinc-200 bg-zinc-50 text-left transition hover:shadow-md dark:border-zinc-800 dark:bg-zinc-900"
            @click="openLightbox(image)"
          >
            <img
              :src="image.url"
              :alt="image.name"
              class="h-40 w-56 object-cover"
              loading="lazy"
            >
            <p class="w-56 truncate px-2 py-1.5 text-xs sk-body">
              {{ image.name }}
            </p>
          </button>
        </div>
      </template>
    </UTabs>

    <UModal
      v-model:open="lightboxOpen"
      :ui="{ content: 'w-[92vw] sm:max-w-[900px]', body: 'p-0' }"
    >
      <template #content>
        <div
          v-if="selectedImage"
          class="p-4"
        >
          <div class="mb-3 flex items-center justify-between gap-3">
            <p class="truncate sk-title">
              {{ selectedImage.name }}
            </p>
            <div class="flex items-center gap-2">
              <UButton
                size="xs"
                color="neutral"
                variant="ghost"
                icon="i-lucide-download"
                aria-label="Download image"
                @click="downloadImage(selectedImage)"
              />
              <UButton
                size="xs"
                color="neutral"
                variant="ghost"
                icon="i-lucide-x"
                aria-label="Close"
                @click="lightboxOpen = false"
              />
            </div>
          </div>
          <div class="flex max-h-[78vh] items-center justify-center overflow-hidden rounded-xl bg-zinc-50 dark:bg-zinc-900">
            <img
              :src="selectedImage.url"
              :alt="selectedImage.name"
              class="max-h-[78vh] max-w-full object-contain"
            >
          </div>
        </div>
      </template>
    </UModal>
  </UCard>
</template>

<script setup lang="ts">
import type { TabsItem } from '@nuxt/ui'
import type { AfmAnalysisImage, AfmImageType } from '~/composables/useAfmDetailApi'

const props = defineProps<{
  tool: string
  filename: string
}>()

const { fetchAnalysisImages } = useAfmDetailApi()

interface TabState {
  images: AfmAnalysisImage[]
  pending: boolean
  loaded: boolean
}

const TYPES: { value: AfmImageType, label: string, icon: string }[] = [
  { value: 'align', label: 'Align', icon: 'i-lucide-crosshair' },
  { value: 'tip', label: 'Tip', icon: 'i-lucide-pen-tool' },
  { value: 'capture', label: 'Capture', icon: 'i-lucide-camera' },
  { value: 'tiff', label: 'Result', icon: 'i-lucide-scan' }
]

const states = reactive<Record<AfmImageType, TabState>>({
  align: { images: [], pending: false, loaded: false },
  tip: { images: [], pending: false, loaded: false },
  capture: { images: [], pending: false, loaded: false },
  tiff: { images: [], pending: false, loaded: false }
})

const activeType = ref<AfmImageType>('align')

const stateFor = (type: AfmImageType) => states[type]

const tabItems = computed<TabsItem[]>(() =>
  TYPES.map(t => ({
    label: t.label,
    icon: t.icon,
    value: t.value,
    badge: states[t.value].loaded && states[t.value].images.length > 0
      ? states[t.value].images.length
      : undefined
  }))
)

const loadType = async (type: AfmImageType) => {
  const state = states[type]
  if (state.loaded || state.pending || !props.filename) return
  state.pending = true
  try {
    const res = await fetchAnalysisImages(props.tool, props.filename, type)
    state.images = res.data ?? []
  } catch {
    state.images = []
  } finally {
    state.loaded = true
    state.pending = false
  }
}

watch(activeType, type => loadType(type), { immediate: true })

const lightboxOpen = ref(false)
const selectedImage = ref<AfmAnalysisImage | null>(null)

const openLightbox = (image: AfmAnalysisImage) => {
  selectedImage.value = image
  lightboxOpen.value = true
}

const downloadImage = async (image: AfmAnalysisImage) => {
  if (!import.meta.client) return
  try {
    const res = await fetch(image.url)
    const blob = await res.blob()
    const objectUrl = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = objectUrl
    const safeName = image.name.replace(/[^a-zA-Z0-9._-]+/g, '_')
    link.download = `${props.filename}-${activeType.value}-${safeName}`
    link.click()
    URL.revokeObjectURL(objectUrl)
  } catch {
    // best-effort download
  }
}
</script>
```

- [ ] **Step 3: Render the gallery on the detail page**

In `front-dev-home/app/pages/afm/[tool]/[filename].vue`, add the gallery in the right column, immediately after the `<AfmDetailProfileImage ... />` block:

```vue
          <AfmDetailProfileImage
            :url="imageUrl"
            :point="selectedPoint"
            :filename="filename"
            :loading="imagePending"
          />
          <AfmDetailAnalysisImages
            :tool="toolName"
            :filename="filename"
          />
```

(`toolName` is the existing `computed` uppercase tool id used for every other API call; `filename` is the existing route-derived ref.)

- [ ] **Step 4: Typecheck**

Run: `cd front-dev-home && npm run typecheck`
Expected: no new errors attributable to these files (pre-existing `RadiusChart.vue` errors are unrelated user WIP).

- [ ] **Step 5: Lint**

Run: `cd front-dev-home && npm run lint`
Expected: no errors in the three files. Fix any (e.g. `@stylistic` quote/spacing) before committing.

- [ ] **Step 6: Commit**

```bash
git add front-dev-home/app/composables/useAfmDetailApi.ts front-dev-home/app/components/afm/detail/AnalysisImages.vue "front-dev-home/app/pages/afm/[tool]/[filename].vue"
git commit  # message below (append the standard trailer)
```

Message: `feat(afm): add analysis-image gallery to measurement detail page`

---

### Task 4: Full verification

**Files:** none (verification only).

- [ ] **Step 1: Backend suite**

Run: `.venv/bin/pytest back_dev_home/afm -q`
Expected: all afm tests pass (existing contract + new data + new routes).

- [ ] **Step 2: Frontend suite + gates**

Run: `cd front-dev-home && npm run test && npm run typecheck && npm run lint`
Expected: tests pass; typecheck shows only the pre-existing unrelated `RadiusChart.vue` errors; lint clean for the new/changed files.

- [ ] **Step 3: In-app verification (verify skill)**

Ensure Flask (`:5050`) and Nuxt (`:3000`) are running (verify skill). Load an AFM detail page, e.g. tool `map608`, and confirm:
  - The "Analysis images" card shows four tabs (Align / Tip / Capture / Result).
  - **Capture** and **Result** tabs show thumbnails (mock populates them for every measurement); Align/Tip may be empty for many measurements (only some are populated) — the empty state renders cleanly.
  - Clicking a thumbnail opens the lightbox; the download button saves `{filename}-{type}-{name}`.
  - Tab badges show counts once a tab is visited.

  Data-level fallback if the browser is unavailable:
  `curl -b "LASTUSER=local-dev" "http://localhost:3000/api/afm/files/<url-encoded-filename>/images/capture?tool=MAP608"`
  returns `{success:true, data:[...], count:>0}`, and appending `/<name>` returns SVG bytes.

- [ ] **Step 4: Markdown lint (only if docs changed)**

Run: `npm run lint:md` from repo root. (No docs expected to change in Tasks 1-3.)

---

## Self-Review

**Spec coverage:**

- Four image kinds (align/tip/capture/tiff) as tabs → Task 3 `TYPES`; routes validate the four → Task 2. ✓
- Mock capture population → Task 1 Step 3 + regression test. ✓
- `list_analysis_images` / `get_analysis_image_svg` in mock, seam (`data.py`), office stubs → Task 1. ✓
- Deterministic seeded placeholder SVG, per-type accent → Task 1 Step 5 + determinism test. ✓
- Two routes (list 200 / unknown 404; serve svg / 404) → Task 2 + tests. ✓
- `fetchAnalysisImages` mirroring `fetchImage` → Task 3 Step 1. ✓
- `AnalysisImages.vue`: tabs, lazy per-tab load, count badges, empty/loading states, thumbnail strip, `UModal` lightbox, per-image download → Task 3 Step 2. ✓
- Page render below profile image → Task 3 Step 3. ✓
- Backend pytest + frontend gates + in-app verify → Tasks 1, 2, 4. ✓

**Placeholder scan:** No TBD/TODO; every code step is complete. ✓

**Type consistency:** `AfmImageType`/`AfmAnalysisImage`/`AfmAnalysisImagesResponse` defined in Task 3 Step 1 and consumed by the same names in the component (Step 2); `IMAGE_TYPE_FIELDS` defined in Task 1 (mock) and referenced in both test files; route paths (`/images/<type>` and `/images/<type>/<name>`) match between the mock-built URL (Task 1), the routes (Task 2), and the composable path (Task 3). `list_analysis_images`/`get_analysis_image_svg` signatures identical across mock, data seam, and office stub. ✓
