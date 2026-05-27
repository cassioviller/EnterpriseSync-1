---
name: high-end-visual-design
description: "Elevates UI to premium, sophisticated quality. Use when the user wants designs that feel expensive, intentional, and distinctive — not generic Bootstrap or utility-class output. Covers luxury typography, refined palettes, generous spacing, deliberate micro-interactions, and editorial-grade layouts. Applies to SaaS dashboards, marketing pages, product UI, and admin panels. Activates anti-generic rules: no default shadows, no flat Bootstrap cards, no 16px Inter everywhere."
---

# High-End Visual Design

Produce interfaces that feel designed by a senior product designer at a company that ships premium software. Not polished templates — opinionated, distinctive, memorable.

---

## Core Doctrine

**Default outputs are the enemy.** Every decision below exists to eliminate the generic.

1. **If it looks like it came from a UI kit, it's wrong.** No default card shadows. No stock blue primary. No Inter at 16px everywhere. No `rounded-lg` on everything.
2. **Every visual decision must be intentional.** If you can't articulate why a spacing value, weight, or color was chosen, it's a default — replace it.
3. **Restraint is a feature.** Fewer effects done well beats many effects done adequately. One deliberate animation, one confident color, one unexpected type choice.
4. **White space is not empty space.** Dense layouts signal amateur work. Generous, structured white space signals confidence.

---

## Typography

### Rules
- **No single typeface at one weight.** Pair at minimum two weights deliberately. For display text: tight tracking, high weight. For body: relaxed tracking, generous line-height.
- **Display type should command the viewport.** Headlines at `clamp(2.5rem, 6vw, 5rem)` minimum for hero contexts. Not 24px.
- **Use tabular figures for any number.** `font-variant-numeric: tabular-nums` on dashboards, prices, stats.
- **Label text is not body text.** `0.6875rem` (11px) caps-and-tracked for field labels. `0.75rem` (12px) sentence-case for metadata.

### Premium Pairings
| Context | Heading | Body |
|---------|---------|------|
| SaaS product | Geist / Instrument Sans | Inter / System UI |
| Marketing premium | Editorial New / Playfair Display | Söhne / Aktiv Grotesk |
| Dashboard data | DM Sans | JetBrains Mono (for values) |
| Editorial | Canela / Tiempos | Graphik / GT Walsheim |
| Luxury brand | Cormorant Garamond | Neue Haas Grotesk |

---

## Color

