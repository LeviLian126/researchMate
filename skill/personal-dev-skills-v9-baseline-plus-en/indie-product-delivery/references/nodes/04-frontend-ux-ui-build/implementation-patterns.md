# Implementation Patterns

> **Goal:** Provide directly usable code patterns for stack defaults, animation, fonts, icons,
> dependencies, RSC safety, layout mechanics, z-index scale, and overscroll containment.
>
> **Owns:** concrete code patterns and import paths
>
> **Does NOT own:** architecture decisions (`component-responsive-accessible-build.md`), direction decisions (`visual-direction-and-design-system.md`)

This is a reference for writing frontend code. Other files in this node reference these patterns rather
than duplicating them.

## Stack Defaults

Unless the design read picks a real design system, these are the defaults:

- **Framework:** React or Next.js. Default to Server Components (RSC).
- **Styling:** Tailwind v4 (default). Tailwind v3 only if the existing project demands it.
  - For v4: do NOT use `tailwindcss` plugin in `postcss.config.js`. Use `@tailwindcss/postcss` or the
    Vite plugin.
- **Animation:** Motion (the library formerly known as Framer Motion). Import from `motion/react`:
  ```js
  import { motion } from "motion/react";
  ```
  The `framer-motion` package still works as a legacy alias - prefer `motion/react` in new code.

## Animation Patterns

### Continuous values: use Motion, not useState

Never use `useState` to track continuous values driven by user input (mouse position, scroll progress,
pointer physics, magnetic hover). `useState` re-renders the React tree on every change and collapses
on mobile.

```js
// Correct: Motion values for continuous tracking
import { useMotionValue, useTransform, useScroll } from "motion/react";

const x = useMotionValue(0);
const opacity = useTransform(x, [0, 100], [1, 0]);
const { scrollYProgress } = useScroll();
```

### GPU-friendly properties only

Animate only `transform` and `opacity`. Never animate `top`, `left`, `width`, `height`, `margin`, or
`padding` - these trigger layout recalculation and cause jank.

```css
/* Correct */
transition: transform 200ms ease, opacity 200ms ease;
transform: translateY(0);

/* Wrong */
transition: top 200ms ease, height 200ms ease;
```

### Scroll listeners: IntersectionObserver or CSS, not window.addEventListener

```js
// Correct: IntersectionObserver
const observer = new IntersectionObserver((entries) => {
  entries.forEach((entry) => {
    if (entry.isIntersecting) {
      entry.target.classList.add("visible");
    }
  });
}, { threshold: 0.1 });

// Correct: CSS scroll-driven animations (modern browsers)
@keyframes reveal {
  from { opacity: 0; transform: translateY(12px); }
  to { opacity: 1; transform: translateY(0); }
}
animation: reveal linear;
animation-timeline: view();
animation-range: entry 0% entry 100%;

// Wrong: never do this
window.addEventListener("scroll", handleScroll); // causes jank
```

### Reduced-motion fallback

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}
```

### Cleanup

Always clean up event listeners, observers, animation instances, and scheduled work in `useEffect`:

```js
useEffect(() => {
  const observer = new IntersectionObserver(callback);
  observer.observe(ref.current);
  return () => observer.disconnect();
}, []);
```

## Font Strategy

### Loading methods

- **Next.js:** use `next/font`:
  ```js
  import { Geist, Geist_Mono } from "next/font/google";
  const geist = Geist({ subsets: ["latin"], variable: "--font-sans" });
  const geistMono = Geist_Mono({ subsets: ["latin"], variable: "--font-mono" });
  ```
- **Other frameworks:** self-host with `@font-face` + `font-display: swap`:
  ```css
  @font-face {
    font-family: "Geist";
    src: url("/fonts/Geist.woff2") format("woff2");
    font-display: swap;
    font-weight: 100 900;
  }
  ```

**Never link Google Fonts via `<link>` in production.** This causes render-blocking requests and
exposes user IP to Google.

### Font pairings

| Sans | Mono | Use case |
|---|---|---|
| Geist | Geist Mono | Default modern SaaS / AI marketing |
| Satoshi | JetBrains Mono | Clean product UI |
| Cabinet Grotesk | Inter Tight | Creative / agency |
| GT America | IBM Plex Mono | Enterprise / technical |

### Default display type

```css
/* Display / Headlines */
text-4xl md:text-6xl tracking-tighter leading-none;

