## 1. Dependencies + base primitives

- [x] 1.1 Add `@radix-ui/react-popover` to `frontend/package.json` runtime deps. Run `pnpm install` and commit `pnpm-lock.yaml`.
- [x] 1.2 Create `frontend/src/components/ui/popover.tsx` — shadcn primitive on top of `@radix-ui/react-popover` (Root / Trigger / Content / Anchor / Portal), mirroring the pattern of `dropdown-menu.tsx` (manual scaffold, no `dlx`).

## 2. UI state + persistence

- [x] 2.1 Create `frontend/src/lib/ui/sidebar-storage.ts` with `read`, `write`, `clear` and the constant `SIDEBAR_COLLAPSED_KEY = "adaasm.ui.sidebarCollapsed"`. Round-trip stores `"true"` / `"false"`. Silently no-ops on SSR / private mode (mirrors `token-storage.ts`).
- [x] 2.2 Create `frontend/src/lib/stores/ui-store.ts` — Zustand store with `{ sidebarCollapsed: boolean, toggleSidebar: () => void, setSidebarCollapsed: (v: boolean) => void }`. Initializer reads `sidebar-storage.read()` synchronously so first paint has the correct value. Every action that mutates `sidebarCollapsed` also calls `sidebar-storage.write(value)`.

## 3. Brand logo wrapper [needs-figma `47:14343`]

- [x] 3.1 Create `frontend/src/features/branding/components/BrandLogo.tsx`: `<img src="/brand/singularthings-wordmark.svg" alt="Singular Things" width={128} height={28} decoding="async" loading="eager" />`. Accepts optional `className` so callers can override sizing.
- [x] 3.2 Verify the asset path: hit `http://localhost:15173/brand/singularthings-wordmark.svg` from the running stack and confirm 200 + `image/svg+xml`.

## 4. Sidebar — expanded + collapsed [needs-figma `47:14343`, `47:23460`]

- [x] 4.1 Update `frontend/src/app/layout/Sidebar.tsx`:
  - Header section ~77 px tall, bottom border `border-border`. Renders `<BrandLogo />` (left-aligned inside 24 px padding-x).
  - `<nav>` below header with three `<NavLink>` items in this order: **Proyectos** (`/projects`, icon `FolderKanban`), **Módulos** (`/modules`, icon `Boxes`), **Componentes** (`/components`, icon `Cpu`).
  - Item shape: 48 px tall, rounded 6 px, 16 px horizontal padding, 12 px gap (icon + label). Active variant: `bg-text-primary text-white`. Inactive: `text-text-primary`. Hover (inactive only): `hover:bg-accent hover:text-accent-foreground`. Focus ring matches Header conventions.
  - Sidebar root: 256 px wide, `bg-white`, `border-r border-border`, full-height flex column.

## 5. DashboardLayout — conditional sidebar render

