export default defineAppConfig({
  ui: {
    // 'paper' is the warm neutral ramp defined in assets/css/main.css (@theme).
    // NuxtUI's neutral drives text, borders, backgrounds and disabled states on
    // every component, so this is what keeps them in the paper/walnut material
    // instead of cool zinc. The semantic --ui-* -> --sk-* bridge in main.css
    // pins the exact tones on top of this ramp.
    colors: {
      primary: 'paper',
      neutral: 'paper'
    },
    header: {
      slots: {
        root: 'h-(--ui-header-height) sticky top-0 z-50 border-b-(--sk-nav-border) bg-(--sk-nav-bg) backdrop-blur-md shadow-none'
      }
    },

    // Radius — pin NuxtUI's components to the 4-step scale (6/8/10/14).
    //
    // NuxtUI derives every rounded-* utility from a single --ui-radius base by
    // fixed multipliers (sm 1x, md 1.5x, lg 2x, xl 3x, 2xl 4x), which is a
    // geometric ramp; our scale isn't one, so no base value can produce it.
    // Rather than bend the scale to the ramp, we bypass the utilities on the
    // components themselves. These classes are tailwind-merged over the default
    // theme, so they replace its rounded-* and leave the rest of each slot
    // untouched. Modal/Popover/dropdown radii are intentionally left on the
    // NuxtUI defaults, per the design system.
    card: {
      slots: { root: 'rounded-[var(--sk-r-card)]' }
    },
    button: {
      slots: { base: 'rounded-[var(--sk-r-nav)]' }
    },
    input: {
      slots: { base: 'rounded-[var(--sk-r-nav)]' }
    },
    select: {
      slots: { base: 'rounded-[var(--sk-r-nav)]' }
    },
    textarea: {
      slots: { base: 'rounded-[var(--sk-r-nav)]' }
    },
    badge: {
      slots: { base: 'rounded-[var(--sk-r-chip)]' }
    },

    // Stacking — NuxtUI v4 ships its slideover with NO z-index at all (see
    // .nuxt/ui/slideover.ts: `fixed inset-0` and `fixed inset-y-0 right-0`),
    // so it resolves to `z-index: auto` and loses to every z-50 surface this
    // app puts on screen: the sticky header, and the full-screen SEM image
    // viewer/lightbox. A drawer opened from inside the viewer therefore slid
    // in BEHIND it, unreadable. Raised here rather than at the five call sites
    // because it is one property of what a slideover IS, not of any one drawer.
    slideover: {
      slots: {
        overlay: 'z-[60]',
        content: 'z-[60]'
      }
    }
  }
})
