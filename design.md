# LiteLLM Admin Dashboard — Design Study

A design specification reverse-engineered from the live LiteLLM Admin UI at `http://localhost:4000/ui/`. All values are taken from computed styles in a real session (1440×900 viewport, light mode). Screenshots in `design/screenshots/`. Raw token dumps in `design/tokens-*.json`.

---

## 1. Stack Fingerprint

The UI is a hybrid of three component systems layered onto Next.js + Tailwind:

| Layer | Source | Where you see it |
|---|---|---|
| Layout shell, top nav, sidebar, menus, tables, modals, basic buttons | **Ant Design 5** (`ant-*` classes, `css-mncuj7` runtime classnames) | Left nav, "Filters" / "Reset Filters" buttons, modal, key table |
| Cards, tabs, primary CTA, charts, text inputs, badges | **Tremor** (`tremor-*` classes, Tailwind `rounded-tremor-default`, `shadow-tremor-input`) | "+ Create New Key" button, Models page tabs, all cards |
| Utility/layout | **Tailwind CSS** (`text-lg font-semibold`, `bg-white border-b border-gray-200 …`) | Top nav classes, headings, page chrome |

Translation: if you're recreating this look greenfield, start with **Tailwind + Tremor** for content and only reach for Ant Design where you need the heavier table/modal primitives. The duality is the original codebase's history, not a deliberate design choice — a clean rebuild should pick one.

---

## 2. Layout

```
┌─────────────────────────────────────────────────────────────────┐
│  Top Nav  ── height 57px, bg #fff, border-b #E5E7EB (gray-200)  │
├──────────┬──────────────────────────────────────────────────────┤
│          │                                                      │
│  Sidebar │   Content area                                       │
│  220 px  │   bg #fff, padding ~24px                             │
│  bg #fff │                                                      │
│          │                                                      │
└──────────┴──────────────────────────────────────────────────────┘
```