- [x] 5.1 Update `frontend/src/app/layout/DashboardLayout.tsx`:
  - Reads `sidebarCollapsed` from `useUiStore`.
  - Renders `<Header />` at top (always), then a horizontal flex row containing either `<Sidebar /><main /></main>` (when expanded) or `<main /></main>` only (when collapsed). The `<main>` always grows (`flex-1`).
  - Page background `bg-page-bg` (#fafafa).
  - Ensure `<main>`'s padding matches the Figma (the existing dashboard placeholder content stays untouched inside `<main>`).

## 6. Header — sidebar toggle + slots [needs-figma `47:14343`, `47:23460`]

- [x] 6.1 Update `frontend/src/app/layout/Header.tsx`:
  - Left side: a 36 px button that reads `sidebarCollapsed` from `useUiStore` and on click calls `toggleSidebar`. Icon `lucide:Menu` when collapsed, `lucide:X` when expanded. `aria-label` flips between "Mostrar menú lateral" / "Ocultar menú lateral".
  - Right side: existing `<NotificationBell />` is REPLACED by `<NotificationMenu />` (see Group 7). `<UserMenuPill />` stays as-is.
  - Tab order is naturally: toggle → NotificationMenu trigger → UserMenuPill trigger.
  - Header dimensions and visual styling stay aligned with the Figma (height ~84 px, bg white, bottom border, padding 24 px-x).

## 7. NotificationMenu + NotificationPanel [needs-figma `47:14343`]

- [x] 7.1 Create `frontend/src/features/notifications/types.ts` with the `Notification` type: `{ id: string; title: string; subtitle: string; timestamp: string; read: boolean; }`.
- [x] 7.2 Create `frontend/src/features/notifications/hooks/use-notifications.ts` returning a hardcoded `Notification[]` from the Figma copy (six items, two unread). Computes `unreadCount` inside. Comment notes this is the placeholder source that a future US replaces with a real backend feed.
- [x] 7.3 Create `frontend/src/features/notifications/components/NotificationPanel.tsx`:
  - 384 px wide, white bg, rounded 6 px, border `border-border`, shadow `0px_20px_12.5px_rgba(0,0,0,0.1),0px_8px_5px_rgba(0,0,0,0.1)`.
  - Header section: flex row with `Notificaciones` (Inter Medium 18 px, `text-text-primary`) on the left and a magenta `bg-brand` rounded pill `<unreadCount> nuevas` on the right (hidden when count is 0). 1 px bottom border `border-border`.
  - List: vertical scrollable, max-height ~500 px. Each item ~117 px with bottom divider (no divider on the last). Title 14 px medium, subtitle 12 px regular `text-text-secondary`, timestamp 12 px regular `text-text-secondary`. Unread items: background `bg-brand/5` and a 8 px `bg-brand` dot at top-right.
  - Footer: top border, centred `<Link to="/notifications">Ver todas las notificaciones</Link>` in `text-brand` Inter Medium 14 px.
- [x] 7.4 Create `frontend/src/features/notifications/components/NotificationMenu.tsx`: composes the existing `<NotificationBell />` (unchanged) inside a Radix Popover as Trigger, with `<NotificationPanel />` as Content. Anchor on the right side, sideOffset ~8 px. `<NotificationBell />` remains a "passive" visual component — the composite owns the open/close state.

## 8. Route stubs

- [x] 8.1 In `frontend/src/App.tsx`, ensure routes `/projects`, `/modules`, `/components`, and `/notifications` are declared under the `<RequireAuth />` element. Each route uses the existing placeholder `DashboardLayout` + `PlaceholderPage` content. (Concrete pages are future USs.)

## 9. Vitest unit + component tests

- [x] 9.1 `frontend/src/lib/ui/sidebar-storage.test.ts`: read/write/clear round trip; missing key returns sensible default; SSR-safe no-op (simulate by deleting `window.localStorage`).
- [x] 9.2 `frontend/src/lib/stores/ui-store.test.ts`: initial value reflects `sidebar-storage.read()`; `toggleSidebar` flips and persists; `setSidebarCollapsed(true|false)` persists.
- [x] 9.3 `frontend/src/app/layout/Sidebar.test.tsx`: renders the three items in `Proyectos → Módulos → Componentes` order; active state on the matching `NavLink`; brand logo image has correct `src` and `alt`.
- [x] 9.4 `frontend/src/app/layout/DashboardLayout.test.tsx`: when `sidebarCollapsed=false`, the Sidebar is in the DOM; when `true`, it is NOT.
- [x] 9.5 `frontend/src/app/layout/Header.test.tsx`: clicking the toggle flips `useUiStore.sidebarCollapsed`; icon is `Menu` when collapsed, `X` when expanded; tab order is toggle → bell → pill.
- [x] 9.6 `frontend/src/features/notifications/components/NotificationMenu.test.tsx`: click bell opens panel; Escape closes panel; outside-click closes panel; tab into panel reaches the footer link.
- [x] 9.7 `frontend/src/features/notifications/components/NotificationPanel.test.tsx`: renders six placeholder items; the two unread ones have the magenta dot and the tinted background; the "2 nuevas" pill renders; the footer link `href` ends with `/notifications`.

## 10. Playwright @smoke (extends `frontend/e2e/smoke.spec.ts`)

- [x] 10.1 Add a smoke test: authenticated user lands on `/`. Sidebar visible by default. Click the toggle. Sidebar disappears. Reload the page. Sidebar still hidden (persistence). Click the toggle again. Sidebar reappears.
- [x] 10.2 Add a smoke test: authenticated user lands on `/`. Click the bell. Notification panel opens with `Notificaciones` heading and the `2 nuevas` pill. Press Escape. Panel closes.

## 11. Pre-commit + verification

- [x] 11.1 `pnpm typecheck`, `pnpm lint`, `pnpm test:coverage` (gate ≥ 80 %), `pnpm build` — all green from `frontend/`.
- [x] 11.2 Run `pre-commit run --all-files` — all hooks pass.
- [x] 11.3 Rebuild only the frontend container: `docker compose up -d --build frontend`. Hard-refresh `http://localhost:15173`, sign in, verify the new chrome matches the Figma side-by-side at `lg`. Test toggle + persistence + notification panel manually.
- [x] 11.4 Commit + push to `main` (direct-to-main per project workflow).
- [x] 11.5 Archive the change: `openspec archive dashboard-shell-redesign --yes`. Commit + push the archive.
