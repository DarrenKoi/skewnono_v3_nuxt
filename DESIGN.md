# DESIGN.md — SKEWNONO Design System

> This document is the **single source of truth** for the SKEWNONO frontend's visual language. Code follows this document; where they disagree, the code is corrected. Token identifiers stay in English to match Tailwind/NuxtUI class names. Implemented in `frontend/app/assets/css/main.css` (tokens) and `frontend/app/app.config.ts` (NuxtUI mapping).
>
> **Teammates building a page to merge into SKEWNONO:** start at [Building a Page That Merges Cleanly](#building-a-page-that-merges-cleanly) — it carries a copy-paste token block, plain-CSS recipes and the pre-merge checklist, and tells you which other sections to read.

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

## Building a Page That Merges Cleanly

This section is for a teammate building a page **outside** SKEWNONO's Nuxt app — a standalone Vite app under `apps/<slug>/`, or a tool on its own server — that should look like it belongs here and be promotable into `frontend/app/` later without a redesign. It is self-contained: everything below is plain CSS and plain HTML, with no Tailwind, NuxtUI or Vue assumed. Where and how such a page is hosted is covered by `docs/contributing/README.md`; this section covers only how it looks.

### What you have, by where you build

| You are building | You get for free | You bring yourself |
|---|---|---|
| Inside `frontend/app/` (after promotion) | Tokens, fonts, the app shell, `<SkNavPill>` / `<SkChip>`, `EbeamMetaBar`, `AppLoadingState` / `AppEmptyState`, and NuxtUI components themed by the bridge | Nothing — use the components named in §Components |
| A Vite app in `apps/<slug>/`, or your own stack | Nothing. No header, no tokens, no NuxtUI | Steps 1–4 below |

### 1. Tokens — copy this block verbatim

Every color, radius and the focus ring. Generated from `frontend/app/assets/css/main.css`; do not retype values from the prose in §Colors, and do not add a hue that is not here. Dark mode is the class `dark` on `<html>` — the page never reads `prefers-color-scheme` directly.

```css
:root {
  --sk-canvas: oklch(0.96 0.012 80);
  --sk-surface: oklch(0.99 0.006 80);
  --sk-muted-surface: oklch(0.97 0.01 80);
  --sk-border: oklch(0.91 0.014 80);
  --sk-border-soft: oklch(0.94 0.01 80);
  --sk-nav-bg: oklch(0.97 0.01 80 / 0.82);
  --sk-nav-border: oklch(0.90 0.014 80);
  --sk-ink-muted: oklch(0.47 0.014 60);
  --sk-ink-subtle: oklch(0.66 0.012 70);
  --sk-chip-bg: oklch(0.95 0.014 80);
  --sk-chip-text: oklch(0.45 0.014 60);
  --sk-on-bg: #d9f5e8;
  --sk-on-fg: #0f5132;
  --sk-off-bg: oklch(0.95 0.014 80);
  --sk-off-fg: oklch(0.45 0.014 60);
  --sk-field: oklch(0.21 0.008 70);
  --sk-field-ink: oklch(0.94 0.008 80);
  --sk-field-core: oklch(0.40 0.014 60);
  --sk-accent: oklch(0.58 0.13 35);
  --sk-accent-soft: oklch(0.95 0.025 60);
  --sk-accent-border: oklch(0.58 0.13 35 / 0.22);
  --sk-accent-tint: oklch(0.58 0.13 35 / 0.06);
  --sk-ok: oklch(0.62 0.13 145);
  --sk-ok-soft: oklch(0.94 0.05 145);
  --sk-ok-border: oklch(0.62 0.13 145 / 0.32);
  --sk-bad: oklch(0.58 0.18 28);
  --sk-bad-soft: oklch(0.94 0.04 30);
  --sk-bad-border: oklch(0.58 0.18 28 / 0.32);
  --sk-bad-soft-hover: oklch(0.89 0.07 30);
  --sk-bad-tint: oklch(0.58 0.18 28 / 0.06);
  --sk-warn: oklch(0.70 0.15 75);
  --sk-warn-soft: oklch(0.94 0.06 85);
  --sk-warn-border: oklch(0.70 0.15 75 / 0.32);
  --sk-ink: #15110D;
  --sk-ink-fg: #F8F4EC;
  --sk-brand: #C75A3C;
  --sk-brand-fg: #FFF7F1;
  --sk-brand-soft: #F3DCD2;
  --sk-brand-ink: #8A3D27;
  --sk-r-sidebar: 6px;
  --sk-r-chip: 8px;
  --sk-r-nav: 10px;
  --sk-r-card: 14px;
  --sk-focus-ring: oklch(0.58 0.13 35 / 0.45);
}

.dark {
  --sk-canvas: oklch(0.21 0.008 70);
  --sk-surface: oklch(0.245 0.008 70);
  --sk-muted-surface: oklch(0.225 0.008 70);
  --sk-border: oklch(0.295 0.008 70);
  --sk-border-soft: oklch(0.265 0.008 70);
  --sk-nav-bg: oklch(0.225 0.008 70 / 0.78);
  --sk-nav-border: oklch(0.30 0.008 70);
  --sk-ink-muted: oklch(0.74 0.008 70);
  --sk-ink-subtle: oklch(0.56 0.008 70);
  --sk-chip-bg: oklch(0.285 0.008 70);
  --sk-chip-text: oklch(0.74 0.008 70);
  --sk-on-bg: #052e16;
  --sk-on-fg: #bbf7d0;
  --sk-off-bg: oklch(0.285 0.008 70);
  --sk-off-fg: oklch(0.74 0.008 70);
  --sk-accent: oklch(0.74 0.14 38);
  --sk-accent-soft: oklch(0.34 0.05 38);
  --sk-accent-border: oklch(0.74 0.14 38 / 0.32);
  --sk-accent-tint: oklch(0.74 0.14 38 / 0.10);
  --sk-ok: oklch(0.78 0.14 150);
  --sk-ok-soft: oklch(0.32 0.06 150);
  --sk-ok-border: oklch(0.78 0.14 150 / 0.32);
  --sk-bad: oklch(0.72 0.17 28);
  --sk-bad-soft: oklch(0.32 0.06 28);
  --sk-bad-border: oklch(0.72 0.17 28 / 0.32);
  --sk-bad-soft-hover: oklch(0.38 0.08 28);
  --sk-bad-tint: oklch(0.72 0.17 28 / 0.10);
  --sk-warn: oklch(0.80 0.15 78);
  --sk-warn-soft: oklch(0.34 0.06 78);
  --sk-warn-border: oklch(0.80 0.15 78 / 0.32);
  --sk-ink: #F4EFE6;
  --sk-ink-fg: #15110D;
  --sk-brand: #E0553F;
  --sk-brand-fg: #FFF7F1;
  --sk-brand-soft: oklch(0.30 0.05 38);
  --sk-brand-ink: #F3DCD2;
  --sk-focus-ring: oklch(0.74 0.14 38 / 0.45);
}
```

`--sk-field*` has no `.dark` value on purpose (§Colors → Dark Field).

### 2. Fonts — copy the files, never link a CDN

Production is an offline internal network, so a `<link>` to Google Fonts renders as a fallback font there. Copy the eleven woff2 files from `frontend/public/fonts/` and the matching `@font-face` blocks from the top of `main.css`. Only the Medium face is unusual: Spoqa Han Sans Neo has no 600, so its 500 file declares `font-weight: 500 600`.

```css
:root {
  --font-sans: 'Spoqa Han Sans Neo', 'Public Sans', 'Apple SD Gothic Neo', 'Malgun Gothic', 'Segoe UI', sans-serif;
  --font-mono: 'JetBrains Mono', ui-monospace, 'Cascadia Code', 'Segoe UI Mono', 'SFMono-Regular', Menlo, Consolas, monospace;
}
```

### 3. Base and the recipes you will actually need

These restate the app's own rules in plain CSS. Class names match the app's so a promoted page keeps its markup.

```css
html { scrollbar-gutter: stable; }
body {
  margin: 0;
  background: var(--sk-canvas);
  color: var(--sk-ink);
  font-family: var(--font-sans);
  font-size: 14px;
}
:focus-visible { outline: 2px solid var(--sk-focus-ring); outline-offset: 2px; }
button:not(:disabled) { cursor: pointer; }

/* Page container — 1280px, centered. Do not go full-bleed. */
.sk-page { max-width: 1280px; margin: 0 auto; padding: 32px; display: grid; gap: 24px; }

/* Card — the only elevated surface. One border, one loose shadow, 14px radius. */
.dashboard-surface {
  border: 1px solid var(--sk-border);
  border-radius: var(--sk-r-card);
  background: var(--sk-surface);
  box-shadow: 0 1px 0 rgba(0, 0, 0, 0.02), 0 8px 22px -18px rgba(0, 0, 0, 0.18);
  padding: 16px;
}
.dark .dashboard-surface {
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.02), 0 8px 22px -18px rgba(0, 0, 0, 0.6);
}

/* NAVIGATE — anything that changes the view. Active = ink. */
.sk-nav-pill {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 9px 16px; font: 500 14px var(--font-sans); white-space: nowrap;
  border: 1px solid var(--sk-border); border-radius: var(--sk-r-nav);
  background: transparent; color: var(--sk-ink-muted);
  transition: background-color 0.15s ease, color 0.15s ease, border-color 0.15s ease;
}
.sk-nav-pill:hover { background: var(--sk-muted-surface); color: var(--sk-ink); }
.sk-nav-pill[aria-pressed='true'] {
  background: var(--sk-ink); color: var(--sk-ink-fg); border-color: var(--sk-ink); font-weight: 600;
}

/* FILTER — anything that narrows the data on the same view. Active = terracotta. */
.sk-chip {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 7px 12px; font: 500 13px var(--font-sans); white-space: nowrap;
  border: 1px solid var(--sk-border); border-radius: var(--sk-r-chip);
  background: var(--sk-surface); color: var(--sk-ink-muted);
  transition: background-color 0.12s ease, color 0.12s ease, border-color 0.12s ease;
}
.sk-chip:hover { background: var(--sk-muted-surface); color: var(--sk-ink); }
.sk-chip[aria-pressed='true'] {
  background: var(--sk-brand); color: var(--sk-brand-fg); border-color: var(--sk-brand); font-weight: 600;
}

/* ACTION — a button that does something. Primary = ink fill; everything else is quiet. */
.sk-btn {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 10px 16px; font: 500 14px var(--font-sans);
  border: 1px solid var(--sk-border); border-radius: var(--sk-r-nav);
  background: var(--sk-surface); color: var(--sk-ink);
}
.sk-btn:hover { background: var(--sk-muted-surface); }
.sk-btn--primary { background: var(--sk-ink); color: var(--sk-ink-fg); border-color: var(--sk-ink); }
.sk-btn:disabled { opacity: 0.5; cursor: not-allowed; }

/* Inputs share the button's radius and the card's border. */
.sk-input {
  padding: 8px 12px; font: 400 14px var(--font-sans);
  border: 1px solid var(--sk-border); border-radius: var(--sk-r-nav);
  background: var(--sk-surface); color: var(--sk-ink);
}

/* Type roles — values are ink, labels are muted. A value is never below 12px. */
.sk-page-title { font-size: 30px; font-weight: 700; line-height: 1.2; letter-spacing: -0.01em; color: var(--sk-ink); }
.sk-heading    { font-size: 18px; font-weight: 600; line-height: 1.4; color: var(--sk-ink); }
.sk-body       { font-size: 14px; font-weight: 400; line-height: 1.5; color: var(--sk-ink); }
.sk-meta       { font-size: 12px; font-weight: 400; line-height: 1.4; color: var(--sk-ink-muted); }
.sk-label      { font-size: 11px; font-weight: 600; line-height: 1.35; color: var(--sk-ink-muted); }
.sk-value      { font-size: 12px; font-weight: 500; line-height: 1.35; color: var(--sk-ink); }
.sk-value-num  { font: 500 12px/1.35 var(--font-mono); font-variant-numeric: tabular-nums; color: var(--sk-ink); }
.sk-eyebrow    { font: 600 10px/1.4 var(--font-mono); letter-spacing: 0.06em; text-transform: uppercase; color: var(--sk-ink-muted); }

/* Table — quiet. Headers are labels, cells are values, numbers are mono and right-aligned. */
.sk-table { width: 100%; border-collapse: collapse; }
.sk-table th { text-align: left; padding: 8px 12px; white-space: nowrap; border-bottom: 1px solid var(--sk-border);
               font-size: 11px; font-weight: 600; color: var(--sk-ink-muted); }
.sk-table td { padding: 8px 12px; border-bottom: 1px solid var(--sk-border-soft); font-size: 12px; color: var(--sk-ink); }
.sk-table td.num { text-align: right; font-family: var(--font-mono); font-variant-numeric: tabular-nums; }
.sk-table tbody tr:hover { background: var(--sk-muted-surface); }

/* Status — always with a text label, never color alone. */
.sk-status { display: inline-flex; align-items: center; padding: 2px 8px; border: 1px solid; border-radius: var(--sk-r-sidebar);
             font-size: 12px; font-weight: 600; }
.sk-status--ok   { background: var(--sk-ok-soft);   border-color: var(--sk-ok-border);   color: var(--sk-ok); }
.sk-status--warn { background: var(--sk-warn-soft); border-color: var(--sk-warn-border); color: var(--sk-warn); }
.sk-status--bad  { background: var(--sk-bad-soft);  border-color: var(--sk-bad-border);  color: var(--sk-bad); }
```

`.sk-page`, `.sk-btn`, `.sk-input`, `.sk-table` and `.sk-status` exist only in this starter: inside the Nuxt app those jobs are done by the layout, `UButton`, `UInput`, `UTable` and `UBadge` through the token bridge. On promotion they are swapped for the components, which is a mechanical change because the values are the same.

### 4. Page skeleton

Every page opens with the same one-line header — mono eyebrow, a Korean `<h1>` that never changes when a tab does, then view toggles — followed by cards at a 24px rhythm.

```html
<main class="sk-page">
  <header style="display: flex; align-items: center; gap: 12px;">
    <span class="sk-eyebrow">CD-SEM · R3</span>
    <h1 class="sk-page-title">페이지 제목</h1>
    <nav style="display: flex; gap: 4px; margin-left: 12px;">
      <button class="sk-nav-pill" aria-pressed="true">요약</button>
      <button class="sk-nav-pill" aria-pressed="false">상세</button>
    </nav>
  </header>

  <section class="dashboard-surface" style="display: flex; flex-wrap: wrap; gap: 12px;">
    <button class="sk-chip" aria-pressed="true">DRAM</button>
    <button class="sk-chip" aria-pressed="false">NAND</button>
  </section>

  <section class="dashboard-surface">
    <table class="sk-table">
      <thead><tr><th>장비</th><th>상태</th><th style="text-align: right;">CD (nm)</th></tr></thead>
      <tbody><tr><td>ECD101</td><td><span class="sk-status sk-status--ok">정상</span></td><td class="num">24.18</td></tr></tbody>
    </table>
  </section>
</main>
```

### 5. Before you ask for a merge

- [ ] No hex, `rgb()` or named color outside the token block — search the source for `#` and `rgb(`. Chart series are the one exception (§Iteration Guide, rule 2).
- [ ] Every selected state passes the litmus test: changes the view → ink `sk-nav-pill`; narrows the data → terracotta `sk-chip`. Never both on one control, and crimson (`--sk-accent`) is never a fill.
- [ ] Data values are `--sk-ink` and at least 12px; only labels are `--sk-ink-muted`. Numbers and IDs are mono with `tabular-nums`.
- [ ] Every radius is one of `--sk-r-sidebar / chip / nav / card` (6 / 8 / 10 / 14px). No `border-radius: 9999px`, no other value.
- [ ] One shadow only — the card's. Depth comes from canvas → surface → muted-surface.
- [ ] Checked in **both** themes by toggling `class="dark"` on `<html>`. A color that did not come from a token is the usual reason dark mode breaks.
- [ ] No network fonts, icon CDNs or external images. Icons are Lucide, bundled.
- [ ] UI copy is Korean with the endings in §Do's and Don'ts; identifiers and keys stay English.
- [ ] Loading shows a spinner and a `~중입니다.` line, an empty result shows a `~없습니다.` line. No skeletons or shimmers.
- [ ] Content stays within 1280px at 1920×1080.

Read next, in this order: §Overview, §Colors, §Typography → Semantic type classes, §Components → Selection Primitives, §Do's and Don'ts. The long scope-bar history under §Layout and the §Changelog describe SKEWNONO's own lab pages and can be skipped.

## Colors

Every token's exact light and dark value is in the copy-paste block under [Building a Page That Merges Cleanly](#1-tokens--copy-this-block-verbatim); the entries below say what each one is *for*. All colors are defined as light/dark pairs on `:root` and `.dark` and must be consumed through the `--sk-*` variables (`bg-(--sk-surface)`, `text-(--sk-ink)`), never as inline hex. Values below read **light / dark**.

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
- **Chip Bg / Text** (`--sk-chip-bg` — `oklch(0.95 0.014 80)` / `oklch(0.285 0.008 70)`, `--sk-chip-text`): The recessed track a segmented control sits in (`sk/SegmentedToggle.vue`), and the hover fill of a bare icon button. One step darker than canvas, so the raised segment reads as lifted without a shadow.
- **Nav Bg / Border** (`--sk-nav-bg`, `--sk-nav-border`): Translucent sticky-header pair (canvas tone at ~80% alpha + `backdrop-blur-md`).

### Text
- **Ink** (`--sk-ink` — `#15110D` / `#F4EFE6`): Headings, body, and **all data values in tables** (ID, model, vendor, IP, version, measurements).
- **Ink Muted** (`--sk-ink-muted` — `oklch(0.47 0.014 60)` / `oklch(0.74 0.008 70)`): Labels, captions, header buttons, meta info — *never data values*. In dark mode muted ink is intentionally dim; on a value column it washes out next to full-ink columns.
- **Ink Subtle** (`--sk-ink-subtle` — `oklch(0.66 0.012 70)` / `oklch(0.56 0.008 70)`): Disabled / de-emphasized text.
- Litmus test — *"Is this a **value** the user came to read, or a **label** describing it? Value → ink; label → ink-muted."*

### Semantic
- **OK** (`--sk-ok` / `-soft` / `-border` — `oklch(0.62 0.13 145)` / `oklch(0.78 0.14 150)`): Connected, healthy. Soft fills sit on muted-surface; borders at 32% alpha so badges read as labels, not buttons.
- **Bad** (`--sk-bad` family — `oklch(0.58 0.18 28)` / `oklch(0.72 0.17 28)`): Down, error.
- **Bad · hover** (`--sk-bad-soft-hover` — `oklch(0.89 0.07 30)` / `oklch(0.38 0.08 28)`): The `-soft` fill when a bad-state element is *clickable*. Light moves away from the page (darker), dark moves away from the canvas (lighter) — the direction the rest of the system hovers. The step is L ±0.05–0.06, calibrated to the `rose-100 → rose-200` distance it replaced, because that is the change users have actually been seeing. **Only `--sk-bad` has a hover value**, because it is the one status family with a clickable member (the outlier badge in `LotTable.vue`). Do not add `--sk-ok-*-hover` / `--sk-warn-*-hover` speculatively — an unused token is one nobody knows has never been looked at.
- **Bad · tint** (`--sk-bad-tint` — bad at `6%` / `10%` alpha): A whole *row or card* washed because something in it is bad, as opposed to the `-soft` fill of the badge naming it. Two strengths of red have to coexist on one surface — a card tint under a badge — and the alpha-over-surface form is what keeps the weaker one weak in both themes. Same construction as `--sk-accent-tint`.
- **Warn** (`--sk-warn` family — `oklch(0.70 0.15 75)` / `oklch(0.80 0.15 78)`): Degraded.
- **On pill** (`--sk-on-bg`/`--sk-on-fg` — `#d9f5e8`/`#0f5132` / `#052e16`/`#bbf7d0`): Equipment running state, via `.sk-pill-on`.
- **Off pill** (`--sk-off-bg`/`--sk-off-fg` — warm gray pair): Idle/maintenance, via `.sk-pill-off`.
- **Error text** (`text-rose-600 dark:text-rose-400`): Message lines only.
- **Focus ring** (`--sk-focus-ring` — accent at 45% alpha): `outline: 2px solid; outline-offset: 2px` on `:focus-visible`, one ring color for both selection families.

### Dark Field (SEM imagery only)

Real CD-SEM images are dark-field, so a simulated micrograph cannot invert with the theme — a "light mode" SEM image would be a different photograph, not the same one relit. These three are therefore declared in `:root` **and deliberately omitted from `.dark`**, the one place in the system where that asymmetry is correct rather than a bug.

- **Field** (`--sk-field` — `oklch(0.21 0.008 70)`): The dark canvas of any simulated SEM view. Deliberately the *walnut* dark-mode canvas value rather than a raw slate/near-black, so the imagery still reads as part of this system when it sits on cream.
- **Field Ink** (`--sk-field-ink` — `oklch(0.94 0.008 80)`): The bright sidewall rim — cream, not cool white.
- **Field Core** (`--sk-field-core` — `oklch(0.40 0.014 60)`): The duller line top/interior between rims.

Scope is exactly the simulated imagery (`magpixel/PatternSchematic.vue`, `magpixel/SemSimulation.vue`). Chrome around the image — captions, legends, margin labels — stays on the normal inverting tokens. Margin hatching over the field uses **terracotta** (`--sk-brand`), because the margin is the value the 여유 마진 filter produces; crimson stays trim-only and is not used here. `SemSimulation.vue` additionally hard-codes the sRGB resolution of these three (`27,24,20` / `78,70,64` / `238,235,229`) because it interpolates between them in JS; if a value here changes, that triple changes with it.

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

All fonts are **self-hosted**: woff2 only, in `frontend/public/fonts/`. Public Sans and JetBrains Mono come from `@fontsource/*`; Spoqa Han Sans Neo comes from the `spoqa-han-sans` npm package (v3.3.0, `Subset/SpoqaHanSansNeo/*.woff2`, SIL OFL 1.1). No CDN or Google Fonts access, ever (offline principle).

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
| micro-label | 11px | 500–600 | 16px | 0 to +0.02em | **Labels only** — table header cells. Never a data value — meta-bar stat captions sit on the 12px `.sk-meta` tier (2026-08-26) |
| eyebrow | 10px | 500–600 mono | 1.4 | +0.06em, uppercase | Meta-bar kickers (`CD-SEM · R3`) — mono caps only |

### Principles
Weight carries hierarchy, not color: 400 body → 500 nav labels/buttons → 600 section titles/pills → 700 page titles and big numbers. Number and ID columns always take `font-mono tabular-nums`; tabular figures are mandatory wherever numbers update in place. Korean labels keep natural spacing with `whitespace-nowrap` on header cells; Korean paragraphs (help text, empty states) take `leading-relaxed` — dense Hangul needs the extra line height at 14–16px. Page titles are Korean; the eyebrow above them is English (`CD-SEM`, `HV-SEM`).

**The sub-12px rule.** Metrology screens are dense, and two tiers below the floor earn their place: the 10px mono **eyebrow** and the 11px **micro-label**. Both are strictly *chrome that names things* — a column header, a stat caption, a kicker. The line that does not move: **a data value never renders below 12px.** If a value doesn't fit, the column is too narrow; if a label doesn't fit at 11px, shorten the label. Nothing else goes under 12px, and no new tier gets invented — 10 and 11 are the whole list.

### Semantic type classes

The hierarchy above is implemented as a small set of **role-named classes** in `main.css`, so type is styled by *purpose and location*, not by ad-hoc `text-[…]` / `text-(--sk-…)` utilities scattered per call site. Each class bundles size + weight + colour + family; a change to a role lands in **one place**, and the class name documents intent. This is the mechanism that keeps the type consistent — hand-written `text-[9.5px]`, `text-[10.5px]`, `text-[11.5px]` and `text-zinc-400/500` on content are the drift these replace.

| Class | Role — purpose / location | Size · weight · colour |
|---|---|---|
| `.sk-eyebrow` | Mono uppercase kicker (meta-bar, section kicker) | 10px · 600 · mono +0.06em uppercase · ink-muted |
| `.sk-label` | Field / column / caption **label** (table headers) | 11px · 600 · ink-muted |
| `.sk-value` | A data **value** (table cell, stat text, ID) | 12px · 500 · **ink** |
| `.sk-value-num` | A **numeric** value (mono + tabular figures) | 12px · 500 · mono tabular · **ink** |
| `.sk-meta` | Secondary / supporting text (helper, timestamp, de-emphasised) | 12px · 400 · ink-muted |
| `.sk-body` | Body copy (descriptions, empty states, help) | 14px · 400 · ink |
| `.sk-title` | Compact panel / card title (dense dashboards) | 13px · 600 · ink |
| `.sk-heading` | Card / section heading | 18px · 600 · ink |
| `.sk-page-title` | Page title (`<h1>`) | 30px · 700 · tracking-tight · ink |

Rules that fall out of the table, enforced by which class you pick: **values are ink, labels are muted** (choosing `.sk-value` vs `.sk-label` *is* the litmus test); **a value is never `.sk-eyebrow`/`.sk-label`** (those are sub-12px, chrome-only); dark-mode colour follows for free because the classes reference `--sk-*` tokens. Spacing, alignment and layout stay as Tailwind utilities at the call site — these classes own type only. NuxtUI components keep inheriting type through the token bridge; use these on hand-written markup.

### The row-card tier

The table above is calibrated for a **real table**: a shared column header carries the field name once, and the eye compares straight down a column. Some screens trade that density away — one record becomes one card, read top-to-bottom in passing rather than scanned across a grid. A card has no column header, so every value carries its own inline label, and both have to survive a single reading. The table tiers are too small for that job, so those screens use a second, larger set of roles:

| Class | Role — purpose / location | Size · weight · colour |
|---|---|---|
| `.sk-card-id` | The identifier the card is **about** (`lot_cd`, `recipe_id`) | 18px · 700 · mono tabular -0.01em · ink |
| `.sk-card-desc` | Prose on a card (`ctn_desc`, `oper_desc`) — never truncated | 15px/1.45 · 400 · ink |
| `.sk-field-label` | Inline label on a meta line (`상한 초과`, `판정 범위`) | 13px · 400 · ink-subtle |
| `.sk-field-value` | The number that label points at | 14px · 500 · mono tabular · ink-muted |
| `.sk-field-name` | A raw **backend field name** shown to the user (`prod_catg_cd`) | 13px · 400 · mono · ink-subtle |
| `.sk-panel-title` | Title of a panel holding cards | 16px · 700 · ink |
| `.sk-hint` | Short guidance beside a panel title ("체크박스로 여러 개 선택") | 14px · 400 · ink-muted |
| `.sk-caption` | Footnote / caption under a card stack | 13px/1.5 · 400 · ink-muted |

Three rules govern the tier. **Nothing goes below 13px** — the sub-12px chrome tiers do not exist here, because on a card there is no column header to demote and a label sits inline with its value. **`.sk-field-name` is the one mono-13px exception**, and it exists to hold raw DB column names visually apart from the Korean words a person actually reads; a Korean label never takes it. **Prose is never truncated** — `.sk-card-desc` wraps, because the reason to spend a card's vertical budget is to show the description the table had to clip. Emphasis is a call-site utility (`.sk-field-value font-semibold text-(--sk-ink)` for the one number that matters), not a second class.

Two shapes pair with the tier, split by whether the colour needs a JS branch:

- **`.sk-badge`** (`main.css`) — the short tag beside a card headline: health, stage, bucket, `oper_id`, category. 24px tall, mono 13px; `.sk-badge-lg` steps it to 26px/14px for the detail header, where it stands beside a 22px `lot_cd` rather than an 18px one. Geometry and type only — the caller supplies colour, as a utility pair or as an inline style from `healthTokens`.
- **`CHIP_BASE` / `CHIP_BASE_MONO`** (`utils/chipClass.ts`) — filter chips, 34px tall with a 14px label. These live in TS rather than CSS because a chip's colour *does* need a branch: always apply them together with `chipClass(active)`.

Health colour is never computed at a call site. `healthTokens.ts` owns the whole mapping — `healthSwatches`, plus `healthStripeColor(health)` and `healthBadgeStyle(health, isDark)` — so a `null` verdict ("룰이 없어 판정하지 않음") renders neutral grey everywhere instead of reading as grey on one screen and green on the next.

Charts can reach none of the above: ECharts paints to a canvas, where CSS classes and `var(--font-mono)` do not apply. `utils/chartType.ts` restates the tier's floor for that one context — `CHART_AXIS_LABEL` (mono 13px) and `CHART_LEGEND_LABEL` — and every chart on these screens reads from it.

Adopted by: CD-SEM 디바이스 통계 (`index.vue`), 디바이스 분석 (`comparison.vue`), `LotTable`, `LotDetailModal`, `TrendChart`, `StageChip`, `CompareCart`, `DrillSlideover`. Screens that are genuinely tables keep the table tiers.

## Layout

### Spacing System
- **Base unit:** 4px (Tailwind default scale).
- **Recurring tokens:** `gap-1`/`p-1` 4px (pill groups) · `gap-2`/`p-2` 8px (input interiors, button groups) · `gap-3`/`p-3` 12px (card headers, filter-bar controls) · `p-4` 16px (card padding) · `gap-6`/`space-y-6` 24px (between cards) · `py-2.5` 10px (button vertical padding).

### Grid & Container
- **Max content width:** `max-w-7xl mx-auto` (1280px), centered. **The target screen is FHD (1920×1080) but content does not fill it** — the side margins are a deliberate calm-first decision bounding the reading width of metrology data. Full-bleed optimization is not adopted; widening at the `2xl` breakpoint requires explicit agreement.
- **Dense exception (1440px):** list-plus-detail pages may widen one step to `max-w-[1440px]`. Current member: Mag/Pixel 가이드 (`pages/mag-pixel.vue`, 392px sticky input-and-answer rail + `1fr` drawings and reference table). Recipe 비교 (`ebeam/RecipeCompareView.vue`) runs the same width. The 실험실 page (`ebeam/LabView.vue`, routed at `pages/ebeam/cd-sem/[fab]/tttm.vue`) — 장비간 스큐 관리 and PM 플래닝 were separate views until 2026-09-01 and are one page whose 보기 chips choose the panels — keeps the same width on the **scope-bar** layout below rather than the rail one; H/W 관리 (`ebeam/HardwareView.vue`, since 2026-08-25) runs that layout's *model-gated* strip, named inside the rule. Device Statistics and Time-Series are candidates. Agreed pattern — do not revert.
  - **The rail rule:** every control that changes *what is being analysed* — the selection, the filter, the threshold — lives in the rail, together with the roll-up of what it costs. The results column may still switch *which view of the same answer* it shows (TTTM's cell tab strip above the pairwise matrix), because that changes nothing the rest of the page is computed from. The split is why the width is granted: a page whose results column re-filters the data has stopped being list-plus-detail and should go back to one column.
  - **The scope-bar rule (2026-08-18):** where the analysis is meaningless until the user has *said what to analyse*, the controls stop being a rail and become one full-width bar above the results — `EbeamScopeBar`, titled **비교 대상**. The rail rule's substance is unchanged (controls above, results below, never mixed); what changes is the axis, and the reason is reading order. A rail puts the first decision to the side of a screen already full of numbers; a bar puts it first, which is where a required decision belongs. Two conditions make this the right choice over a rail, and both must hold:
    - **The results are gated.** Until the scope is set, the results area carries an explicit `AppEmptyState` naming the missing choice — never a skeleton (which promises data that is not coming) and never a zeroed card (which reads as a computed verdict). TTTM and PM 플래닝 gate on the **recipe** alone; the parameter stays optional because folding every measured feature is a legitimate answer, and its list only exists once the recipe's payload has landed.
    - **The scope is shared or small.** One bar row holds roughly three control cells. TTTM and PM 플래닝 hold RECIPE + **수집 기간** (`ebeam/ScopeWindow.vue`, 1주/2주/3주/4주 as `SkChip`s, default 2주 — it decides how many weeks of runs the server gathers, so it *selects the measurement data* the same way the first two do, and it re-fetches the recipe picker as well as the check; 2026-08-25). A scope needing more cells than that wants a rail.
    - **Who is compared is its own bar (2026-08-27).** 장비·모델 그룹 left 비교 대상 for a **장비 모델 그룹** bar (`ebeam/ToolGroupBar.vue`) directly under it: the roster arrives on the recipe's payload, so which tools to compare is decided *among* that answer — the second step, not a third cell of the first. Same model-group dropdowns (terracotta when any tool is picked), plus bar-level 전체 선택 / 전체 해제. The selection has **no lower bound in the control**: 해제 on a group empties it even when that leaves one or zero tools, and the results area answers with an `AppEmptyState` ("2대 이상 고르세요") — the old bar silently refused any change below two tools, which on a one-model fab meant 해제 did nothing at all. Stored as `null` = all, `[]` = none.
    - **What acts on the selected data goes in a second bar (2026-08-25).** The procedure is tools + recipe → the recipe's measurement rows → the parameters those rows carry, so the parameter is not a third cell of the first choice; it is a choice made *from* the answer. It is a **multi-select** (2026-08-27): the N배화 group is "tools that match on each picked parameter", and the 장비 그룹 배치도 (`tttm/FleetMap.vue`) is a **PCA** over the same picks (`utils/parameterPca.ts` on the payload's `parameter_profile`; every parameter when none is picked) — the header states PC1/PC2 explained variance and the caption names each axis's loadings, the way the MDS map states its stress. It sits in a **분석 조건** bar (`EbeamAnalysisBar`) directly under 비교 대상, with the page-specific judging control (TTTM's tolerance knob) in a divided trailing cell — same stage, different question. The trailing cell is optional and PM 플래닝 no longer fills it (see the subject-bar bullet); an empty divided column reads as a control that went missing. The second bar is always mounted and its controls are **disabled** until a recipe is picked (and while its answer is unavailable), each with a caption naming the missing step — hidden, the layout jumped when it appeared and the procedure did not read as two steps until the first was taken.
    - **The subject is picked on the map, not in a bar (2026-09-18).** 튜닝할 장비 was a full-width bar summoned by a PM 튜닝 chip (2026-08-27 → 2026-09-01); both are gone. Clicking a dot on 장비 그룹 배치도 selects that tool and the 튜닝 목표 card beside the map (`ebeam/pmPlanning/Targets.vue`) shows, per parameter, how far it must move to reach the group centre; clicking it again or empty space deselects. There is no default pick — an unselected card says to click a tool. The tolerance slider (`ebeam/ToleranceKnob.vue`) lives inside the map card so the drag and the recolouring are one glance; it falls back to 분석 조건's trailing cell only when the 배치도 panel is off. PARAMETER is a row of toggle chips (전체 = empty selection), not a dropdown, and 데이터 요청 sits directly under 수집 기간. Lab-page charts draw **no dashed lines** — BM/PM markers are told apart by colour and width — and the trend is a scatter, because a dozen tools' lines cannot be traced. Captions are one plain sentence; the 자세히 fold is not used.
    - **The model-gated strip (2026-08-25).** H/W 관리 puts its decision in a **장비 선택** strip in the same position and gates on the **model**: there is no "all models" chip, no tool chips show, and the results carry an `AppEmptyState` until at least one model is picked — so the reader always knows which models the page is about (user decision). Model chips **toggle**, so several models can be picked together and their tools share one strip (2026-08-25). Within the picked models the first tool auto-selects; that default is honest because the model has been stated and a page showing one tool's hardware state folds nothing. Where the default would be a fold nobody chose (TTTM's fleet-wide recipe fold), the page gates on the choice itself.
    - Width is still granted, but on the results' own terms: both pages run four rows of paired cards, and 1280px pushes the pairwise matrix off a 1080px screen.
  - TTTM runs its results column at `gap-3` (12px) rather than the standard 24px rhythm below, per the `TTTM 개선안` 3a design: four rows of paired cards inside a `1fr` column read as one argument, and 24px between them pushes the pairwise matrix off a 1080px screen. The 24px rhythm remains the default everywhere else.
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
No photography, no illustration — this is a data tool. One icon set: **Lucide** (`@iconify-json/lucide`), used as `icon="i-lucide-<name>"`. Canonical assignments: `search` (inputs), `rotate-ccw` (reset), `download` (Excel export), `info`, `settings`, `loader-circle` + `animate-spin` (loading), `star`/`star-off` (favorites), `arrow-up-narrow-wide`/`arrow-down-wide-narrow`/`arrow-up-down` (sort), `construction` (under construction). `@iconify-json/simple-icons` exists as a dependency but is reserved for brand logos.

