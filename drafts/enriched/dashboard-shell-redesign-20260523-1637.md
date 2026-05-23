<!-- BEGIN_ENRICHED_USER_STORY -->
# Enriched User Story

design-linked: true
scope:
  backend: false
  frontend: true
source: Manual
reference: N/A

## Title
Dashboard shell — pixel-perfect sidebar + notifications dropdown

## Problem / Context
The current dashboard shell (Header + Sidebar) is the bootstrap placeholder from US 1 (login-en-asm). It does not match the canonical design captured in Figma 47:14343 (sidebar expanded + notifications dropdown open) and 47:23460 (sidebar collapsed). Specifically:

- The brand wordmark is rendered as text (`<p>singularthings</p>`) instead of the real Singular Things SVG asset that already lives at `frontend/public/brand/singularthings-wordmark.svg`.
- The Sidebar has no collapsed state — the user cannot reclaim screen real estate for the content area.
- The Header has no toggle control; the left side is a static spacer.
- The NotificationBell renders the icon and the red dot, but the click handler is a no-op — no panel opens.
- The Sidebar nav items don't yet reflect the domain hierarchy (they were placeholder text in the bootstrap).

This US closes those gaps and makes the shell pixel-faithful at the `lg` (1024+) breakpoint.

## Desired Outcome
A developer or operator opening `http://localhost:15173/` (after login) sees a shell that visually matches the two Figma frames, can collapse the sidebar with a single click, and can open a notification panel anchored under the bell — even though the notification list is placeholder data until the real notification feed lands in a future US.

## Acceptance Criteria

### Sidebar — expanded state (Figma `47:14343`)
- The Sidebar is rendered when the collapse state is `expanded`. Width 256 px, white background, right border `rgba(0,0,0,0.1)`.
- The Sidebar header (top, ~77 px tall, bottom border `rgba(0,0,0,0.1)`) renders the real Singular Things SVG logo loaded from `frontend/public/brand/singularthings-wordmark.svg`, scaled to ~128 px wide. The text-based `BrandWordmark` previously used in this surface is removed (it remains available for the auth pages — see Constraints).
- Below the header, three navigation items render in this **fixed order** (domain hierarchy):
  1. **Proyectos**
  2. **Módulos**
  3. **Componentes**
- Each item: 48 px tall, rounded 6 px, 16 px horizontal padding, 12 px gap between the leading icon (20 px) and the label (16 px regular Inter).
- The currently-active route renders with `bg-text-primary` (black `#1a1a1a`) and `text-white`. Inactive items render with `text-text-primary` on the default white background; on hover, `bg-accent` / `text-accent-foreground`.
- The mapping route → item is: `/projects` → Proyectos, `/modules` → Módulos, `/components` → Componentes. Until those routes exist, the items navigate to those URLs but the protected route handler shows the placeholder shell. The items are still rendered.

### Sidebar — collapsed state (Figma `47:23460`)
- When the collapse state is `collapsed`, the Sidebar is fully removed from the layout (NOT a rail mode with only icons). The DashboardLayout reflows so the Header and content area span the full viewport width.
- The toggle button persists in the Header (top-left, 36 px). When collapsed, it shows a hamburger icon (lucide `Menu`). When expanded, it shows a close icon (lucide `X`). Clicking the button toggles the state.
- The collapse state persists across reloads via `localStorage` under the key `adaasm.ui.sidebarCollapsed`, storing `"true"` / `"false"`. On first load (no value), default is `expanded`.

### Notification panel (Figma `47:14343`, dropdown anchored under the bell)
- Clicking the existing `NotificationBell` opens a 384 px wide panel anchored under it, on the right side of the Header. The panel uses the same Radix popover pattern as the user menu dropdown (`@radix-ui/react-popover`).
- The panel has:
  - **Header section** (bottom border): the heading "Notificaciones" (Inter Medium 18 px, `text-text-primary`) on the left, and a magenta pill (`bg-brand`, white text, ~24 px tall, fully rounded) on the right with the text "2 nuevas".
  - **Scrollable list section** (max-height ~500 px, vertical scroll). Each item is ~117 px tall with a bottom divider. Items render: a 14 px Inter Medium title (`text-text-primary`), a 12 px Inter Regular subtitle (`text-text-secondary`), and a 12 px Inter Regular timestamp (`text-text-secondary`). Unread items use a `rgba(233,30,140,0.05)` background tint and render a 8 px magenta dot at the top-right corner. The placeholder content comes from the Figma copy verbatim (6 items, two unread, Spanish).
  - **Footer section** (top border): a centred link "Ver todas las notificaciones" in `text-brand` 14 px Inter Medium.
- The panel closes on `Escape` and on outside-click (Radix defaults).
- A subtle elevated shadow matches the Figma: `0px 20px 12.5px rgba(0,0,0,0.1), 0px 8px 5px rgba(0,0,0,0.1)`.

