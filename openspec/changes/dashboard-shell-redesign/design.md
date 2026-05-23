## Context

The dashboard chrome shipped with `login-en-asm` is a deliberately minimal placeholder: black header text, hardcoded sidebar items, no toggle, no notification panel. Now we have two locked Figma frames (`47:14343` expanded with notifications open, `47:23460` collapsed) and a real brand logo committed at `frontend/public/brand/singularthings-wordmark.svg`. The current change brings the chrome up to design fidelity before the first business pages start landing on top of it.

The change is **entirely frontend**. There is no backend touch, no migration, no env var. The only new runtime dependency is `@radix-ui/react-popover` (small, mainline Radix primitive, already a transitive dependency of `@radix-ui/react-dropdown-menu`).

## Goals / Non-Goals

**Goals:**

- Pixel-faithful sidebar in both states at `lg`, anchored to Figma `47:14343` / `47:23460`.
- Replace the text wordmark in the sidebar with the real SVG (`frontend/public/brand/singularthings-wordmark.svg`).
- Add an interactive sidebar toggle in the Header with persistence across reloads.
- Make the notification bell interactive: open a panel with placeholder data behind a `useNotifications` hook so the future real-feed US can swap the data source without touching the rendering components.
- Exercise the openspec MODIFIED workflow on a second-order capability (`frontend-auth-shell`) plus a chassis capability (`runnable-skeleton`).

**Non-Goals:**

- No backend changes, no new env, no new database tables, no notification feed API.
- No `/projects`, `/modules`, `/components` business pages — the sidebar's links route there but those routes still render the placeholder shell.
- No mobile-overlay variant. At sub-`lg` the sidebar starts collapsed; the user can still toggle. No drawer animation, no scrim.
- No animation polish beyond Radix defaults.
- No persistence of the notification panel "read" state — items are static; "read" is just a render flag from placeholder data.
- No `unread count` from the backend; the magenta "2 nuevas" pill is computed locally from the placeholder feed.

## Decisions

### D1. Sidebar collapse = remove from layout, not rail mode

The Figma `47:23460` shows a fully blank left edge when collapsed (no sidebar, no rail with icons). The simplest implementation matches that — `<Sidebar />` returns `null` when `sidebarCollapsed` is true; the parent flex / grid reflows naturally.

- **Alternative considered**: rail mode (60-ish px wide with icons only). Rejected because (a) the Figma rules it out and (b) it requires an entirely different sidebar markup with extra states for icon-only items.

### D2. Persistence layer is a separate file, mirroring `token-storage`

`src/lib/ui/sidebar-storage.ts` owns the `adaasm.ui.sidebarCollapsed` key. The Zustand store imports `read/write/clear` from it. This keeps the storage policy in one place (one file to migrate if we move to cookies, sessionStorage, or server-side preferences). Same pattern we already use for the refresh token.

### D3. UI store is separate from the auth store

A new `useUiStore` in `src/lib/stores/ui-store.ts`. We do NOT extend `useAuthStore`. Reasoning:

- Auth and UI have different lifetimes (auth cleared on logout; UI persists).
- A future `usePreferencesStore` (theme, density, table column visibility, etc.) is a more natural neighbour to `useUiStore` than to `useAuthStore`.

### D4. Brand logo is loaded via `<img>` from `/brand/...`, not inlined as a React component

Vite serves `frontend/public/*` at the site root. An `<img src="/brand/singularthings-wordmark.svg" />` is the lowest-friction integration. We avoid `?react` plugin imports (none installed) and avoid inlining the SVG markup in the component (10 KB of paths makes the component file unreadable).

- A small wrapper component (`src/features/branding/components/BrandLogo.tsx`) sets a default size and `alt` so callers can use `<BrandLogo />` instead of typing the `<img>` boilerplate. Future-proof for swapping to a smarter variant (e.g., dark-mode-aware SVG) without touching call sites.

### D5. NotificationMenu composes the bell and the panel

We do NOT modify `NotificationBell` to host the popover itself. Instead, `NotificationMenu` is a new composite component:

```tsx
<NotificationMenu>
  <Popover>
    <Popover.Trigger asChild>
      <NotificationBell />        // unchanged
    </Popover.Trigger>
    <Popover.Content>
      <NotificationPanel />
    </Popover.Content>
  </Popover>
</NotificationMenu>
```