## Components

### Selection Primitives

> The single source of truth for the *Selection & Button System (Bolder)* v1.0. When a control has a selected state, use `sk-nav-pill` or `sk-chip` — not `UButton`.

**`sk-nav-pill`** (`<SkNavPill>`) — NAVIGATE. Active fill `--sk-ink`, text `--sk-ink-fg`, radius `--sk-r-nav` (10px). Used for product tabs, feature tabs, section toggles (BSM/FDC/BM·PM), sub-tabs, sidebar items. `aria-pressed` mandatory.

**`sk-chip`** (`<SkChip>`) — FILTER. Active fill `--sk-brand` (or `tone="ink"`), text `--sk-brand-fg`, radius `--sk-r-chip` (8px). Used for Fab, Category, Lot, Tech, Status chips.

**`sk-btn`** — ACTION. Inside the app this is **`UButton`, not a component of its own**: `<SkBtn>` was specified in v1.0 and never built, because the token bridge already makes `<UButton color="primary">` an ink fill at `--sk-r-nav`. The `kind="brand"` terracotta button was never used and is withdrawn — terracotta stays a filter color. Outside the app, the `.sk-btn` recipe in the starter section is the same button in plain CSS.

Decision flow: changes route/view → `sk-nav-pill` · narrows data on the same page → `sk-chip` · mutates data or triggers an action → `UButton` (§Buttons).

