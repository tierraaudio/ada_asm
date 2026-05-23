# dashboard-shell Specification

## Purpose
TBD - created by archiving change dashboard-shell-redesign. Update Purpose after archive.
## Requirements
### Requirement: Authenticated dashboard renders a chrome with brand sidebar and content area

The frontend SHALL render an authenticated dashboard chrome that consists of: a Header bar at the top, a Sidebar on the left, and a content area on the right. Pixel-faithful to Figma `47:14343` at the `lg` (1024+) breakpoint when the Sidebar is expanded; pixel-faithful to Figma `47:23460` when the Sidebar is collapsed. The Header is always rendered; the Sidebar is conditionally rendered based on collapse state (see "Sidebar collapse" requirement).

#### Scenario: Expanded chrome renders Header above and Sidebar to the left of content

- **WHEN** an authenticated user opens `/` with `sidebarCollapsed` state `false`
- **THEN** the page renders a Header (full width, ~85 px tall) above a row containing a 256 px Sidebar (left) and a content area (right) that takes the remaining width
- **AND** the Sidebar background is `#ffffff`, the right border `1 px solid rgba(0,0,0,0.1)`, the page background `#fafafa`

#### Scenario: Collapsed chrome reflows content to full width

- **WHEN** an authenticated user opens `/` with `sidebarCollapsed` state `true`
- **THEN** the Sidebar is fully removed from the layout (not a rail with icons)
- **AND** the Header + content area span the entire viewport width

### Requirement: The Sidebar header renders the real Singular Things SVG logo

The Sidebar header section (top, ~77 px tall, bottom border `rgba(0,0,0,0.1)`) SHALL render the Singular Things wordmark from the SVG asset at `frontend/public/brand/singularthings-wordmark.svg`. The asset is served as `/brand/singularthings-wordmark.svg` from the Vite static root and consumed via an `<img>` tag, scaled to roughly 128 px wide so the wordmark height matches the Figma at ~28 px. The text-based `BrandWordmark` component MUST NOT be used in this surface; it stays available only for the auth pages (`/login`, `/forgot-password`, `/reset-password`).

#### Scenario: Sidebar header shows the brand logo as an image

- **WHEN** the Sidebar is expanded
- **THEN** the Sidebar header contains an `<img>` whose `src` resolves to `/brand/singularthings-wordmark.svg`
- **AND** the image's `alt` attribute is `Singular Things`

### Requirement: Sidebar exposes three nav items in domain-hierarchy order

The Sidebar SHALL render a `<nav>` with exactly three items, in this fixed order from top to bottom:

1. **Proyectos** — routes to `/projects`
2. **Módulos** — routes to `/modules`
3. **Componentes** — routes to `/components`

This order overrides the Figma frame `47:14343` (which shows Proyectos → Componentes → Módulos) because the project mandates domain-hierarchy ordering. Each item is a `react-router-dom` `<NavLink>` so the active state is automatic. Each item is 48 px tall with rounded 6 px corners, 16 px horizontal padding, a 20 px leading lucide icon, and a 16 px Inter Regular label. Active item: `bg-text-primary` (black `#1a1a1a`), `text-white`. Inactive item: text `text-text-primary` on the Sidebar's white background. Hover (inactive only): `bg-accent` background, `text-accent-foreground` text.

#### Scenario: Sidebar nav items render in hierarchy order

- **WHEN** the Sidebar is expanded
- **THEN** the three `<nav>` links appear in this DOM order: `Proyectos`, `Módulos`, `Componentes`
- **AND** their `href` attributes are `/projects`, `/modules`, `/components` respectively

#### Scenario: The active route highlights its nav item

- **WHEN** the user is at `/modules`
- **THEN** the `Módulos` item has `bg-text-primary` (black) background and white text
- **AND** the other two items have transparent background and dark text

### Requirement: The Header hosts a sidebar toggle on the left

The Header SHALL render a 36 px button at the top-left that toggles the Sidebar between expanded and collapsed. When the Sidebar is collapsed, the button's icon is `lucide:Menu` (a hamburger); when expanded, the icon is `lucide:X` (a close glyph). The button is keyboard reachable and announces its purpose via `aria-label="Mostrar menú lateral"` (collapsed) / `aria-label="Ocultar menú lateral"` (expanded). The button has a visible `focus-visible` ring consistent with the rest of the chrome.

#### Scenario: Toggle icon reflects the current state

- **WHEN** `sidebarCollapsed` is `true`
- **THEN** the Header's top-left button renders the `Menu` (hamburger) icon
- **WHEN** `sidebarCollapsed` is `false`
- **THEN** the Header's top-left button renders the `X` icon

#### Scenario: Clicking the toggle flips the state

- **WHEN** the user clicks the Header toggle button while `sidebarCollapsed` is `false`
- **THEN** `sidebarCollapsed` becomes `true`
- **AND** the Sidebar disappears from the DOM
- **WHEN** the user clicks the toggle again
- **THEN** `sidebarCollapsed` becomes `false`
- **AND** the Sidebar reappears

### Requirement: Sidebar collapse state persists across reloads

The Sidebar collapse state SHALL be persisted to `localStorage` under the key `adaasm.ui.sidebarCollapsed` as the string `"true"` or `"false"`. On a fresh load with no value stored, the default state is **expanded** (`sidebarCollapsed = false`). The persistence layer lives in a dedicated module (`src/lib/ui/sidebar-storage.ts`) so a future migration to a different store can swap the persistence without touching the rendering components.

#### Scenario: Toggle persists and is restored on reload

- **WHEN** the user collapses the Sidebar
- **THEN** `localStorage.getItem("adaasm.ui.sidebarCollapsed")` returns `"true"`
- **WHEN** the page is reloaded
- **THEN** the Sidebar starts in the collapsed state without flashing the expanded state first

#### Scenario: First load defaults to expanded

- **WHEN** the application loads for the first time on a fresh device (no value in localStorage)
- **THEN** the Sidebar renders in expanded state
- **AND** no value is yet written to `localStorage` (writing only happens on explicit user toggle)

### Requirement: Keyboard navigation order in the Header is deterministic

When focus enters the Header via Tab, focus SHALL move through the controls in this order: sidebar toggle (top-left) → notification bell trigger → user menu pill trigger. All three controls are keyboard reachable and visibly indicate focus via `focus-visible` styles.

#### Scenario: Tab cycles through the Header controls left to right

- **WHEN** the page is focused on the document body and the user presses Tab repeatedly
- **THEN** focus visits the sidebar toggle, then the notification bell trigger, then the user menu pill trigger, in that order
