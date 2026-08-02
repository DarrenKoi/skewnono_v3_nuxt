# DESIGN.md — SKEWNONO Design System

> This document is the **single source of truth** for the SKEWNONO frontend's visual language. Code follows this document; where they disagree, the code is corrected. Token identifiers stay in English to match Tailwind/NuxtUI class names. Implemented in `front-dev-home/app/assets/css/main.css` (tokens), `front-dev-home/app/app.config.ts` (NuxtUI mapping), and verified against `preview.html` / `preview-dark.html`.

## Overview

SKEWNONO is a calm, warm, data-first metrology tool. The base atmosphere is a **warm paper canvas** (`--sk-canvas` — `oklch(0.96 0.012 80)`) — a cream tint at hue ≈ 80°, deliberately not the cool gray that every dashboard defaults to. Cards sit one shade lighter in the same hue (`--sk-surface`), so the UI reads as one warm material instead of white islands floating on gray. Dark mode inverts into a **Walnut** palette (page L≈0.21, hue 70°; cards lift to L≈0.245) so the tinted-card pattern survives inversion.

Brand voltage comes from **two selection families with strict meanings**: near-black ink (`--sk-ink` — `#15110D`) fills anything that *navigates* (tabs, toggles, sub-tabs, CTAs), and terracotta (`--sk-brand` — `#C75A3C`) fills anything that *filters* (Fab, Category, Lot, Status chips). A third color, warm crimson (`--sk-accent`), is trim only — a 2px underline, a 2px left edge, a 5% radial page wash — never a fill.

The system has three surface roles that carry every page:
1. **Paper canvas** (`--sk-canvas`) — the body floor
2. **Paper cards** (`--sk-surface` + `.dashboard-surface`) — tables, stats, panels
3. **Inset panels** (`--sk-muted-surface`) — secondary surfaces inside cards

**Key Characteristics:**
- Warm paper canvas with a three-step warm ink text hierarchy (`--sk-ink` / `--sk-ink-muted` / `--sk-ink-subtle`). The defining rule: **data values always get full ink; muted ink is for labels only.**
- BLACK = navigate, TERRACOTTA = filter. Never mixed on the same active state; the litmus test is "does pressing this change the view, or narrow the data?"
- Crimson (`--sk-accent`) as trim only: `.sk-nav-accent` underline, `.sk-fab-active` left edge, `.dashboard-bg-layer` radial wash. Never a filled button, never body text.
- **Soft rectangles only.** A four-step radius scale (6 / 8 / 10 / 14px). `rounded-full` is banned on new components (legacy exception: status pills).
- Tables built to read: `font-mono tabular-nums` numerals, 1px borders, hover highlight only.
- Shadows near zero — one loose "paper" shadow on cards, nothing else.
- Offline-capable: self-hosted woff2 fonts, bundled Lucide icons, no CDN.
- Bilingual: Korean UI labels, English tokens/keys/identifiers.
- Content deliberately capped at 1280px on FHD screens — calm reading width over full-bleed density.

## Colors

All colors are defined as light/dark pairs on `:root` and `.dark` and must be consumed through the `--sk-*` variables (`bg-(--sk-surface)`, `text-(--sk-ink)`), never as inline hex. Values below read **light / dark**.

### Brand & Accent
- **Ink / Navigate fill** (`--sk-ink` — `#15110D` / `#F4EFE6`): Near-black fill for every active NAVIGATE state (nav pills, section toggles, primary buttons) and for primary text. Inverts to cream in dark mode so nav stays "the darkest thing on the page" conceptually.
- **On Ink** (`--sk-ink-fg` — `#F8F4EC` / `#15110D`): Text on ink fills.
- **Terracotta / Filter fill** (`--sk-brand` — `#C75A3C` / `#E0553F`): Fill for every active FILTER chip. Warms up slightly in dark mode for legibility.
- **On Terracotta** (`--sk-brand-fg` — `#FFF7F1` / `#FFF7F1`): Text on terracotta fills.
- **Terracotta Soft** (`--sk-brand-soft` — `#F3DCD2` / `oklch(0.30 0.05 38)`): Background tint for filter rows.
- **Terracotta Ink** (`--sk-brand-ink` — `#8A3D27` / `#F3DCD2`): Readable text on the soft tint.
- **Crimson Accent** (`--sk-accent` — `oklch(0.58 0.13 35)` / `oklch(0.74 0.14 38)`): The favicon-slash identity, retoned to sit on cream. **Trim only** — sanctioned uses are exactly three: `.sk-nav-accent`, `.sk-fab-active`, `.dashboard-bg-layer`.
- **Accent Soft** (`--sk-accent-soft` — `oklch(0.95 0.025 60)` / `oklch(0.34 0.05 38)`): Hover tint on interactive stat cells.
- **Accent Border / Tint** (`--sk-accent-border`, `--sk-accent-tint`): Accent at 22–32% / 6–10% alpha. Reserved for future emphasized-card use.