### Buttons (NuxtUI)

**`button-primary`** — `UButton color="primary"` for the one action a panel exists for (submit, 데이터 요청). Ink fill through the bridge.

**`button-default`** — `UButton color="neutral"` in `outline` or `subtle` for plain actions with no selected state (close modal, reset, export). These two variants are what the app overwhelmingly uses; `solid` neutral is rare.

**`button-ghost`** — `UButton color="neutral" variant="ghost"` for incidental actions (info, settings, dark-mode toggle).

**`button-destructive`** — none exist yet; if one appears: `text-rose-600` text + explicit confirm dialog.

All buttons use Lucide icons; icon-only buttons require `aria-label`; Korean labels prefer verb forms (`Excel 다운로드`, not `다운로드`); disabled buttons also set `cursor-not-allowed`.

**Table downloads are `.xlsx`, always.** Every table export in the app goes through `utils/xlsx.ts` (`downloadTable` for one sheet, `downloadWorkbook` for several) and carries the word `Excel` in its label (`Excel`, `Excel 다운로드`, `Excel (전체)`; an all-English menu may read `Download All (Excel)`). CSV was retired on 2026-09-02: it is a typeless format, so it needed a UTF-8 BOM to survive Korean headers, a formula-injection guard on every cell, and it turned `0012` into `12`. Do not add a CSV button back — a button whose label and file extension disagree is exactly the drift this unification removed. The clipboard copy stays TSV (`copyTableToClipboard`), and that one still needs `guardFormulaCell`.