This keeps `NotificationBell` reusable as a passive visual element (current API stays — important because the `frontend-auth-shell` spec still documents the bell's visual contract). The panel and its data hook live in a new feature folder `src/features/notifications/`.

### D6. Placeholder feed is hardcoded in the hook, not stored in a constants file

`useNotifications` returns the placeholder list directly inside the hook implementation. When the real-feed US lands, the entire hook body becomes a `useQuery` call; no other component changes. Storing the placeholder list in a separate `constants.ts` would be premature abstraction.

### D7. Nav-item icons are lucide icons

- Proyectos → `lucide:FolderKanban`
- Módulos → `lucide:Boxes`
- Componentes → `lucide:Cpu`

These are chosen to roughly match the silhouettes in the Figma. If the Figma uses bespoke icons we can swap to inline SVGs later — this is a follow-up polish task, not blocking.

### D8. Nav order: hierarchy wins over the Figma

The Figma frame `47:14343` lists Proyectos → Componentes → Módulos. The user explicitly instructed Proyectos → Módulos → Componentes (domain hierarchy). The override is intentional and documented in proposal.md + the `dashboard-shell` spec. The Figma copy is otherwise honoured.

### D9. The bell's red dot stays as a placeholder

Per the existing `frontend-auth-shell` spec, the red status dot on the bell is a static visual element (introduced in `login-en-asm`). This change does not gate the dot behind real notification state. When the real-feed US lands, the dot will be wired to `unreadCount > 0`.

### D10. Modify `runnable-skeleton` AND `frontend-auth-shell` in this change

Two MODIFIED deltas — one delta file per modified capability — both included in this change's `specs/` folder. They are small, scoped edits to existing requirements (header layout contract + bell interactivity).

## Risks / Trade-offs

- **Risk**: The `<img>` for the brand logo cause a layout shift while the SVG loads. → **Mitigation**: the Sidebar header reserves a fixed height (~77 px) and the `<img>` declares `width=128 height=28` attributes so the browser reserves space at parse time. As an additional safety net we set `decoding="async"` and `loading="eager"` (it's above the fold for authenticated users).
- **Risk**: Sidebar collapse persistence flashes the wrong state on hard refresh while the React tree mounts. → **Mitigation**: read `localStorage` synchronously in the Zustand store's initializer (NOT in a `useEffect`) so the first paint has the correct state.
- **Risk**: The notification popover and the user menu dropdown could overlap if both are anchored to the same Header right edge. → **Mitigation**: both use Radix Portal with their own anchor; they cannot be open simultaneously by user input (separate triggers). If both happen to be open programmatically (test scenario), Radix's z-index defaults handle stacking — no extra work needed.
- **Trade-off**: We hardcode the placeholder feed in the hook. When the real backend lands, the hook will need rewriting AND its tests will change. We accept this — the alternative (mock interface, fake provider, etc.) is heavier than the change itself.
- **Trade-off**: We use `<img>` for the logo instead of inline SVG. Inline would give us CSS-level fill control (e.g., for dark mode). Today we have a single light theme and the logo already has its colours baked in, so the `<img>` is fine. A future "dark mode" US will likely swap to inline + currentColor.

## Migration Plan

This is a frontend-only change. After merge:

1. `git pull`.
2. `cd frontend && pnpm install` (picks up `@radix-ui/react-popover` if not already present).
3. `docker compose up -d --build frontend` to rebuild the static bundle inside the container.
4. Hard-refresh the browser (`Cmd+Shift+R`).

No DB changes, no env changes, no backend rebuild.

Rollback: `git revert` the change commit; the previous chrome (text wordmark, no toggle, no notification panel) returns.

## Open Questions

- **Notification page route**: the "Ver todas las notificaciones" link targets `/notifications`. We do not implement that page in this change; the link just routes to the placeholder shell. Decision deferred to the US that owns the real feed.
- **Icon selection**: lucide icons (`FolderKanban`, `Boxes`, `Cpu`) are best-effort matches for the Figma's nav icons. If those happen to be bespoke artwork we can swap to inline SVGs in a follow-up — the icon swap is one-line per item.
- **Mobile / `<lg` behaviour**: today we default to collapsed below `lg`. We do NOT implement a drawer overlay. A mobile US can revisit this if/when the app is actively used on small screens.