### Surface
- **Canvas** (`--sk-canvas` — `oklch(0.96 0.012 80)` / `oklch(0.21 0.008 70)`): The page floor. Warm paper; walnut at night.
- **Surface** (`--sk-surface` — `oklch(0.99 0.006 80)` / `oklch(0.245 0.008 70)`): Cards, headers. One shade lighter than canvas, same hue.
- **Muted Surface** (`--sk-muted-surface` — `oklch(0.97 0.01 80)` / `oklch(0.225 0.008 70)`): Inset panels, secondary surfaces.
- **Border** (`--sk-border` — `oklch(0.91 0.014 80)` / `oklch(0.295 0.008 70)`): Default 1px border.
- **Border Soft** (`--sk-border-soft` — `oklch(0.94 0.01 80)` / `oklch(0.265 0.008 70)`): Hairline dividers between nav rows and stat cells.
- **Nav Bg / Border** (`--sk-nav-bg`, `--sk-nav-border`): Translucent sticky-header pair (canvas tone at ~80% alpha + `backdrop-blur-md`).

### Text
- **Ink** (`--sk-ink` — `#15110D` / `#F4EFE6`): Headings, body, and **all data values in tables** (ID, model, vendor, IP, version, measurements).
- **Ink Muted** (`--sk-ink-muted` — `oklch(0.47 0.014 60)` / `oklch(0.74 0.008 70)`): Labels, captions, header buttons, meta info — *never data values*. In dark mode muted ink is intentionally dim; on a value column it washes out next to full-ink columns.
- **Ink Subtle** (`--sk-ink-subtle` — `oklch(0.66 0.012 70)` / `oklch(0.56 0.008 70)`): Disabled / de-emphasized text.
- Litmus test — *"Is this a **value** the user came to read, or a **label** describing it? Value → ink; label → ink-muted."*

### Semantic
- **OK** (`--sk-ok` / `-soft` / `-border` — `oklch(0.62 0.13 145)` / `oklch(0.78 0.14 150)`): Connected, healthy. Soft fills sit on muted-surface; borders at 32% alpha so badges read as labels, not buttons.
- **Bad** (`--sk-bad` family — `oklch(0.58 0.18 28)` / `oklch(0.72 0.17 28)`): Down, error.
- **Warn** (`--sk-warn` family — `oklch(0.70 0.15 75)` / `oklch(0.80 0.15 78)`): Degraded.
- **On pill** (`--sk-on-bg`/`--sk-on-fg` — `#d9f5e8`/`#0f5132` / `#052e16`/`#bbf7d0`): Equipment running state, via `.sk-pill-on`.
- **Off pill** (`--sk-off-bg`/`--sk-off-fg` — warm gray pair): Idle/maintenance, via `.sk-pill-off`.
- **Error text** (`text-rose-600 dark:text-rose-400`): Message lines only.

### Dark Field (SEM imagery only)

Real CD-SEM images are dark-field, so a simulated micrograph cannot invert with the theme — a "light mode" SEM image would be a different photograph, not the same one relit. These three are therefore declared in `:root` **and deliberately omitted from `.dark`**, the one place in the system where that asymmetry is correct rather than a bug.

- **Field** (`--sk-field` — `oklch(0.21 0.008 70)`): The dark canvas of any simulated SEM view. Deliberately the *walnut* dark-mode canvas value rather than a raw slate/near-black, so the imagery still reads as part of this system when it sits on cream.
- **Field Ink** (`--sk-field-ink` — `oklch(0.94 0.008 80)`): The bright sidewall rim — cream, not cool white.
- **Field Core** (`--sk-field-core` — `oklch(0.40 0.014 60)`): The duller line top/interior between rims.

Scope is exactly the simulated imagery (`magpixel/PatternSchematic.vue`, `magpixel/SemSimulation.vue`). Chrome around the image — captions, legends, margin labels — stays on the normal inverting tokens. Margin hatching over the field uses **terracotta** (`--sk-brand`), because the margin is the value the 여유 마진 filter produces; crimson stays trim-only and is not used here. `SemSimulation.vue` additionally hard-codes the sRGB resolution of these three (`27,24,20` / `78,70,64` / `238,235,229`) because it interpolates between them in JS; if a value here changes, that triple changes with it.
- **Focus ring** (`--sk-focus-ring` — accent at 45% alpha): `outline: 2px solid; outline-offset: 2px` on `:focus-visible`, one ring color for both selection families.

### NuxtUI Token Bridge

NuxtUI themes its components off its own fixed token set (`--ui-bg`, `--ui-text*`, `--ui-border*`, `--ui-primary`), which by default resolves to a neutral color ramp. Two pieces connect it to this design system, and together they are why **a bare `<UCard>`, `<UButton>`, `<UInput>`, `<USelect>` or `<UTable>` comes out on-system with no classes at the call site**:

1. **`paper` ramp** (`--color-paper-50…950`, `main.css` `@theme`) — zinc's lightness steps re-hued to the warm 70–80° family. `app.config.ts` maps NuxtUI's `primary` and `neutral` onto it. Zinc is hue ≈ 285 (cool); every NuxtUI default used to draw from it, which is why untouched components read gray-blue against a cream page.
2. **Semantic bridge** (`main.css`) — `--ui-*` → `--sk-*`: `--ui-bg` → `--sk-surface`, `--ui-text` → `--sk-ink`, `--ui-text-muted` → `--sk-ink-muted`, `--ui-border` → `--sk-border`, `--ui-bg-inverted` / `--ui-primary` → `--sk-ink`.