### Cards & Containers

**`card`** — Plain NuxtUI `UCard` for ordinary content groups. Header pattern: `flex items-center justify-between gap-3` with an `text-lg font-semibold` title and a `UBadge color="neutral" variant="subtle"` count.

**`dashboard-surface`** — Tables and stat cards that should read as dashboard surfaces. `--sk-surface` background, 1px `--sk-border`, the paper shadow (see Elevation). Radius `--sk-r-card`.

**`meta-bar`** (`EbeamMetaBar`) — The **first component in every page body**; a one-line page header replacing the old `FeatureHeader` + toggle row + stat strip. Left cluster: mono eyebrow (`CD-SEM · R3`) + **fixed `<h1>` title** → 1px vertical divider → `#toggle` slot. Right cluster: inline stats + freshness badge (`EbeamDataFreshness`) + `#actions` slot. Below the bar: demoted context line in `text-xs text-(--sk-ink-muted)`. Core rule: **the title never changes when a tab/view changes** — scope drops to the eyebrow. Toggles are always BLACK-family segmented controls; terracotta chips never appear in a toggle. `stats: MetaBarStat[]` cells (`{ key, value, label, tone?, active? }`) separate with `--sk-border-soft`; `tone` maps to the semantic families; `interactiveStats` turns cells into a `role="radiogroup"` filter with a tone-soft active tint. Rich KPIs (period/device-dependent, or grouped like Align/Meas) stay as cards below the bar, never flattened inline.