### System Structure
Every high-end palette has three layers:
1. **Canvas** — the page/surface background (not pure white, not #fff — try `#fafaf9`, `#f5f4f2`, `#0f0f0f` for dark)
2. **Surface** — cards, panels, elevated elements (slightly lighter or with subtle border, never just `white` on white)
3. **Accent** — one intentional hue used sparingly. The accent should feel earned, not sprinkled.

### Anti-patterns to eliminate
- `bg-blue-500` as primary → use a specific hue with intention: `hsl(217, 91%, 50%)` or define a custom scale
- Pure black text `#000` → use `#0f0f0f`, `#111`, `#1a1a1a`
- Pure white `#fff` backgrounds → use `#fafaf9` or `#fdfdfc`
- Gray as neutral filler → pick one gray family and stick to it (`zinc`, `stone`, `slate` — not mixed)

### Palette Examples
| Style | Canvas | Accent | Text |
|-------|--------|--------|------|
| Warm minimal | `#f5f0eb` | `#c2713b` | `#1c1917` |
| Cold precision | `#f1f3f5` | `#2563eb` | `#0f172a` |
| Dark premium | `#0a0a0a` | `#a78bfa` | `#f8fafc` |
| Editorial | `#fffef7` | `#dc2626` | `#1a1a1a` |

---

## Spacing & Layout

- **8px base grid, 4px for micro.** No arbitrary values. Spacing = `4, 8, 12, 16, 24, 32, 48, 64, 96, 128`.
- **Section padding starts at `clamp(4rem, 10vw, 8rem)`** for full-width sections on marketing pages.
- **Content max-width**: prose at `65ch`, cards at `640px`, wide layouts at `1280px` with `1440px` max.
- **Column gaps at `1.5rem` minimum** between card columns. Tight grids look cheap.

---

## Elevation & Depth

Forget `box-shadow: 0 2px 4px rgba(0,0,0,0.1)`.

**Layered shadow system:**
```css
/* Level 1 — subtle card lift */
box-shadow: 0 1px 2px rgba(0,0,0,0.04), 0 4px 8px rgba(0,0,0,0.04);

/* Level 2 — dropdown, popover */
box-shadow: 0 4px 6px rgba(0,0,0,0.05), 0 12px 20px rgba(0,0,0,0.08);

/* Level 3 — modal, dialog */
box-shadow: 0 8px 16px rgba(0,0,0,0.06), 0 24px 48px rgba(0,0,0,0.12);
```

For dark mode, shadows don't work — use border-based elevation:
```css
border: 1px solid rgba(255,255,255,0.08);
background: rgba(255,255,255,0.04);
```

---

## Motion & Interaction

### Principles
- **Animate meaning, not decoration.** A button loading state communicates progress. A random bounce communicates nothing.
- **Duration discipline:** Micro (button hover) = 120–180ms. Component enter = 200–300ms. Page transition = 350–450ms. Nothing longer than 600ms.
- **Easing:** `cubic-bezier(0.16, 1, 0.3, 1)` for enters (springy). `cubic-bezier(0.4, 0, 1, 1)` for exits (snappy out). Never `ease-in-out` for UI (it feels sluggish).

### Micro-interactions to include
- Button: `transform: translateY(-1px)` on hover + subtle shadow increase
- Card hover: `transform: translateY(-2px)` + shadow level up
- Input focus: border color transition + faint ring expand
- Success state: checkmark draw animation, not a static icon swap

---

## Component Specifics

### Buttons
```css
/* Primary — not just a colored rectangle */
.btn-primary {
  background: var(--accent);
  color: white;
  padding: 0.625rem 1.25rem;
  border-radius: 6px;          /* Not fully rounded — signals product, not consumer */
  font-weight: 500;
  font-size: 0.875rem;
  letter-spacing: -0.01em;
  transition: all 140ms cubic-bezier(0.16, 1, 0.3, 1);
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.15), 0 1px 2px rgba(0,0,0,0.2);
}
.btn-primary:hover {
  filter: brightness(1.08);
  transform: translateY(-1px);
}
```

### Cards
No default cards. Every card should answer: *what is the visual hierarchy inside this card?*
- One dominant piece of information (large, heavy)
- One secondary (smaller, lighter)
- Actions at bottom with clear affordance
- Border at `1px solid` with `rgba` opacity, never a solid gray

### Tables
- Zebra striping only if >8 rows
- Sticky header with `backdrop-filter: blur(8px)` on scroll
- Numeric columns right-aligned, always `tabular-nums`
- Action columns: icon buttons, visible only on row hover (`:hover` CSS, not JS)

---

## What NOT to Do

| Pattern | Why It's Generic | Fix |
|---------|-----------------|-----|
| `rounded-full` on everything | Consumer/playful signal, not product | Use `rounded-md` (6–8px) for UI elements |
| Gradient buttons | Dated, WebKit-era aesthetic | Flat with inset highlight or solid |
| `font-size: 16px` body everywhere | No visual hierarchy | 15px body, 13px secondary, 11px label |
| Multiple accent colors | Visual noise | One accent, one neutral, done |
| `opacity-50` disabled states | Not accessible | `cursor-not-allowed` + specific disabled color token |
| Bootstrap `card` defaults | Looks like 2017 | Custom shadow + border system |
| `mb-4` on every element | No rhythm | Define a spacing scale and stick to it |

---

## Quick Checklist Before Shipping

- [ ] No pure `#fff` background, no pure `#000` text
- [ ] Typeface pairing with at least 2 intentional weights
- [ ] Spacing follows 8px grid (no `17px`, `23px` margins)
- [ ] One accent color used ≤3 places on a single view
- [ ] All interactive elements have hover + focus states
- [ ] Shadows use layered system, not single value
- [ ] Numbers use `tabular-nums`
- [ ] Motion under 400ms, meaningful easing