/* Body / Paragraphs */
text-base text-gray-600 leading-relaxed max-w-[65ch];
```

## Icon Strategy

- **Priority order:** `@phosphor-icons/react`, `hugeicons-react`, `@radix-ui/react-icons`,
  `@tabler/icons-react`.
- **Discouraged:** `lucide-react`. Acceptable only when the user explicitly asks for it or the project
  already depends on it.
- **Never hand-roll SVG icons.** If a glyph is missing, install a second library or compose from
  primitives - do not draw icon paths from scratch.
- **One family per project.** Do not mix Phosphor with Lucide in the same component tree.
- **Standardize `strokeWidth` globally** (e.g. `1.5` or `2.0`).

## Dependency Verification

Before importing ANY third-party library, check `package.json`. If the package is missing, output the
install command first. **Never assume a library exists.**

```bash
# Check before importing
grep "motion" package.json
# If missing:
npm install motion
```

## RSC Safety

- Global state works ONLY in Client Components. In Next.js, wrap providers in a `"use client"` component.
- Any component using Motion, scroll listeners, or pointer physics MUST be an isolated leaf with
  `'use client'` at the top. Server Components render static layouts only.
- Server Components can pass serializable props to Client Components but cannot use hooks, event
  handlers, or browser APIs.

```jsx
// page.tsx (Server Component - no "use client")
import { Hero } from "./Hero";

export default function Page() {
  return <Hero title="Welcome" />;
}

// Hero.tsx (Client Component - interactive)
"use client";
import { motion } from "motion/react";

export function Hero({ title }) {
  return <motion.h1 initial={{ opacity: 0 }}>{title}</motion.h1>;
}
```

## Layout Mechanics

- **Full-height sections:** `min-h-[100dvh]`, never `h-screen` (iOS Safari address bar causes layout
  jumping).
- **Multi-column layouts:** CSS Grid, never flexbox percentage math:
  ```jsx
  // Correct
  <div className="grid grid-cols-1 md:grid-cols-3 gap-6">

  // Wrong
  <div className="flex">
    <div className="w-[calc(33%-1rem)]">
  ```
- **Container:** `max-w-[1400px] mx-auto` or `max-w-7xl`.
- **Standard breakpoints:** `sm 640`, `md 768`, `lg 1024`, `xl 1280`, `2xl 1536`.

## z-index Scale

Use layered tokens instead of bare values. Define these as CSS variables or Tailwind config entries:

```css
:root {
  --z-base: 0;
  --z-dropdown: 10;
  --z-sticky: 20;
  --z-drawer: 30;
  --z-modal: 40;
  --z-toast: 50;
}
```

| Layer | Token | Use for |
|---|---|---|
| base | `--z-base` (0) | normal document flow |
| dropdown | `--z-dropdown` (10) | select menus, autocomplete, popovers |
| sticky | `--z-sticky` (20) | sticky headers, sticky sidebars, sticky table headers |
| drawer | `--z-drawer` (30) | slide-over panels, navigation drawers |
| modal | `--z-modal` (40) | dialogs, modals, full-screen overlays |
| toast | `--z-toast` (50) | toast notifications, snackbar, alerts above modals |

Rules:
- `z-index` values must come from tokens or CSS variables. Never inline `z-index: 9999` or similar
  magic numbers.
- If a stacking conflict appears, add a token layer rather than escalating the number.
- Projects may customize layer names but must maintain a分层 scale.

## Overscroll Containment

Prevent scroll chaining (scrolling inside a modal/drawer propagating to the underlying page):

```css
.modal-body {
  overscroll-behavior: contain;
  overflow-y: auto;
  max-height: 90vh;
}

/* Optional: lock body scroll when modal is open */
body.modal-open {
  overflow: hidden;
  /* Preserve scroll position: use position: fixed with top offset */
}
```

For body scroll lock that preserves scroll position, record `window.scrollY` before locking and restore
it on unlock. CSS-only `overflow: hidden` on `body` will jump to top in some browsers.

---

**Acceptance criteria:** After reading this file, you can use correct import paths for Motion, write
animation with `useMotionValue`/`useScroll` instead of `useState`, load fonts via `next/font` or
self-hosted `@font-face`, choose the right icon library, verify dependencies before importing, isolate
interactivity in RSC client leaves, use CSS Grid instead of flex math, apply `min-h-[100dvh]` instead
of `h-screen`, use layered z-index tokens instead of magic numbers, and apply overscroll containment
on modals and drawers.