**`filter-bar` / `stat-bar`** — Card-shaped (`dashboard-surface`) with `flex flex-wrap gap-3` inside. Multi-metric rows separate cells with `divide-x divide-(--sk-border)` (divide, not border, to avoid doubled edges). Interactive stat cells show `--sk-accent-soft` on hover.

### Navigation

**`top-nav`** (`nav/AppHeader.vue`) — Sticky translucent header: `bg-(--sk-nav-bg)` + `backdrop-blur-md`, bottom border `--sk-nav-border`, `shadow-none`. Left to right: logo, `feature-tabs`, then the two `header-menu`s. Active tab = `--sk-ink` fill + `.sk-nav-accent` crimson underline.

**`header-menu`** (`nav/LabMenu.vue`, `nav/AccountMenu.vue`, rows in `nav/HeaderMenuItem.vue`) — The header's right side is **two labelled menus, never a row of icons**. 실험실 holds the tools that answer to no feature tab; 계정 holds the caller and the pages about their own use. Both draw their rows from the one `utils/headerNav` array the feature tabs also read, so a page cannot be reachable from the header while rendering no tabs.

Trigger states: 실험실 is a `sk-nav-pill` and goes `--sk-ink` fill + `.sk-nav-accent` when the current page is inside it — the header still answers *"where am I"* unopened. 계정 keeps the crimson underline but **never takes the ink fill**, because the avatar inside it is already an ink square and a filled pill around a filled square reads as two nested buttons. Panels are `align: 'end'` (they are wider than their triggers and sit at the right edge) and keep NuxtUI's popover radius and shadow, per §Shapes.