Two rules protect this layer. It is declared **outside `@layer`**, so it outranks NuxtUI's own `@layer theme` defaults. And it is declared **in `:root` only, never in `.dark`** — the `--sk-*` tokens already invert under `.dark`, so dark mode follows for free; adding a `.dark` bridge block would let the two modes drift apart and is a bug, not a safety net.

**Consequence for existing code:** a call-site class like `border-zinc-200/70` or `text-zinc-900` is no longer a color that needs *replacing* — the correct value is already underneath it. Delete the class.

## Typography

### Font Family
The system runs **Spoqa Han Sans Neo** as the default UI/body sans, covering **both Hangul and Latin** from a single self-hosted face per weight, with **Public Sans** kept as a Latin fallback, and **JetBrains Mono** for numbers, IDs, code, and eyebrows. Fallback stacks: `Spoqa Han Sans Neo, Public Sans, Apple SD Gothic Neo, Malgun Gothic, Segoe UI, sans-serif` (`--font-sans`), `JetBrains Mono, ui-monospace, Cascadia Code, Segoe UI Mono, SFMono-Regular, Menlo, Consolas, monospace` (`--font-mono`), and `--font-korean` when Korean must be forced.

Unlike the previous Noto Sans KR setup (which split into korean + latin subsets with `unicode-range` ordering), each Spoqa Han Sans Neo weight is **one woff2 file that already covers Latin + Hangul**, so there are only three `@font-face` blocks. Spoqa Han Sans Neo ships **no SemiBold (600)** — only 400/500/700 are bundled. The Medium (500) face declares `font-weight: 500 600`, so `font-semibold` / `font-weight: 600` render as **Medium** rather than auto-mapping up to Bold; flip the range if 600 should render as Bold.

All fonts are **self-hosted**: woff2 only, in `front-dev-home/public/fonts/`. Public Sans and JetBrains Mono come from `@fontsource/*`; Spoqa Han Sans Neo comes from the `spoqa-han-sans` npm package (v3.3.0, `Subset/SpoqaHanSansNeo/*.woff2`, SIL OFL 1.1). No CDN or Google Fonts access, ever (offline principle).

- Spoqa Han Sans Neo 400/500/700 → default sans: body, navigation, buttons, headings, Korean labels and copy (Latin + Hangul); weight 600 → Medium
- Public Sans 400–700 → Latin fallback
- JetBrains Mono 400–700 → all numeric and ID columns, code, eyebrows

### Hierarchy

| Token | Size | Weight | Line Height | Letter Spacing | Use |
|---|---|---|---|---|---|
| `text-3xl` | 30px | 700 | 36px | tracking-tight | Page titles (`<h1>`) |
| `text-2xl` | 24px | 600 | 32px | 0 | Page subtitles, KPI numbers (`tabular-nums`) |
| `text-xl` | 20px | 600 | 28px | 0 | Section titles |
| `text-lg` | 18px | 600 | 28px | 0 | Card titles |
| `text-base` | 16px | 400 | 24px | 0 | Body default |
| `text-sm` | 14px | 400 | 20px | 0 | Table cells, inputs, secondary body |
| `text-xs` | 12px | 500–600 | 16px | 0 | Metadata, pills, secondary labels — **the floor for anything the user reads as content** |
| micro-label | 11px | 500–600 | 16px | 0 to +0.02em | **Labels only** — table header cells, stat-strip captions. Never a data value |
| eyebrow | 10px | 500–600 mono | 1.4 | +0.06em, uppercase | Meta-bar kickers (`CD-SEM · R3`) — mono caps only |

### Principles
Weight carries hierarchy, not color: 400 body → 500 nav labels/buttons → 600 section titles/pills → 700 page titles and big numbers. Number and ID columns always take `font-mono tabular-nums`; tabular figures are mandatory wherever numbers update in place. Korean labels keep natural spacing with `whitespace-nowrap` on header cells; Korean paragraphs (help text, empty states) take `leading-relaxed` — dense Hangul needs the extra line height at 14–16px. Page titles are Korean; the eyebrow above them is English (`CD-SEM`, `HV-SEM`).

**The sub-12px rule.** Metrology screens are dense, and two tiers below the floor earn their place: the 10px mono **eyebrow** and the 11px **micro-label**. Both are strictly *chrome that names things* — a column header, a stat caption, a kicker. The line that does not move: **a data value never renders below 12px.** If a value doesn't fit, the column is too narrow; if a label doesn't fit at 11px, shorten the label. Nothing else goes under 12px, and no new tier gets invented — 10 and 11 are the whole list.

### Semantic type classes

The hierarchy above is implemented as a small set of **role-named classes** in `main.css`, so type is styled by *purpose and location*, not by ad-hoc `text-[…]` / `text-(--sk-…)` utilities scattered per call site. Each class bundles size + weight + colour + family; a change to a role lands in **one place**, and the class name documents intent. This is the mechanism that keeps the type consistent — hand-written `text-[9.5px]`, `text-[10.5px]`, `text-[11.5px]` and `text-zinc-400/500` on content are the drift these replace.