- **Top nav** — sticky, `bg-white border-b border-gray-200 sticky top-0 z-10`. Brand mark left (🚅 LiteLLM, 16px Inter), action links right (Chat with `NEW` badge, Docs, Blog, User menu). Height **57 px**.
- **Sidebar** — `ant-layout-sider ant-layout-sider-light`, fixed 220 px wide, white background, no border or shadow (purely separated by the content's left padding). Collapsible via a "menu-fold" icon in the top nav.
- **Content** — full remaining width, white background, light internal padding. All views are bordered cards or tables, not a grid of widgets.

---

## 3. Design Tokens

### 3.1 Color palette

Derived from frequency analysis across the rendered DOM. Most used → least used.

#### Brand / interactive

| Token | Hex | RGB | Used for |
|---|---|---|---|
| `brand.primary` | **`#4338CA`** | rgb(67, 56, 202) | Tremor primary CTA (`+ Create New Key`, `Login`) — solid fill |
| `brand.primary-fg` | `#FFFFFF` | rgb(255, 255, 255) | Text on primary buttons |
| `brand.accent` | `#6366F1` (indigo-500) | rgb(99, 102, 241) | Active tab underline, focus-ring base |
| `brand.deep` | `#531DAB` | rgb(83, 29, 171) | Heavy text accents (rare) |
| `brand.tint` | `#F9F0FF` | rgb(249, 240, 255) | Accent surface (info chip background) |
| `link.primary` | `#1677FF` (Ant blue-6) | rgb(22, 119, 255) | Selected menu item text; `NEW` badge text |
| `link.primary-bg` | `#E6F4FF` | rgb(230, 244, 255) | Selected sidebar menu item background |
| `info.tag-bg` | `#EFF6FF` (blue-50) | rgb(239, 246, 255) | Copyable IDs / monospace pill background |
| `info.tag-fg` | `#3B82F6` (blue-500) | rgb(59, 130, 246) | Copyable IDs foreground |

#### Neutrals (Tailwind gray-scale)

| Token | Hex | RGB | Used for |
|---|---|---|---|
| `text.strong` | `#111827` (gray-900) | rgb(17, 24, 39) | Headings, table headers |
| `text.default` | `rgba(0,0,0,0.88)` | — | Ant body text (labels, menus, buttons) |
| `text.muted` | `#6B7280` (gray-500) | rgb(107, 114, 128) | Paragraphs, table cells, placeholder-ish copy |
| `text.subtle` | `#374151` (gray-700) | rgb(55, 65, 81) | Form input value text, accordion headers |
| `text.disabled` | `rgba(0,0,0,0.45)` | — | Disabled labels, breadcrumb dividers |
| `text.placeholder` | `rgba(0,0,0,0.25)` | — | Input placeholders |
| `border.subtle` | `#E5E7EB` (gray-200) | rgb(229, 231, 235) | Primary divider — by far the most used color (~647 occurrences) |
| `border.muted` | `#D9D9D9` | rgb(217, 217, 217) | Ant outlined-button border |
| `border.card` | `#F0F0F0` | rgb(240, 240, 240) | Ant Card border (lighter than the gray-200 dividers) |
| `surface.base` | `#FFFFFF` | rgb(255, 255, 255) | Page, sidebar, top nav, card bg |
| `surface.alt` | `#FAFAFA` | rgb(250, 250, 250) | Ant tags |
| `surface.alt-2` | `#F5F5F5` | rgb(245, 245, 245) | Rare — hover states |

**Practical implication**: this is a **white-first, low-contrast UI**. Borders carry the structure; fills are reserved for emphasis (CTA indigo, selected menu blue, info chips). Get the gray-200 border right and most of the look falls into place.

### 3.2 Typography

The stack mixes two font families because Ant Design ships its own:

| Family | Where |
|---|---|
| **`Inter, "Inter Fallback"`** | Body, headings, brand mark, sidebar headers — set on `body` |
| `-apple-system, "system-ui", "Segoe UI", Roboto, "Helvetica Neue", Arial, "Noto Sans", sans-serif, …` | Ant Design components (form labels, buttons, menu items) — Ant's own stack |
| `ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace` | `<code>` blocks (e.g. `admin`, `MASTER_KEY` in the login info box) |
| `ui-sans-serif, system-ui, sans-serif, …` | The bare HTML root (gets overridden by body) |

**For a clean rebuild: one family, Inter, everywhere.** Add a system fallback chain and a separate monospace token.

#### Scale (observed)

| Role | Size / Line-height | Weight | Color | Notes |
|---|---|---|---|---|
| `h2` (page title, "Model Management") | 18 / 28 | 600 | `#000` | `text-lg font-semibold` |
| `h3` (login form heading "Login") | ~20 / ~28 | 600 | strong | — |
| `h4` (section heading, "Missing a provider?") | 14 / 20 | 600 | gray-900 | `text-gray-900 font-semibold text-sm m-0` |
| `body` | 16 / 24 | 400 | `#000` | Inter |
| `label` (Ant) | 14 / 22 | 400 | `rgba(0,0,0,0.88)` | Form labels |
| `button` (Tremor primary) | 14 / — | 500 | `#fff` | — |
| `button` (Ant) | 14 / — | 400 | `rgba(0,0,0,0.88)` | — |
| `body small / p` | **12.4 / 18.4** | 400 | gray-500 | `0.775rem` — quirky, see below |
| `table cell` | 12.4 / — | 400 | gray-500 | Same scale as small body |
| `badge "NEW"` | 9 / — | 700 | `#1677FF` | 1px 4px padding, 3px radius |

The `12.4 / 18.4` value is `0.775rem / 1.15rem` — likely Tremor's `text-tremor-default` token. Round to **12 / 16** or **13 / 18** when recreating; the fractional values come from a Tailwind rem calc that doesn't add value.

### 3.3 Spacing & sizing

| Element | Padding | Size |
|---|---|---|
| Top nav | — | height 57 px |
| Sidebar | 0 | width 220 px |
| Sidebar menu item | `0 16px 0 24px` | height **30 px** (tight) |
| Page content | 24 px (cards) | — |
| Primary button (Tremor) | `8px 16px` | 36 px tall |
| Secondary button (Ant) | `0 15px` | 32 px tall (height-driven) |
| Form input (Tremor) | `8px 12px` | — |
| Form input (Ant) | `4px 11px` | — |
| Table header cell | `4px 16px` | — |
| Table body cell | **`2px 16px`** | Very tight rows |
| Card body | `24px` | — |
| Modal | `20px 24px` | — |

The table rows are deliberately dense (2px vertical padding). If you want a less cramped feel, bump to 8–12 px.

### 3.4 Border radius

Frequency-sorted:

| Radius | Use |
|---|---|
| **`6px`** (37 hits) | Ant default — buttons, inputs, dropdowns |
| **`8px`** (7 hits) | Tremor radius (`rounded-tremor-default`) — primary CTA, cards, modal |
| `4px` | Ant tags |
| `3px` | `NEW` micro-badge |
| `50%` / `100%` | Avatars, indicator dots |
| `10px` | Rare — one accent surface |

**Pick one and stick with it.** For a clean rebuild, `6px` for inputs/secondary, `8px` for primary CTAs and cards.

### 3.5 Shadows

The UI is **nearly flat**. The few shadows in use:

| Token | Value | Use |
|---|---|---|
| `shadow.xs` (Tailwind shadow-sm) | `0 1px 2px 0 rgba(0,0,0,0.05)` | Tremor primary CTA |
| `shadow.ant-button` | `0 2px 0 0 rgba(0,0,0,0.02)` | Ant outlined buttons (almost invisible) |
| `shadow.focus-ring` (Tremor) | `inset 0 0 0 1px rgba(59,130,246,0.2)` | Focused input |
| `shadow.modal` (Ant) | `0 6px 16px rgba(0,0,0,0.08), 0 3px 6px -4px rgba(0,0,0,0.12), 0 9px 28px 8px rgba(0,0,0,0.05)` | Modal dialog |
| `ring.focus` (Tailwind default) | `--tw-ring-color: #3b82f680` (blue-500 @ 50%) | Focus ring base |

Cards have **no shadow** — they're delineated by a `1px solid #F0F0F0` border only.

---

## 4. Component Inventory

### 4.1 Top navigation (`screenshots/02-dashboard-keys.png`)
- White, 57px tall, sticky, `border-b border-gray-200`.
- Left: hamburger (menu-fold), brand "🚅 LiteLLM" (16 px Inter, no special weight).
- Right cluster: `Chat` link with **`NEW`** badge, `Docs`, `Blog` dropdown, `User` dropdown.
- All right-side buttons are Ant text-buttons: transparent bg, no border, padding `0 15px`.

### 4.2 Sidebar (`screenshots/02-dashboard-keys.png`)
- 220 px wide, white background, no right border (separation by content offset).
- **Grouped menu** with uppercase section labels: `AI GATEWAY`, `OBSERVABILITY`, `ACCESS CONTROL`, `DEVELOPER TOOLS`, `SETTINGS`.
- Each row is 30 px tall, 13 px font, `padding: 0 16px 0 24px`.
- **Selected state**: background `#E6F4FF`, text `#1677FF`. No bar/indicator — pure fill.
- Each item has a small leading icon (Ant Design icon set: `key`, `play-circle`, `block`, `robot`, `tool`, `safety`, etc.).
- Inline `NEW` badge on new items (e.g. Chat, Settings).

### 4.3 Primary CTA — Tremor button (`screenshots/02-dashboard-keys.png`)

```css
background: #4338CA;        /* indigo-700 */
color: #FFFFFF;
border: 1px solid #4338CA;
border-radius: 8px;
padding: 8px 16px;
font: 500 14px Inter;
box-shadow: 0 1px 2px rgba(0,0,0,0.05);  /* shadow-sm */
```

Used for `+ Create New Key`, `Login`, and the principal action in each view. Plus glyph is part of the label, not a separate icon.

### 4.4 Secondary button — Ant outlined (`screenshots/02-dashboard-keys.png`)

```css
background: #FFFFFF;
color: rgba(0,0,0,0.88);
border: 1px solid #D9D9D9;
border-radius: 6px;
padding: 0 15px;            /* height-driven sizing */
font: 400 14px (system stack);
box-shadow: 0 2px 0 0 rgba(0,0,0,0.02);
```

`Filters`, `Reset Filters`, `Create Key` (when in a form context).

### 4.5 Text input (`screenshots/01-login.png`, `screenshots/10-create-key-modal.png`)

Two flavors visible:

**Tremor** (large free-standing inputs):
```css
background: transparent;
color: #374151;
border: 1px solid #E5E7EB;
border-radius: 8px;
padding: 8px 12px;
font-size: 12.4px;
/* focus */
box-shadow: inset 0 0 0 1px rgba(59,130,246,0.2);
```

**Ant** (form inputs in modals):
```css
border: 1px solid #D9D9D9;
border-radius: 6px;
padding: 4px 11px;
font-size: 14px;
```

### 4.6 Data table (`screenshots/02-dashboard-keys.png`, `screenshots/05-logs.png`)

- Plain HTML `<table>`, not Ant Table — uses Tremor styles + custom Tailwind.
- **Header**: transparent bg, gray-900 text, 600 weight, **12.4 px**, padding `4px 16px`. No bottom border.
- **Body cell**: transparent bg, gray-500 text, 12.4 px, **padding `2px 16px`** (dense rows).
- Sortable header cells have a sort arrow icon trailing the label.
- **Tag-in-cell pattern**: small pills (e.g. `coder_model`, `heartbeat`, `TPM: Unlimited`) — these are Ant tags: `#FAFAFA` bg, `#D9D9D9` border, 4 px radius, 12 px, weight 500.
- **Truncated ID button**: monospace style, `bg #EFF6FF`, `color #3B82F6`, 12 px, padding `2px 8px` — designed to look clickable for copy.
- **Pagination**: tight bar above table — "Showing 1 - 1 of 1 results" + "Page 1 of 1" + Previous/Next outlined buttons (`#E5E7EB` border, 6 px radius).
- **Filter bar**: "Filters" + "Reset Filters" outlined buttons, left-aligned.

### 4.7 Card (`screenshots/03-models.png`, `screenshots/07-settings.png`)

Ant Card pattern:
```css
.card        { background: #fff; border: 1px solid #F0F0F0; border-radius: 8px; }
.card-body   { padding: 24px; }
/* no shadow */
```
The "Provider / Router Type" panels on the Models page are stacked vertical cards.

### 4.8 Tabs (`screenshots/03-models.png`)

Tremor Tab:
- **Active**: 2 px bottom border `#6366F1` (indigo-500), text color matches, weight 400, padding 8 px.
- **Inactive**: no border, text gray-500.
- Hover: borders to 2 px (placeholder/hover styling).
- Used for in-page navigation under headings (e.g. "All Models" / "Add Model" / "LLM Credentials" on Models page).

### 4.9 Modal (`screenshots/10-create-key-modal.png`)

```css
background: #FFFFFF;
border-radius: 8px;
padding: 20px 24px;
box-shadow:
  0 6px 16px 0 rgba(0,0,0,0.08),
  0 3px 6px -4px rgba(0,0,0,0.12),
  0 9px 28px 8px rgba(0,0,0,0.05);
```
- Backdrop is Ant's default semi-transparent black.
- Title row: heading + close (×). Footer right-aligns Cancel + primary action.
- Forms inside modals: vertical layout, 14 px Ant labels, 4–8 px input gap, 16–20 px between fields. Required fields prefixed with red `*`.
- Long forms use a collapsible **Accordion** ("Optional Settings") — Tremor accordion, `padding: 12px 16px`, weight 400.

### 4.10 Info/alert box (`screenshots/01-login.png`)

The "Default Credentials" callout on the login screen:
- Light gray background (Ant `alert-info` light variant).
- Leading `info-circle` icon.
- Title `Default Credentials` (semibold), then body copy with inline `<code>` chips.
- Links inline, default blue, no underline until hover.

Use for documentation snippets inside the UI.

### 4.11 Badges & tags

- **`NEW` micro-badge**: 9 px, weight 700, white bg, `#1677FF` text, 3 px radius, padding `1px 4px`. Inline next to nav links.
- **Pill tag (Ant)**: `#FAFAFA` bg, `#D9D9D9` border, 4 px radius, 12 px, weight 500. For row tags like model names, rate limits.

---

## 5. To Recreate — Tailwind Config Cheat Sheet

If you're building a fresh app and want the same visual language, start here:

```js
// tailwind.config.js (extract)
module.exports = {
  theme: {
    extend: {
      colors: {
        // Brand
        brand:       { DEFAULT: '#4338CA', accent: '#6366F1', deep: '#531DAB', tint: '#F9F0FF' },
        // Link / selected nav
        link:        { DEFAULT: '#1677FF', bg: '#E6F4FF' },
        // Info pill (copyable IDs)
        info:        { fg: '#3B82F6', bg: '#EFF6FF' },
        // Neutrals — Tailwind defaults cover most, plus:
        border:      { card: '#F0F0F0', muted: '#D9D9D9' },  // augments gray-200
      },
      fontFamily: {
        sans: ['Inter', 'Inter Fallback', 'system-ui', 'sans-serif'],
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'Monaco', 'monospace'],
      },
      fontSize: {
        // The observed scale (rounded)
        xs:   ['12px', '16px'],
        sm:   ['13px', '18px'],
        base: ['14px', '22px'],
        md:   ['16px', '24px'],
        lg:   ['18px', '28px'],
      },
      borderRadius: {
        sm:  '4px',   // tags
        md:  '6px',   // inputs, secondary buttons (most common)
        lg:  '8px',   // primary CTA, cards, modal
      },
      boxShadow: {
        xs:    '0 1px 2px 0 rgba(0,0,0,0.05)',                     // CTA
        modal: '0 6px 16px rgba(0,0,0,0.08), 0 3px 6px -4px rgba(0,0,0,0.12), 0 9px 28px 8px rgba(0,0,0,0.05)',
        ring:  'inset 0 0 0 1px rgba(59,130,246,0.2)',             // focused input
      },
    },
  },
}
```

### Layout primitives

```jsx
// Shell
<div className="min-h-screen bg-white">
  <nav className="sticky top-0 z-10 h-[57px] flex items-center bg-white border-b border-gray-200 px-4">
    {/* brand + right links */}
  </nav>
  <div className="flex">
    <aside className="w-[220px] bg-white">
      {/* grouped menu — see Sidebar component */}
    </aside>
    <main className="flex-1 p-6">{children}</main>
  </div>
</div>

// Primary CTA
<button className="inline-flex items-center px-4 py-2 rounded-lg bg-brand text-white text-sm font-medium shadow-xs hover:bg-brand/90">
  + Create New Key
</button>

// Secondary
<button className="px-4 py-1.5 rounded-md border border-border-muted bg-white text-sm text-gray-800 hover:bg-gray-50">
  Filters
</button>

// Card
<div className="rounded-lg border border-border-card bg-white p-6">
  {/* card body */}
</div>

// Sidebar group
<div className="px-6 pt-4 text-xs uppercase tracking-wider text-gray-500">AI Gateway</div>
<ul>
  <li className="flex items-center h-[30px] pl-6 pr-4 text-[13px] hover:bg-gray-50 data-[selected]:bg-link-bg data-[selected]:text-link">
    <Icon /> Virtual Keys
  </li>
</ul>

// Table — dense rows
<table className="w-full">
  <thead>
    <tr className="text-left">
      <th className="px-4 py-1 text-xs font-semibold text-gray-900">Key ID</th>
      {/* ... */}
    </tr>
  </thead>
  <tbody>
    <tr>
      <td className="px-4 py-0.5 text-xs text-gray-500">
        <button className="rounded-sm bg-info-bg px-2 py-0.5 font-mono text-xs text-info-fg">
          95fc1b...
        </button>
      </td>
    </tr>
  </tbody>
</table>
```

---

## 6. Information Architecture (for completeness)

The sidebar tells you the product's mental model. Five groups, each with the menu items observed:

| Group | Items |
|---|---|
| **AI Gateway** | Virtual Keys · Playground · Models + Endpoints · Agents · MCP Servers · Guardrails · Policies · Tools |
| **Observability** | Usage · Logs · Guardrails Monitor |
| **Access Control** | Teams · Internal Users · Organizations · Access Groups · Budgets |
| **Developer Tools** | API Reference · AI Hub · Learning Resources · Experimental |
| **Settings** | Settings <span style="color:#1677FF">NEW</span> |

A clone would want similar grouping if the product covers the same surface area.

---

## 7. Captured Screens

All in `design/screenshots/`:

| # | File | View |
|---|---|---|
| 1 | `01-login.png` | Login screen with default-credentials callout |
| 2 | `02-dashboard-keys.png` | Virtual Keys (default landing) — top nav, sidebar, table |
| 3 | `03-models.png` | Models + Endpoints — tabs, cards, provider form |
| 4 | `04-usage.png` | Usage — observability/chart layout |
| 5 | `05-logs.png` | Logs — wide data table |
| 6 | `06-teams.png` | Teams — empty/list view |
| 7 | `07-settings.png` | Settings — sectioned forms |
| 8 | `08-api-ref.png` | API Reference — code-doc layout |
| 9 | `09-users.png` | Internal Users |
| 10 | `10-create-key-modal.png` | "Create New Key" modal — form layout, accordion |

Raw token JSON in `design/tokens-keys-page.json`, `tokens-extra.json`, `tokens-models-page.json`.