Row anatomy: `--sk-r-chip` radius, icon at `--sk-ink-muted`, `.sk-title` label, optional `.sk-meta` description. The **active** row takes the crimson left edge (`inset 2px 0 0 var(--sk-accent)`) on `--sk-muted-surface` — the FAB sidebar's indicator without its paper shadow, since a row inside an already-elevated panel must not cast a second one. A hairline (`--sk-border-soft`) marks a change of *kind* inside one menu, not merely a gap: 채팅 is conversational where the rows above it are things you look up. The one fab-scoped row states its destination inline as a mono `CD-SEM · R3` chip, because that destination moves under the user.

**`feature-tabs`** (`nav/FeatureTabs.vue`) — 4–7 feature tabs per tool type, rendered inside the header and scrolling horizontally rather than wrapping; `aria-disabled` when inactive.

**`fab-sidebar`** (`nav/FabSidebar.vue`) — Collapsible rail (`w-52` ↔ `w-16`) holding **both** pickers: the 장비모델 list on top (CD-SEM / HV-SEM / VeritySEM / Provision, each with a tool count; two-letter codes at rail width) and the fab list with favorite stars under it. The tool-type pill row that used to sit above the feature tabs (`nav/ToolTypeTabs.vue`) was folded into this rail. The active row takes `.sk-fab-active` (2px crimson left edge, readable even at icon-rail width).

**Row divider rule (retired)** — a full-bleed `--sk-border-soft` hairline used to separate the tool-type pill row from the feature-tab row. Both were pills and read as peers, so the line was what kept *"which tool"* apart from *"how I'm viewing it"*. Moving the tool types into the sidebar put that boundary on a different axis, and the row and its divider went with it. The principle survives: two pill groups that answer different questions never sit on one line without a separator.

### Tables

**`data-table`** (UTable) — Header `sticky top-0 bg-(--sk-surface)`. Sort via the three Lucide arrow icons + `aria-sort`. Number columns `font-mono tabular-nums text-right`; ID columns `font-mono`; value cells `text-(--sk-ink)` — never muted. Hover `hover:bg-zinc-50 dark:hover:bg-zinc-800/50`. Empty state: `text-zinc-500` message in the `:empty` slot. Pagination in the card footer: `이전 / 페이지 N/M / 다음`.

### Inputs & Forms

**`text-input`** — `<UInput icon="i-lucide-search" placeholder="검색" />`. Border and radius come from the theme (`--sk-border`, `--sk-r-nav`) via the NuxtUI bridge — do not restate them at the call site. Focus uses the `--sk-focus-ring` treatment.

**`select`** — `<USelect>` / `<USelectMenu>`, same themed border and radius as the input. Option labels Korean, values English. Multi-select filters (Category, Lot, Tech) use the `sk-chip` pattern instead — see `pages/ebeam/cd-sem/device-statistics/index.vue`.

### Tags / Badges

**`badge-count`** — `<UBadge color="neutral" variant="subtle">` for row counts and filter counts.

**`notice-new-badge`** (`<NoticeNewBadge>`) — the 16px `N` marking an unread 공지사항: on the App 정보 trigger, on its menu row, and on each unread notice in the `/notices` timeline, where reading is explicit (모두 읽음 처리) rather than marked on open. Solid `--sk-brand` fill with `--sk-brand-fg` text at `--sk-r-sidebar` — terracotta because "new" is not a verdict and crimson is trim only. The letter is `aria-hidden` beside an `sr-only` "새 공지", so it never signals by colour alone.

**`pill-on` / `pill-off`** — `.sk-pill-on` / `.sk-pill-off` status pills: 12px, weight 600, 9999px radius (the sanctioned legacy exception), `--sk-on-*` / `--sk-off-*` pairs. Always carry a text label — never color alone.

**`category-tag`** — a tag naming which *kind* of thing a row is, where the kinds are peers and none is a status (DRAM/NAND on a rule row; `ebeam/rules/MemoryChip.vue` is the reference). The reflex is one hue per value, and that is what pulls `sky-*`/`amber-*`/`violet-*` into a warm page. Encode it as **tint vs neutral** instead: one value takes `--sk-brand-soft` + `--sk-brand-ink`, the rest stay `--sk-muted-surface` + `--sk-border` + `--sk-ink-muted`. Both at the same size and weight, so the tint distinguishes without ranking.

This is forced, not preferred. The semantic families (`--sk-ok/warn/bad`) are excluded because peer categories carry no verdict, and crimson is trim-only — which leaves terracotta as the system's only non-semantic tint. So a **binary** resolves as tinted-vs-plain, and a category with three or more values does not get a colour encoding at all: use the label text, and if the values must be told apart at a glance, they belong in their own column, not in a chip.

## Do's and Don'ts

### Do
- Route every color through `--sk-*` variables (`bg-(--sk-surface)`, `text-(--sk-ink)`). It's the simplest way to never forget a dark variant.
- Apply the litmus test before styling any selected state: view changes → BLACK (`sk-nav-pill`), data narrows → TERRACOTTA (`sk-chip`).
- Give data values `--sk-ink` and labels `--sk-ink-muted`, everywhere, especially in dark mode.
- Keep tables quiet: mono tabular numerals, 1px borders, hover highlight, nothing else.
- Keep content at `max-w-7xl` (1280px); use the 1440px dense exception only for agreed list-plus-detail pages.
- Use `aria-pressed` on every toggle, `aria-disabled` + `disabled` together, `aria-label` on icon-only buttons, `aria-sort` on sorted columns.
- Follow Korean voice endings: page titles noun-form (`디바이스 통계`), buttons verb-form (`Excel 다운로드`), empty states `~없습니다.`, errors `~못했습니다.`, help text `~입니다/합니다.` Tokens and keys stay English (`prod_catg_cd`).

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
  top-level panel, pass `dashboard-surface rounded-(--sk-r-card)` to it instead.
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
| `lg` | 1024–1280px | Filter bars wrap (`flex-wrap`); feature tabs scroll horizontally |
| below `lg` | < 1024px | Not a primary target (internal FHD tool); FAB sidebar collapses to icon rail, tables scroll horizontally inside their cards |

### Touch & Pointer Targets
- Buttons are 40px tall (`py-2.5` + label); pills and chips ≥ 32px with generous horizontal padding — this is a mouse-first internal tool.
- Entire table rows are clickable where a detail view exists (e.g. H/W management list rail).

### Collapsing Strategy
- The FAB sidebar narrows to an icon rail; the `.sk-fab-active` left edge stays legible at rail width.
- Sidebar pages guard against horizontal scroll with `flex` + `min-w-0` on the main pane.
- Tables never wrap numeric content; they scroll horizontally within their card.
- Feature tabs scroll horizontally rather than wrapping to a second row.

## Iteration Guide

1. Focus on ONE component at a time; reference it by its name here (`meta-bar`, `sk-chip`, `dashboard-surface`).
2. Never inline hex — every color routes through a `--sk-*` token. If a needed color has no token, add the token to this document first, then to `main.css`.
   Exception: ECharts-theme palette values may be used unchanged only for corresponding SVG/canvas chart marks and matching DOM data marks, so one data series keeps one color across its representations.
3. New selected states must pass the BLACK/TERRACOTTA litmus test before any styling begins.
4. New radii must come from the 4-step scale; new text sizes from the Tailwind scale with the 12px floor.
5. When in doubt about emphasis: one weight step up (400→500→600→700) before any color change.
6. Paper + walnut + ink + terracotta + crimson-trim is the complete palette. Don't introduce a new hue; status colors are already provided (`--sk-ok/bad/warn`).
7. This document changes first; `main.css` and `app.config.ts` are updated in the same change. A token added, removed or retoned also changes the copy-paste block in §Building a Page That Merges Cleanly — teammates build from that block, not from `main.css`.