### Behaviour
- Header layout: left = sidebar toggle (36 px), right = NotificationBell + UserMenuPill cluster (same as today).
- Tab order in the Header: sidebar toggle → notification bell → user menu pill.
- All three controls are keyboard-reachable and have visible `focus-visible` rings consistent with the existing app conventions.
- The shell layout is responsive: at `lg` (1024+) the design is pixel-faithful. Below `lg` the sidebar starts collapsed by default and the user can still toggle it (overlay-style is acceptable but not required for this US — keep it simple: expanded = pushes content; collapsed = removed).

### Implementation notes
- Add a new Zustand store `useUiStore` (`src/lib/stores/ui-store.ts`) with `{ sidebarCollapsed: boolean, toggleSidebar: () => void, setSidebarCollapsed: (v) => void }`. Persist `sidebarCollapsed` to `localStorage` via a thin wrapper analogous to `token-storage.ts` (key `adaasm.ui.sidebarCollapsed`).
- Wrap the existing Radix popover into a new shadcn primitive `src/components/ui/popover.tsx` if it does not exist yet.
- New component `src/features/auth/components/NotificationPanel.tsx` (or move to `src/features/notifications/components/` if we want to anticipate the future US). For this US keep it under `frontend/src/features/notifications/components/NotificationPanel.tsx` so the placeholder data + component live together and the future feed-fed version can replace the data hook without touching the component.
- Update `NotificationBell` to forward the `onOpenChange` to its parent OR self-host the popover; cleanest is to compose `NotificationBell + NotificationPanel` inside a new `NotificationMenu` component that owns the popover state.
- Update `Header.tsx`: read `sidebarCollapsed` from the store; render the toggle on the left (`Menu` icon when collapsed, `X` when expanded); render `NotificationMenu` and `UserMenuPill` on the right.
- Update `DashboardLayout.tsx`: read `sidebarCollapsed`; conditionally render `<Sidebar />` (or render `null` when collapsed).
- Update `Sidebar.tsx`: header renders the real SVG (via `<img src="/brand/singularthings-wordmark.svg" alt="Singular Things" />`, sized to the Figma); nav items rendered in hierarchy order; active state via NavLink's `isActive`.
- The text-based `BrandWordmark` component is kept for the auth pages (LoginPage, ForgotPasswordPage, ResetPasswordPage) — those screens still match Figma `37:2` which uses the large text wordmark. Only the dashboard Sidebar swaps to the SVG.

### Test scenarios (Vitest + Playwright)
- Unit: `ui-store` toggle + persistence round-trip.
- Component: `Sidebar` renders nav items in `Proyectos → Módulos → Componentes` order; clicking an item updates URL.
- Component: `Header` renders the toggle; clicking flips the store's `sidebarCollapsed` value.
- Component: `DashboardLayout` does NOT render the Sidebar when `sidebarCollapsed=true`.
- Component: `NotificationMenu` opens the panel on bell click; Escape closes; outside-click closes.
- Component: panel renders the "Notificaciones" heading, the "2 nuevas" pill, the list of placeholder items with two unread (tinted + dot), and the footer link.
- E2E (`@smoke`): authenticated user lands on `/`; sidebar visible by default; clicks toggle → sidebar hidden; reloads → still hidden (localStorage persisted); clicks bell → panel opens with placeholder data; Escape → closes.

### Out of scope (deferred)
- No real notification feed (backend endpoint, polling, badge counter sync). Future US.
- No `/projects`, `/modules`, `/components` route components — the nav links exist and route but the destination remains the placeholder shell until the respective US.
- No mobile overlay variant — basic collapse only.
- No animation polish beyond the Radix defaults.

## Design References

Figma File:
https://www.figma.com/design/pMUgDI7rbRRzVWLCJhoVnY/ada_asm

Referenced Nodes:
- https://www.figma.com/design/pMUgDI7rbRRzVWLCJhoVnY/ada_asm?node-id=47-14343
- https://www.figma.com/design/pMUgDI7rbRRzVWLCJhoVnY/ada_asm?node-id=47-23460

## Constraints / Notes
- **Domain order overrides the Figma's nav order.** The Figma frame `47:14343` shows the sidebar items as Proyectos → Componentes → Módulos. The user explicitly instructed the implementation to use the domain hierarchy order Proyectos → Módulos → Componentes. This divergence MUST be documented in `design.md` of the resulting OpenSpecs change.
- Notification panel data is hardcoded placeholder copy from the Figma. The component contract MUST be designed so the future "real feed" US replaces the data source (a hook) without touching the rendering component.
- The bell's red status dot stays as a static visual placeholder (introduced in `login-en-asm`).
- The brand logo asset is already at `frontend/public/brand/singularthings-wordmark.svg` (committed in `fa64c91`).
- Frontend-only change: no backend touches, no migrations, no new runtime dependencies beyond `@radix-ui/react-popover` (if not already present from earlier additions).

<!-- END_ENRICHED_USER_STORY -->