| Class | Role — purpose / location | Size · weight · colour |
|---|---|---|
| `.sk-eyebrow` | Mono uppercase kicker (meta-bar, section kicker) | 10px · 600 · mono +0.06em uppercase · ink-muted |
| `.sk-label` | Field / column / caption **label** (table headers, stat captions) | 11px · 600 · ink-muted |
| `.sk-value` | A data **value** (table cell, stat text, ID) | 12px · 500 · **ink** |
| `.sk-value-num` | A **numeric** value (mono + tabular figures) | 12px · 500 · mono tabular · **ink** |
| `.sk-meta` | Secondary / supporting text (helper, timestamp, de-emphasised) | 12px · 400 · ink-muted |
| `.sk-body` | Body copy (descriptions, empty states, help) | 14px · 400 · ink |
| `.sk-title` | Compact panel / card title (dense dashboards) | 13px · 600 · ink |
| `.sk-heading` | Card / section heading | 18px · 600 · ink |
| `.sk-page-title` | Page title (`<h1>`) | 30px · 700 · tracking-tight · ink |

Rules that fall out of the table, enforced by which class you pick: **values are ink, labels are muted** (choosing `.sk-value` vs `.sk-label` *is* the litmus test); **a value is never `.sk-eyebrow`/`.sk-label`** (those are sub-12px, chrome-only); dark-mode colour follows for free because the classes reference `--sk-*` tokens. Spacing, alignment and layout stay as Tailwind utilities at the call site — these classes own type only. NuxtUI components keep inheriting type through the token bridge; use these on hand-written markup.

## Layout

### Spacing System
- **Base unit:** 4px (Tailwind default scale).
- **Recurring tokens:** `gap-1`/`p-1` 4px (pill groups) · `gap-2`/`p-2` 8px (input interiors, button groups) · `gap-3`/`p-3` 12px (card headers, filter-bar controls) · `p-4` 16px (card padding) · `gap-6`/`space-y-6` 24px (between cards) · `py-2.5` 10px (button vertical padding).

### Grid & Container
- **Max content width:** `max-w-7xl mx-auto` (1280px), centered. **The target screen is FHD (1920×1080) but content does not fill it** — the side margins are a deliberate calm-first decision bounding the reading width of metrology data. Full-bleed optimization is not adopted; widening at the `2xl` breakpoint requires explicit agreement.
- **Dense exception (1440px):** list-plus-detail pages may widen one step to `max-w-[1440px]`. Current members: H/W management (`ebeam/HardwareView.vue`, 320px list rail + `1fr` detail) and Mag/Pixel 가이드 (`pages/mag-pixel.vue`, 392px sticky input-and-answer rail + `1fr` drawings and reference table). Device Statistics and Time-Series are candidates. Agreed pattern — do not revert.
- **Breakpoints:** Tailwind v4 defaults (`sm 640 / md 768 / lg 1024 / xl 1280 / 2xl 1536`); no custom screens in `main.css`.
- Pages with a sidebar apply `flex` + `min-w-0` on the main pane to prevent horizontal scroll.
- `html { scrollbar-gutter: stable }` globally, so centered content doesn't shift ~8px between scrolling and non-scrolling pages.

### Whitespace Philosophy
Calm-first: vertical rhythm between cards is a uniform `space-y-6` (24px), card padding stays at 16px, and density comes from well-set tables rather than tighter chrome. The page never competes with the data.

## Elevation & Depth

| Level | Treatment | Use |
|---|---|---|
| Flat | No shadow, no border | Page body, toggles, pills |
| Hairline | 1px `--sk-border-soft` | Dividers between nav rows and stat cells |
| Bordered | 1px `--sk-border` | Default card/input edge |
| Paper card | `.dashboard-surface`: `0 1px 0 rgba(0,0,0,0.02), 0 8px 22px -18px rgba(0,0,0,0.18)` | Tables, stat cards. The −18px spread keeps the shadow loose and diffuse — paper, not plastic |
| Paper card (dark) | `inset 0 1px 0 rgba(255,255,255,0.02), 0 8px 22px -18px rgba(0,0,0,0.6)` | The 1px inset top highlight mimics light catching a paper edge |
| Accent trim | `.sk-nav-accent` (`inset 0 -2px 0 0 --sk-accent`), `.sk-fab-active` (`inset 2px 0 0 0 --sk-accent` + faint drop) | Active nav underline; selected FAB row |

The philosophy is **material first, shadow rare**: depth comes from the canvas → surface → muted-surface tonal steps in one hue, not from shadows. Dialog/dropdown shadows managed by NuxtUI keep NuxtUI defaults. The sticky header is `shadow-none`, separated by `--sk-nav-border` + blur.

### Decorative Depth
- `.dashboard-bg-layer` — a fixed, non-interactive radial wash of the accent at 5% (light) / 6% (dark) opacity from the top-right, so the logo's crimson doesn't sit orphaned on the canvas. One instance per page shell; never stacked.