## Known Gaps

- **Call-site drift to sweep (doc + theme are correct):** some pages still carry chrome classes that predate the NuxtUI bridge — `rounded-2xl` on cards (which *beats* the themed 14px), `border-zinc-*` toolbar dividers, `bg-zinc-*` table headers, `text-zinc-900` card titles, and raw `rose`/`amber`/`emerald` where the `--sk-ok/warn/bad` families belong. These are **deletions**, not replacements: the correct value already sits underneath. `장비 리스트` / `스토리지` (`ToolInventoryView.vue`, `StorageView.vue`) have been **swept and now read as the reference case** — data tables at `text-xs` full-`--sk-ink` values, `text-[11px]` muted headers, sanctioned zinc only in the row hover.
- **Font-tier + dim-colour sweep (done, 2026-07-15):** non-sanctioned type tiers (`text-[9px]`, `text-[9.5px]`, `text-[10.5px]`, `text-[11.5px]`) were normalised to the sanctioned 11px/12px, and cool `text-zinc-400/500` supporting text was replaced with the warmer, higher-contrast `--sk-ink-muted`. Going forward, prefer the **semantic type classes** (§Typography → Semantic type classes) over re-introducing ad-hoc `text-[…]` sizes; adopting them across the remaining components is the open follow-up.
- **`.sk-eyebrow` misused as a table header.** The eyebrow is a *meta-bar kicker*; a `<th>` is a `.sk-label`. Rendering column headers as 10px mono UPPERCASE at +0.06em in ink-muted gives the densest part of a page the weakest type in the system. 계측 룰 (`ebeam/rules/*`) was swept on 2026-08-05 and is the reference case; grep for `sk-eyebrow` inside a `<th>` before adding a table.
- **`chipClass(active)` fills with crimson.** `utils/chipClass.ts` paints the active row-card chip `bg-(--sk-accent)` with `text-white`, and rests on `bg-white` / `ring-zinc-*` — a crimson *fill* on a filter, against the two hardest rules in this document. It reaches six files (디바이스 통계, 디바이스 분석, `LotDetailModal`, `AnalyticsDevicePicker`, two AFM detail components). The fix is one function: active → `--sk-brand` / `--sk-brand-fg`, rest → `--sk-surface` / `--sk-border` / `--sk-ink-muted`, and `CHIP_BASE`'s `rounded-lg` → `--sk-r-chip`. Do not copy this chip; copy `sk-chip`.
- **`fab-sidebar` is hand-rolled zinc.** `nav/FabSidebar.vue` draws its active row as `bg-zinc-900` / `dark:bg-zinc-100` rather than `--sk-ink`, its dividers as `border-zinc-200/70`, and its corners as `rounded-2xl` / `rounded-lg`. It looks right only because zinc-900 sits close to ink; it does not follow a retone.
- **`AppLoadingState`'s block variant is `rounded-2xl`** (16px through NuxtUI's ramp) where a card is `--sk-r-card` (14px), so a loading card and the card that replaces it differ by 2px of corner.
- Equipment status sub-tabs (`EquipmentStatusSubTabs.vue`) are a hand-rolled white/zinc segmented control; they are a NAVIGATE control and must become `<SkNavPill>` (ink fill).
- Several pages are still English in the UI copy (placeholders, `Reset`, empty states, error lines) against the Korean-voice rule.
- The `--sk-accent-soft` hover on interactive stat cells is specified but not yet applied everywhere.
- Destructive actions have no component yet; the `text-rose-600` + confirm-dialog rule is untested.
- `prefers-reduced-motion` is not handled; only `animate-spin` and `sk-pulse` would be affected.
- Skeleton/shimmer loading states are deliberately not adopted; if load times grow, that decision should be revisited here first.
- `--sk-accent-border` is now used in exactly one place: the emphasised cap cell in 계측 룰 (`rules/CapCell.vue`), paired with `--sk-accent-tint` as a fill. That pairing is the sanctioned way to mark an emphasised *data* cell — crimson stays a border and a wash, and the value itself keeps `--sk-ink`. The old crimson-bordered card treatment remains retired in favour of the paper shadow. `--sk-accent-tint` is also the live-alarm new-arrival highlight, on both `AlarmRow.vue` and `MeasGroup.vue`'s group header.
- The zinc scale remains in `main.css` for Tailwind compatibility; it is no longer NuxtUI's neutral (that is `paper` now), and its only sanctioned direct uses are table hovers and empty-state text.

## Changelog

