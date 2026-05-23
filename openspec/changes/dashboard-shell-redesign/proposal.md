<!--
design-linked: true | scope: FE
-->

## Design References

Figma file: `pMUgDI7rbRRzVWLCJhoVnY` (`ada_asm`).

Referenced Nodes:
- https://www.figma.com/design/pMUgDI7rbRRzVWLCJhoVnY/ada_asm?node-id=47-14343 — Sidebar expanded + notifications dropdown open
- https://www.figma.com/design/pMUgDI7rbRRzVWLCJhoVnY/ada_asm?node-id=47-23460 — Sidebar collapsed

Pixel fidelity required at the `lg` (1024+) breakpoint.

## Why

The dashboard shell that landed with `login-en-asm` was the minimum a logged-in user needed to see something behind the auth wall. It is now visibly off-design: the brand is rendered as text instead of the real Singular Things SVG that lives in the repo, the sidebar has no collapsed state so users cannot reclaim horizontal space, the header has no toggle control, the notification bell is a no-op visual placeholder, and the placeholder nav items don't yet reflect the domain hierarchy. We have two Figma frames (`47:14343` expanded + `47:23460` collapsed) that lock the canonical look — implementing them now closes the gap before we start landing business pages on top of a half-finished chassis.

## What Changes

### Sidebar
- The placeholder sidebar from `login-en-asm` is replaced with the canonical version per Figma `47:14343`.
- Brand area renders the real Singular Things SVG from `frontend/public/brand/singularthings-wordmark.svg` (committed in `fa64c91`); the text-based `BrandWordmark` is kept for the auth pages but no longer used by the dashboard chrome.
- Three nav items in **domain-hierarchy order**: **Proyectos → Módulos → Componentes**. NOTE: this deliberately overrides the Figma's literal order (Proyectos → Componentes → Módulos) per explicit user instruction; documented in design.md.
- Nav item styling: 48 px tall, rounded 6 px, leading icon (lucide 20 px) + 16 px label; active state `bg-text-primary` / `text-white`; inactive `text-text-primary`; hover `bg-accent`.
- Items wire to `/projects`, `/modules`, `/components`. Those routes do not yet have business pages (future USs); for now they render the existing placeholder content via the protected route shell.

### Header — sidebar toggle
- New left-side button (36 px) in the Header that toggles the sidebar collapsed/expanded.
- Icon flips between `lucide:Menu` (when collapsed) and `lucide:X` (when expanded).
- Collapse state persists across reloads via `localStorage` under `adaasm.ui.sidebarCollapsed`. Default on first load: expanded.
- When collapsed, the sidebar is **fully removed** from the layout (not a rail-with-icons). The Header + content area reflow to fill the viewport width.

### Notification panel
- The existing `NotificationBell` becomes interactive. Wrapped in a new `NotificationMenu` component that owns the popover state (Radix Popover, same pattern as `UserMenuDropdown`).
- Panel: 384 px wide, anchored under the bell, pixel-faithful to Figma `47:14343`. Header "Notificaciones" + magenta pill "2 nuevas"; scrollable list of items (unread tinted + magenta dot); footer link "Ver todas las notificaciones".
- Placeholder data only (6 items from the Figma copy, two unread). A data hook (`useNotifications`) is introduced so the future US that wires the real feed replaces the source without touching the rendering component.
- Panel closes on Escape and outside-click.

### UI state store
- New `useUiStore` (`src/lib/stores/ui-store.ts`) Zustand store holding `sidebarCollapsed: boolean` and `toggleSidebar`, `setSidebarCollapsed` actions.
- Tiny persistence helper `src/lib/ui/sidebar-storage.ts` (mirrors `token-storage.ts`) owning the `adaasm.ui.sidebarCollapsed` key.

### Non-goals
- No real notification feed (no backend endpoint, no polling, no unread count from server). The bell's red dot stays as a visual placeholder.
- No `/projects`, `/modules`, `/components` business pages. The links route but land on the placeholder shell until each domain US ships.
- No mobile-overlay sidebar variant. Below `lg` the sidebar starts collapsed; user can toggle but the layout is the same push/hide behaviour.
- No animation polish beyond Radix defaults.
- No backend changes, no migrations, no new env vars.

## Capabilities

### New Capabilities
- `dashboard-shell`: the authenticated chrome — sidebar with brand logo, hierarchy-ordered nav, expanded/collapsed state with localStorage persistence, hamburger toggle in the Header.
- `in-app-notifications`: the click-to-open notification panel surfaced from the Header bell. Static placeholder data behind a `useNotifications` hook so the future feed can drop in.

### Modified Capabilities
- `runnable-skeleton`: the placeholder shell requirement no longer mandates a hardcoded plain "ADA ASM" Header; it defers Header chrome to `dashboard-shell` and `in-app-notifications`.
- `frontend-auth-shell`: the `UserMenuPill` requirement still owns the avatar pill on the Header right side, but the previously-static `NotificationBell` is now interactive (opens the notification panel from `in-app-notifications`). The pill component is unchanged.

## Impact

- **Code (frontend only)**: introduces `src/lib/stores/ui-store.ts`, `src/lib/ui/sidebar-storage.ts`, `src/components/ui/popover.tsx`, `src/features/notifications/components/{NotificationMenu,NotificationPanel}.tsx`, `src/features/notifications/hooks/use-notifications.ts`, `src/features/notifications/types.ts`, plus updates to `src/app/layout/{Header,Sidebar,DashboardLayout}.tsx` and a logo wrapper component for the SVG.
- **Assets**: the SVG already at `frontend/public/brand/singularthings-wordmark.svg` is now consumed by the dashboard sidebar.
- **Tests**: new Vitest cases for `ui-store`, `sidebar-storage`, `NotificationMenu`, the new `Sidebar` and `Header` behavior, and a new Playwright `@smoke` test that covers sidebar toggle persistence and notification panel open/close.
- **Dependencies**: `@radix-ui/react-popover` (if not already installed transitively via `@radix-ui/react-dropdown-menu`).
- **Backend / migrations / docker / CI**: no changes.
- **Risk**: this is the second change that modifies `runnable-skeleton` and the first that modifies `frontend-auth-shell` — exercises the openspec MODIFIED delta workflow on a capability that has multiple downstream specs depending on it.