## Shapes

### Border Radius Scale

| Token | Value | Use |
|---|---|---|
| `--sk-r-sidebar` | 6px | FAB sidebar cells, fine notices |
| `--sk-r-chip` | 8px | Filter chips (`<SkChip>`) |
| `--sk-r-nav` | 10px | Nav pills and buttons (`<SkNavPill>`, `<SkBtn>`) |
| `--sk-r-card` | 14px | Cards, panels |
| pill (legacy) | 9999px | `.sk-pill-on` / `.sk-pill-off` status pills only |

Soft rectangles only — anything outside this set is a bug. `rounded-full` is banned on new components; the status pills are the single grandfathered exception.

**Why the variables, and not `rounded-lg`.** NuxtUI overrides Tailwind's `rounded-*` utilities and derives every one of them from a single `--ui-radius` base by fixed multipliers (`sm` 1×, `md` 1.5×, `lg` 2×, `xl` 3×, `2xl` 4×) — a *geometric* ramp. The scale above is not geometric, so **no value of `--ui-radius` can produce 6/8/10/14.** Rather than bend the scale to the framework, we bypass the utilities: `--ui-radius` is left at its default, and `app.config.ts` pins the components to the scale by slot (`card` → `--sk-r-card`, `button` / `input` / `select` / `textarea` → `--sk-r-nav`, `badge` → `--sk-r-chip`). Dialog, popover and dropdown radii stay on NuxtUI's defaults.

So: NuxtUI components inherit the scale automatically, and **hand-written markup uses the variables directly** (`rounded-[var(--sk-r-chip)]`) — never `rounded-lg`/`rounded-2xl`, whose sizes are an artifact of NuxtUI's ramp rather than a decision made here. A `rounded-2xl` on a `<UCard>` is worse than redundant: tailwind-merge lets it *beat* the themed radius, so the card silently leaves the scale.

### Iconography & Imagery
No photography, no illustration — this is a data tool. One icon set: **Lucide** (`@iconify-json/lucide`), used as `icon="i-lucide-<name>"`. Canonical assignments: `search` (inputs), `rotate-ccw` (reset), `download` (CSV export), `info`, `settings`, `loader-circle` + `animate-spin` (loading), `star`/`star-off` (favorites), `arrow-up-narrow-wide`/`arrow-down-wide-narrow`/`arrow-up-down` (sort), `construction` (under construction). `@iconify-json/simple-icons` exists as a dependency but is reserved for brand logos.

## Components

### Selection Primitives

> The single source of truth for the *Selection & Button System (Bolder)* v1.0. When a control has a selected state, use one of these three — not `UButton`.

**`sk-nav-pill`** (`<SkNavPill>`) — NAVIGATE. Active fill `--sk-ink`, text `--sk-ink-fg`, radius `--sk-r-nav` (10px). Used for product tabs, feature tabs, section toggles (BSM/FDC/BM·PM), sub-tabs, sidebar items. `aria-pressed` mandatory.

**`sk-chip`** (`<SkChip>`) — FILTER. Active fill `--sk-brand` (or `tone="ink"`), text `--sk-brand-fg`, radius `--sk-r-chip` (8px). Used for Fab, Category, Lot, Tech, Status chips.

**`sk-btn`** (`<SkBtn>`) — ACTION. `kind="primary"` fills `--sk-ink`; `kind="brand"` fills `--sk-brand` (only inside emphasized panels like "selected device"). Radius `--sk-r-nav`.

Decision flow: changes route/view → `sk-nav-pill` · narrows data on the same page → `sk-chip` · mutates data or triggers an action → `sk-btn`.

### Buttons (NuxtUI)

**`button-default`** — `UButton color="neutral" variant="solid"` for plain actions with no selected state (close modal, submit form).

**`button-ghost`** — `UButton color="neutral" variant="ghost"` for incidental actions (info, settings, dark-mode toggle).

**`button-destructive`** — none exist yet; if one appears: `text-rose-600` text + explicit confirm dialog.

All buttons use Lucide icons; icon-only buttons require `aria-label`; Korean labels prefer verb forms (`CSV 다운로드`, not `다운로드`); disabled buttons also set `cursor-not-allowed`.

### Cards & Containers

**`card`** — Plain NuxtUI `UCard` for ordinary content groups. Header pattern: `flex items-center justify-between gap-3` with an `text-lg font-semibold` title and a `UBadge color="neutral" variant="subtle"` count.

**`dashboard-surface`** — Tables and stat cards that should read as dashboard surfaces. `--sk-surface` background, 1px `--sk-border`, the paper shadow (see Elevation). Radius `--sk-r-card`.