- 2026-04-26: Initial version — tokens extracted from `main.css`, `app.config.ts`, and components; preview HTML added.
- 2026-05-12: *Selection & Button System (Bolder)* v1.0: BLACK = nav / TERRACOTTA = filter semantics, 4-step radius scale, `SkNavPill` / `SkChip` / `SkBtn` primitives, `--sk-ink*` / `--sk-brand*` / `--sk-r-*` tokens.
- 2026-05-16: Full-bleed `--sk-border-soft` row divider between tool row and feature row.
- 2026-05-23: Layout widths codified (FHD target, 1280px cap); meta bar (`EbeamMetaBar`) pattern added and adopted on five views; H/W management rebuilt as Dense 2-column with the 1440px exception.
- 2026-05-24: Ink text hierarchy codified — data values get `--sk-ink`, muted ink for labels only.
- 2026-07-13: Full polish — translated to English, promoted to source of truth, token values synced to the Paper/Walnut theme, missing tokens documented, focus ring + type refinements added.
- 2026-07-13: **Reformatted to the standard design-system document format** (Overview / Colors / Typography / Layout / Elevation & Depth / Shapes / Components / Do's and Don'ts / Responsive Behavior / Iteration Guide / Known Gaps). Voice & tone and accessibility rules folded into Do's and Don'ts; code-drift items moved to Known Gaps.
- 2026-07-13: **NuxtUI token bridge** — `app.config.ts` now genuinely implements the mapping this document always claimed it did. NuxtUI's `primary`/`neutral` point at a new warm `paper` ramp instead of cool zinc, and the `--ui-*` semantic tokens are bridged to `--sk-*` (unlayered, `:root`-only, so dark mode follows the `--sk-*` inversion automatically). NuxtUI components now inherit the design system with no call-site classes. Resolved three doc↔code conflicts: **(1)** the §Shapes-vs-§Inputs radius contradiction — components are pinned to the 6/8/10/14 scale by slot in `app.config.ts`, since NuxtUI's geometric `--ui-radius` ramp cannot express a non-geometric scale; **(2)** the 12px floor, which the code broke 311× — two sub-12px tiers (10px mono eyebrow, 11px micro-label) are now sanctioned for *labels only*, with data values still hard-floored at 12px; **(3)** the cool-zinc neutral underlying every NuxtUI component on a warm page. Also landed the previously-missing `--sk-focus-ring` and removed the duplicate `--sk-ink` definition.
- 2026-07-26: **Mag/Pixel 가이드 aligned to the system** (design option 2a). The page adopts `meta-bar` as its first body component, joins the 1440px dense exception with a 392px sticky input-and-answer rail, and moves its cards to `dashboard-surface` + `--sk-r-card` (they were `rounded-lg` + `bg-white dark:bg-zinc-950`, i.e. off the radius scale and outside the bridge). Series and 여유 마진 became `SkChip` by the litmus test — they narrow data, they don't change the view. Raw `emerald`/`amber`/`red`/`indigo` were replaced by the `--sk-ok/warn/bad` families and terracotta. Added the **Dark Field** token family (§Colors) for simulated SEM imagery, the one sanctioned non-inverting set in the system.
- 2026-08-05: **계측 룰 (measurement-rules) readability sweep.** Column headers moved from `.sk-eyebrow` to `.sk-label`; family group headers became a `--sk-muted-surface` band at `.sk-value` weight instead of a 10px kicker. Emphasised caps stopped rendering `text-(--sk-accent)` on `--sk-accent-tint` — crimson is now trim only (border + wash) and the digit sits at full `--sk-ink`, per §Colors. `0` (측정 금지) lifted from ink-subtle to ink-muted on a muted fill, since a cap is a data value in every state. Raw `sky-*`/`amber-*` DRAM/NAND pills and the `rose-*` violation badge moved into the palette — the memory chip as **tint vs neutral** (below), the badge onto the `--sk-bad` family. `text-[12.5px]`/`text-[10px]` normalised to the sanctioned tiers, `rounded-2xl`/`rounded-md` to `--sk-r-card`/`--sk-r-chip`, and the accent-tint row hover to the documented `--sk-accent-soft`. Column widths were pinned with a trailing spacer column so the caps sit beside their row label rather than ~600px away.
- 2026-08-15: **Top nav 재구성** (design option 2a). The header's eight unlabelled right-side icons became two labelled menus, `header-menu` above. The icons were a second hierarchy on the feature tabs' own line with nothing to distinguish a fab-scoped feature from a global page, they had to be hovered to be read, and two of them collided with icons the tabs already used (`bar-chart-3` for both 사용 통계 and 디바이스 통계; a magnifier for both Recipe 검색 and Mag/Pixel). 사용 통계 moved to `activity` to break the first collision; the second stopped mattering once every header item draws its label. `IdentityPill` became the 계정 trigger rather than a ninth icon, and now renders in every identity state — it used to hide itself when it had no declaration to release, which would have stranded the three pages it now carries.
- 2026-08-18: **The two lab pages moved from a control rail to a 비교 대상 scope bar**, and §Layout gained the scope-bar rule beside the rail rule. 장비간 스큐 관리 and PM 플래닝 put 장비·모델 그룹 + RECIPE + PARAMETER in one full-width bar above the results, with the page-specific control (tolerance knob / 튜닝할 장비) in a divided trailing cell; `tttm/ScopePanel.vue` is gone and `ebeam/ScopeBar.vue` is shared by both. The results are now **gated** on the recipe and carry an explicit `AppEmptyState` until one is picked — the server does answer without a recipe, but that answer is a fleet-wide fold of every measured recipe and it rendered identically to a deliberately scoped one, so the page was quoting a comparison nobody chose. The parameter stays optional: its list comes from recipe-open over FTP, and a required field behind a failable request is a page that can lock shut. PM 플래닝 also gained the tool selector it previously could only read, on the same reasoning that made recipe and parameter editable there. Both pages keep 1440px, now justified by their four rows of paired result cards rather than by a list-plus-detail split.
- 2026-08-25: **The scope bar split in two along the data flow.** 비교 대상 keeps 장비·모델 그룹 + RECIPE; PARAMETER moved to a new 분석 조건 bar (`ebeam/AnalysisBar.vue`, with `ebeam/ScopeParameter.vue`) beneath it, together with the page-specific trailing cell that used to share the first bar. The parameter list is no longer fetched from recipe-open over FTP: it rides on the check payload itself (`parameters`), read from the same measurement rows the skew is, so the picker offers exactly what the filter can match and the error caption for a failed lookup is gone. §Layout's scope-bar rule gained the second-bar bullet.
- 2026-08-25: **비교 대상 gained a 수집 기간 cell** (`ebeam/ScopeWindow.vue`): `SkChip`s — 1주 / 2주 / 3주 / 4주, default 2주 (user decision, 2026-08-26; it shipped as three chips defaulting to 3주) — that set `window_weeks` on the check, the recipe picker and PM 플래닝's fleet fetch alike, from the one persisted scope both lab pages share. The meta bar's cadence readout (`N주 윈도우`) is now read off the payload's echo instead of a hardcoded "1주 윈도우" that the server never honoured (it gathered a fixed 10 runs per tool over 60 days). §Layout's scope-bar rule names the cell.
- 2026-08-25: **H/W 관리 moved its 320px tool rail to a 장비 선택 strip above the results.** The page has one required decision — the tool — and every card and chart below is computed for it, so it now reads first, and the detail (FDC's per-key grid, the MDC/SCE comparison charts) takes the full width. The strip is two chip rows by the litmus test: model chips narrow the roster (terracotta `SkChip`, with counts that respect the other controls), and the tool row picks one subject among peers (`tone="ink"` `SkChip`, the same choice `skewvoir/timeseries/ParamCoverageList.vue` makes) — different roles, so the two fills do not mix. Availability chips and search sit at the trailing edge; the vendor / model / fab / IP / version line that each rail row carried now describes the selected tool under the chips. The tool row caps at about four rows and scrolls, because a multi-fab union can reach 60+ tools. Same day, on the user's call, the strip became **gated on the model**: the All Models chip went, tool chips appear only for the picked model, and the results show an `AppEmptyState` until then — the point being that the reader is never unsure which model they are working on.
- 2026-08-27: **Three bars on the lab pages, and a PCA 배치도.** 장비·모델 그룹 moved out of 비교 대상 into its own **장비 모델 그룹** bar (`ebeam/ToolGroupBar.vue`; 비교 대상 now holds RECIPE + 수집 기간 only), with the below-two-tools refusal removed — it was why 해제 could not empty a group — and a `"2대 이상"` empty state in its place. PARAMETER became a multi-select: the check takes a repeated `parameter` key, the N배화 group is the intersection over the picks, and 장비 그룹 배치도 is placed by PCA over the payload's new tool × parameter `parameter_profile` (`utils/parameterPca.ts`, CD-relative columns, Chebyshev red rule, explained variance in the header, loadings in the caption), falling back to the MDS map only when no usable column exists. §Layout's scope-bar rule gained the third-bar bullet and the multi-select note.
- 2026-08-27: **PM 플래닝's 튜닝할 장비 became the page's first bar.** It had been the divided trailing cell of 분석 조건 — a 264px column at the far right of the third bar, under a title that did not name it — while the three bars above it hold settings shared with TTTM. The page reports on one tool, so that tool now reads before the data it is judged against: its own full-width bar under the meta bar, the picked id at `.sk-card-id` size, and the Up gate / 1차 그룹 / last-PM facts beside the trigger instead of in a caption under it. It no longer takes the 분석 조건 lock (the PM roster is a separate request from the recipe's payload), and `ebeam/AnalysisBar.vue`'s trailing cell became optional so the bar does not render an empty divided column. §Layout's scope-bar rule gained the subject-bar bullet.
- 2026-09-01: **튜닝할 장비 moved from above 분석 조건 to directly below it.** The two lab pages merged into one 실험실 route whose 보기 chips choose the panels, which made this bar conditional rather than permanent — the **PM 튜닝 chip, inside 분석 조건, is what summons it**. It had kept its 2026-08-28 slot above 분석 조건, so turning the chip on made a bar appear *above* the control just clicked, which is the one place the reader was not looking; chip and bar are now adjacent. Nothing about the earlier reasoning is given up: 비교 대상 and 장비 모델 그룹 are still above it, so the tool is still picked out of an already-defined set. Same change, the **튜닝 목표 card names its subject** — the picked `eqp_id` at `.sk-card-id` with `eqp_model_cd` beside it in the picker trigger's own identity styling, drawn only once a tool is picked, because every row of that table is a distance measured for one tool the card had never named. §Layout's subject-bar bullet rewritten to the new rule.
- 2026-09-18: **TTTM renovated: PM 튜닝 chip and 튜닝할 장비 bar removed; tuning is a map click.** The Up gate card and the pm_planning request left the page with them (`backend/ebeam/pm_planning` and the `/pm-planning` redirect are untouched). The residual card reads the selected 수집 기간 (median of each tool's daily residuals, re-based on the visible tools) instead of "오늘", parameters became chips, the tolerance slider moved into the map card, the trend became a scatter, and dashed lines were dropped.
- 2026-09-19: **Made shareable with teammates.** Added §Building a Page That Merges Cleanly: a copy-paste token block generated from `main.css` (seven tokens — the `-soft` / `-border` status members and `--sk-chip-*` — had no value anywhere in this document, so the palette could not be reproduced from it), plain-CSS recipes for the card, nav pill, chip, button, input, table and status tag, a page skeleton, and a pre-merge checklist. Corrected references to files that no longer exist (`ebeam/TttmView.vue`, `ebeam/PmPlanningView.vue`, `nav/ToolTypeTabs.vue`, `device-statistics.vue`, both preview HTML files) and the navigation description they belonged to — tool types live in the FAB sidebar now, and the row-divider rule is retired. `<SkBtn>` is recorded as never built: the action button is `UButton color="primary"` through the bridge. The focus-ring bullet moved out of §Dark Field, where it had been stranded. §Known Gaps gained three code-side findings from the same audit (`chipClass`'s crimson fill, the hand-rolled FAB sidebar, `AppLoadingState`'s radius). Changelog re-sorted chronologically.