**`meta-bar`** (`EbeamMetaBar`) — The **first component in every page body**; a one-line page header replacing the old `FeatureHeader` + toggle row + stat strip. Left cluster: mono eyebrow (`CD-SEM · R3`) + **fixed `<h1>` title** → 1px vertical divider → `#toggle` slot. Right cluster: inline stats + freshness badge (`EbeamDataFreshness`) + `#actions` slot. Below the bar: demoted context line in `text-xs text-(--sk-ink-muted)`. Core rule: **the title never changes when a tab/view changes** — scope drops to the eyebrow. Toggles are always BLACK-family segmented controls; terracotta chips never appear in a toggle. `stats: MetaBarStat[]` cells (`{ key, value, label, tone?, active? }`) separate with `--sk-border-soft`; `tone` maps to the semantic families; `interactiveStats` turns cells into a `role="radiogroup"` filter with a tone-soft active tint. Rich KPIs (period/device-dependent, or grouped like Align/Meas) stay as cards below the bar, never flattened inline.

**`filter-bar` / `stat-bar`** — Card-shaped (`dashboard-surface`) with `flex flex-wrap gap-3` inside. Multi-metric rows separate cells with `divide-x divide-(--sk-border)` (divide, not border, to avoid doubled edges). Interactive stat cells show `--sk-accent-soft` on hover.

### Navigation

**`top-nav`** (`nav/AppHeader.vue`) — Sticky translucent header: `bg-(--sk-nav-bg)` + `backdrop-blur-md`, bottom border `--sk-nav-border`, `shadow-none`. Category pills; active = `--sk-ink` fill + `.sk-nav-accent` crimson underline.

**`tool-type-tabs`** (`nav/ToolTypeTabs.vue`) — Horizontally scrollable pill group with count badges; 1px `--sk-border-soft` bottom divider.

**`feature-tabs`** (`nav/FeatureTabs.vue`) — 4–7 feature tabs per tool type; `aria-disabled` when inactive; same hairline divider.

**`fab-sidebar`** (`nav/FabSidebar.vue`) — Collapsible rail with favorite stars; the active row takes `.sk-fab-active` (2px crimson left edge, readable even at icon-rail width).

**Row divider rule** — a 1px `--sk-border-soft` hairline separates the *tool row* from the *feature row*. Both rows are pills and visually peers; without the divider the boundary between *"which tool"* and *"how I'm viewing it"* disappears. Drawn **full-bleed** (`border-b` on the `px-*` parent, outside the `max-w-7xl` container) so it runs unbroken across the FAB sidebar.

### Tables

**`data-table`** (UTable) — Header `sticky top-0 bg-(--sk-surface)`. Sort via the three Lucide arrow icons + `aria-sort`. Number columns `font-mono tabular-nums text-right`; ID columns `font-mono`; value cells `text-(--sk-ink)` — never muted. Hover `hover:bg-zinc-50 dark:hover:bg-zinc-800/50`. Empty state: `text-zinc-500` message in the `:empty` slot. Pagination in the card footer: `이전 / 페이지 N/M / 다음`.

### Inputs & Forms

**`text-input`** — `<UInput icon="i-lucide-search" placeholder="검색" />`. Border and radius come from the theme (`--sk-border`, `--sk-r-nav`) via the NuxtUI bridge — do not restate them at the call site. Focus uses the `--sk-focus-ring` treatment.

**`select`** — `<USelect>` / `<USelectMenu>`, same themed border and radius as the input. Option labels Korean, values English. Multi-select filters (Category, Lot, Tech) use the `sk-chip` pattern instead — see `device-statistics.vue`.

### Tags / Badges

**`badge-count`** — `<UBadge color="neutral" variant="subtle">` for row counts and filter counts.

**`pill-on` / `pill-off`** — `.sk-pill-on` / `.sk-pill-off` status pills: 12px, weight 600, 9999px radius (the sanctioned legacy exception), `--sk-on-*` / `--sk-off-*` pairs. Always carry a text label — never color alone.

## Do's and Don'ts

### Do
- Route every color through `--sk-*` variables (`bg-(--sk-surface)`, `text-(--sk-ink)`). It's the simplest way to never forget a dark variant.
- Apply the litmus test before styling any selected state: view changes → BLACK (`sk-nav-pill`), data narrows → TERRACOTTA (`sk-chip`).
- Give data values `--sk-ink` and labels `--sk-ink-muted`, everywhere, especially in dark mode.
- Keep tables quiet: mono tabular numerals, 1px borders, hover highlight, nothing else.
- Keep content at `max-w-7xl` (1280px); use the 1440px dense exception only for agreed list-plus-detail pages.
- Use `aria-pressed` on every toggle, `aria-disabled` + `disabled` together, `aria-label` on icon-only buttons, `aria-sort` on sorted columns.
- Follow Korean voice endings: page titles noun-form (`디바이스 통계`), buttons verb-form (`CSV 다운로드`), empty states `~없습니다.`, errors `~못했습니다.`, help text `~입니다/합니다.` Tokens and keys stay English (`prod_catg_cd`).

### Don't
- Don't use crimson (`--sk-accent`) as a fill — no crimson buttons, no crimson body text, no large crimson areas. Trim only, in its three sanctioned spots.
- Don't mix BLACK and TERRACOTTA in the same role, and never put a terracotta chip in a toggle slot.
- Don't use `--sk-ink-muted` on data cells — it washes out in dark mode next to full-ink columns.
- Don't use `rounded-full` on new components; the radius scale is 6/8/10/14 and nothing else.
- Don't use fixed-lightness classes (`text-zinc-500`, `border-zinc-200`) for supporting text or chrome; they sink into the dark canvas, and they are *cool* against a warm page. Zinc survives only in table hovers and the empty-state message.
- Don't restate a themed default at the call site. `bg-`/`text-`/`border-`/`rounded-` on a NuxtUI component is almost always either redundant with the bridge or actively overriding it — check what the component renders bare before adding a class.
- Don't add shadows beyond the paper-card treatment, and don't restyle NuxtUI's dialog/dropdown shadows.
- Don't change the meta-bar `<h1>` when a tab changes — scope belongs in the eyebrow.
- Don't put a data value below 12px, and don't invent a third sub-12px tier — 10px mono eyebrow and 11px micro-label are the complete list.
- Don't introduce long transitions, skeletons, or shimmers; `transition-colors duration-200`, `animate-spin`, and `sk-pulse` are the entire motion vocabulary.

## Loading States

Loading is never hand-rolled. Four surfaces cover every case, and a page that
fetches must use one of them — a frozen previous page is not a loading state.

| Case | Use | Renders |
|---|---|---|
| A panel that has not rendered yet | `<AppLoadingState>` (default `variant="block"`) | Own `dashboard-surface` card, indeterminate `UProgress`, centered title + optional `description` |
| A row *inside* a card that already exists | `<AppLoadingState variant="inline">` | `loader-circle` + `animate-spin` and the title on one centered line, no second surface |
| A page whose view `await`s its data in setup | `<AppAsyncBoundary title="…">` wrapping the view | A `<Suspense :timeout="0">` whose fallback is the block variant |
| The app shell, before the identity gate resolves | `app/spa-loading-template.html` | Full-viewport spinner + title; the only loading state outside Vue |

Rules:

- **Never nest surfaces.** `variant="inline"` exists because a block variant
  inside a `UCard` renders a card within a card. When the inline row *is* the
  top-level panel, pass `dashboard-surface rounded-2xl` to it instead.
- **Don't fight the padding.** The variants own their padding; pass sizing
  (`h-72`, `flex-1`) rather than a competing `py-*`, which is a specificity
  coin-flip. Tailwind v4 has no `!py-*` prefix escape hatch.
- **A page-level boundary is required whenever the view awaits.** Without it the
  suspension bubbles up to Nuxt's `<NuxtPage>` boundary and the router holds the
  *previous* page on screen with no feedback at all.
- Copy is Korean and ends in `~중입니다.`; match the wording between a view's
  first-load and refetch states so the two don't read as different events.
- Bare-spinner overlays on an image (gallery thumbnails, the lightbox, the
  evidence drawer) are deliberately **not** `AppLoadingState` — they carry no
  text and sit on a non-card surface.

## Responsive Behavior

### Breakpoints

| Name | Width | Key Changes |
|---|---|---|
| Target | 1920×1080 (FHD) | The design target. Content centered at `max-w-7xl` (1280px); dense pages at 1440px; sides stay as margin |
| `xl` | 1280–1536px | Content fills the container; no layout change |
| `lg` | 1024–1280px | Filter bars wrap (`flex-wrap`); tool-type tabs scroll horizontally |
| below `lg` | < 1024px | Not a primary target (internal FHD tool); FAB sidebar collapses to icon rail, tables scroll horizontally inside their cards |

### Touch & Pointer Targets
- Buttons are 40px tall (`py-2.5` + label); pills and chips ≥ 32px with generous horizontal padding — this is a mouse-first internal tool.
- Entire table rows are clickable where a detail view exists (e.g. H/W management list rail).

### Collapsing Strategy
- The FAB sidebar narrows to an icon rail; the `.sk-fab-active` left edge stays legible at rail width.
- Sidebar pages guard against horizontal scroll with `flex` + `min-w-0` on the main pane.
- Tables never wrap numeric content; they scroll horizontally within their card.
- Tool-type tabs scroll horizontally rather than wrapping to a second row.

## Iteration Guide

1. Focus on ONE component at a time; reference it by its name here (`meta-bar`, `sk-chip`, `dashboard-surface`).
2. Never inline hex — every color routes through a `--sk-*` token. If a needed color has no token, add the token to this document first, then to `main.css`.
3. New selected states must pass the BLACK/TERRACOTTA litmus test before any styling begins.
4. New radii must come from the 4-step scale; new text sizes from the Tailwind scale with the 12px floor.
5. When in doubt about emphasis: one weight step up (400→500→600→700) before any color change.
6. Paper + walnut + ink + terracotta + crimson-trim is the complete palette. Don't introduce a new hue; status colors are already provided (`--sk-ok/bad/warn`).
7. This document changes first; `main.css`, `app.config.ts`, and the preview HTML files are updated in the same change.

## Known Gaps

- **Call-site drift to sweep (doc + theme are correct):** some pages still carry chrome classes that predate the NuxtUI bridge — `rounded-2xl` on cards (which *beats* the themed 14px), `border-zinc-*` toolbar dividers, `bg-zinc-*` table headers, `text-zinc-900` card titles, and raw `rose`/`amber`/`emerald` where the `--sk-ok/warn/bad` families belong. These are **deletions**, not replacements: the correct value already sits underneath. `장비 리스트` / `스토리지` (`ToolInventoryView.vue`, `StorageView.vue`) have been **swept and now read as the reference case** — data tables at `text-xs` full-`--sk-ink` values, `text-[11px]` muted headers, sanctioned zinc only in the row hover.
- **Font-tier + dim-colour sweep (done, 2026-07-15):** non-sanctioned type tiers (`text-[9px]`, `text-[9.5px]`, `text-[10.5px]`, `text-[11.5px]`) were normalised to the sanctioned 11px/12px, and cool `text-zinc-400/500` supporting text was replaced with the warmer, higher-contrast `--sk-ink-muted`. Going forward, prefer the **semantic type classes** (§Typography → Semantic type classes) over re-introducing ad-hoc `text-[…]` sizes; adopting them across the remaining components is the open follow-up.
- Equipment status sub-tabs (`EquipmentStatusSubTabs.vue`) are a hand-rolled white/zinc segmented control; they are a NAVIGATE control and must become `<SkNavPill>` (ink fill).
- Several pages are still English in the UI copy (placeholders, `Reset`, empty states, error lines) against the Korean-voice rule.
- The `--sk-accent-soft` hover on interactive stat cells is specified but not yet applied everywhere.
- Destructive actions have no component yet; the `text-rose-600` + confirm-dialog rule is untested.
- `prefers-reduced-motion` is not handled; only `animate-spin` and `sk-pulse` would be affected.
- Skeleton/shimmer loading states are deliberately not adopted; if load times grow, that decision should be revisited here first.
- `--sk-accent-border` / `--sk-accent-tint` are defined but currently unused (the old crimson-bordered card treatment was retired in favor of the paper shadow).
- The zinc scale remains in `main.css` for Tailwind compatibility; it is no longer NuxtUI's neutral (that is `paper` now), and its only sanctioned direct uses are table hovers and empty-state text.

## Changelog

- 2026-04-26: Initial version — tokens extracted from `main.css`, `app.config.ts`, and components; preview HTML added.
- 2026-05-12: *Selection & Button System (Bolder)* v1.0: BLACK = nav / TERRACOTTA = filter semantics, 4-step radius scale, `SkNavPill` / `SkChip` / `SkBtn` primitives, `--sk-ink*` / `--sk-brand*` / `--sk-r-*` tokens.
- 2026-05-16: Full-bleed `--sk-border-soft` row divider between tool row and feature row.
- 2026-05-23: Layout widths codified (FHD target, 1280px cap); meta bar (`EbeamMetaBar`) pattern added and adopted on five views; H/W management rebuilt as Dense 2-column with the 1440px exception.
- 2026-05-24: Ink text hierarchy codified — data values get `--sk-ink`, muted ink for labels only.
- 2026-07-13: Full polish — translated to English, promoted to source of truth, token values synced to the Paper/Walnut theme, missing tokens documented, focus ring + type refinements added.
- 2026-07-13: **Reformatted to the standard design-system document format** (Overview / Colors / Typography / Layout / Elevation & Depth / Shapes / Components / Do's and Don'ts / Responsive Behavior / Iteration Guide / Known Gaps). Voice & tone and accessibility rules folded into Do's and Don'ts; code-drift items moved to Known Gaps.
- 2026-07-26: **Mag/Pixel 가이드 aligned to the system** (design option 2a). The page adopts `meta-bar` as its first body component, joins the 1440px dense exception with a 392px sticky input-and-answer rail, and moves its cards to `dashboard-surface` + `--sk-r-card` (they were `rounded-lg` + `bg-white dark:bg-zinc-950`, i.e. off the radius scale and outside the bridge). Series and 여유 마진 became `SkChip` by the litmus test — they narrow data, they don't change the view. Raw `emerald`/`amber`/`red`/`indigo` were replaced by the `--sk-ok/warn/bad` families and terracotta. Added the **Dark Field** token family (§Colors) for simulated SEM imagery, the one sanctioned non-inverting set in the system.
- 2026-07-13: **NuxtUI token bridge** — `app.config.ts` now genuinely implements the mapping this document always claimed it did. NuxtUI's `primary`/`neutral` point at a new warm `paper` ramp instead of cool zinc, and the `--ui-*` semantic tokens are bridged to `--sk-*` (unlayered, `:root`-only, so dark mode follows the `--sk-*` inversion automatically). NuxtUI components now inherit the design system with no call-site classes. Resolved three doc↔code conflicts: **(1)** the §Shapes-vs-§Inputs radius contradiction — components are pinned to the 6/8/10/14 scale by slot in `app.config.ts`, since NuxtUI's geometric `--ui-radius` ramp cannot express a non-geometric scale; **(2)** the 12px floor, which the code broke 311× — two sub-12px tiers (10px mono eyebrow, 11px micro-label) are now sanctioned for *labels only*, with data values still hard-floored at 12px; **(3)** the cool-zinc neutral underlying every NuxtUI component on a warm page. Also landed the previously-missing `--sk-focus-ring` and removed the duplicate `--sk-ink` definition.
