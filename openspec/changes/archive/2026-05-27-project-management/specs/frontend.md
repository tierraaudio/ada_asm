# Frontend spec — project-management

## Reuse contract

Every primitive shipped by `module-management` and `component-management` is reused **as-is**. The only refactor on existing code is generalizing `<AddChildModal>` so it accepts a generic `parentId` (the callsite owns which mutation hook to call). The modules callsite is updated in the same change to keep the API uniform.

## Routes

Registered in `App.tsx` (replacing the four `<DashboardPlaceholder label="Proyectos · próximamente" />` placeholders):

- `/projects` → `ProjectsListPage` (Figma 46:3).
- `/projects/new` → `ProjectEditPage mode="create"` (Figma 46:4038).
- `/projects/:id` → `ProjectDetailPage` (Figma 46:878).
- `/projects/:id/edit` → `ProjectEditPage mode="edit"` (Figma 46:4038).

All four pages render inside `<DashboardLayout>` and use the existing sticky `<DetailPageHeader>` (X + `<` `>` nav-stack controls + right action slot).

## File layout

```
frontend/src/features/projects/
  api/
    projects-api.ts         # typed axios methods for /api/v1/projects/*
    customers-api.ts        # /api/v1/customers/*
    config-api.ts           # GET /api/v1/config
  hooks/
    use-projects.ts                  # list with filters
    use-project-detail.ts
    use-project-mutations.ts         # create / update / softDelete / addChild / removeChild
    use-project-price-history.ts
    use-project-stock-events.ts
    use-customers.ts
    use-create-customer.ts
    use-config.ts
    use-projects-using.ts            # exports useComponentProjectsUsing + useModuleProjectsUsing
  pages/
    ProjectsListPage.tsx
    ProjectDetailPage.tsx
    ProjectEditPage.tsx
  components/
    ProjectHeaderCard.tsx
    ProjectStatusBadge.tsx
    CustomerLink.tsx
    CreateCustomerModal.tsx
  types.ts                  # Project, ProjectSummary, ProjectChild, ProjectStatus, Customer, ConfigResponse

frontend/src/features/shared/badges/
  ProjectsHierarchyRow.tsx  # NEW: compact one-line row used by "Usado en proyectos" sections
```

## Reused primitives (no variants)

| Existing | Used for |
|---|---|
| `DashboardLayout` | shell |
| `DetailPageHeader` | sticky X + `<` `>` + right slot |
| `DetailNavStack`, `DetailNavControls`, `useDetailNavPush` | back/forward + auto-push on mount + reset on X |
| `FiltersDrawer` | `status[]` + `customer_id[]` + `include_archived` toggle |
| `DataTablePagination` | list pagination |
| `ConfirmDeleteDialog` | soft-delete dialog (copy: "Mover a Archivados" / confirm "Archivar") |
| `ModulesHierarchyTable` | BOM (directChildren mode, expandable, onRemoveChild in edit) |
| `AddChildModal` | "+ Añadir hijo" finder (generalized — see below) |
| `FamilyChip`, `NatoScoreBadge`, `TierBadge`, `StockStatusBadge`, `NatoScoringSummaryCard` | UI |
| `HistoricoPreciosChart` | price history pane in detail |
| `Tooltip`, `Select`, `Dialog`, `Button` from `@/components/ui` | shadcn primitives |

## New components

### `<ProjectStatusBadge value={status} />`

Pill with 4-colour mapping + hover tooltip explaining the lifecycle:

| Status | Bg / text |
|---|---|
| `Draft` | `bg-muted text-text-secondary` |
| `Active` | `bg-emerald-50 text-emerald-700` |
| `Delivered` | `bg-indigo-50 text-indigo-700` |
| `Archived` | `bg-zinc-100 text-zinc-500` |

Tooltip body lists all four statuses in order and highlights the current one.

### `<CustomerLink customer={Customer} />`

```
<a target="_blank" rel="noopener" href={ holded_url ?? `${config.holded_base_url}/contact/${holded_id}` }>
  <span>{name}</span>
  <span className="font-mono text-xs">{holded_id}</span>
</a>
```

If `useConfig()` is still loading, fall back to disabled text (link rendered as non-anchor span) — don't ship a broken `href`.

### `<ProjectHeaderCard project={ProjectSummary} />`

Mirror of `<ModuleHeaderCard>`:
- Left column: code (mono), name (large), description, `<ProjectStatusBadge>`, `<CustomerLink>`, fechas (inicio, entrega estimada, entrega real if present).
- Right column slot: caller passes `<NatoScoringSummaryCard aggregated={project.aggregated_nato_score} tier={project.aggregated_tier} expiresAt={project.aggregated_expires_at} />` (the existing card already accepts the aggregated shape).

### `<CreateCustomerModal open onOpenChange onCreated />`

Tiny modal called inline from the customer select in `ProjectEditPage`. Fields: `holded_id` (required), `name` (required), `holded_url` (optional), `notas` (optional). On submit → POST `/api/v1/customers`, invalidates `["customers"]` query key, calls `onCreated(newCustomer)`.

### `<ProjectsHierarchyRow project={ProjectSummary} />` (shared)

Compact one-line row used by the "Usado en proyectos" sections on component/module detail. Flat (no expand). Columns: code (mono), name, `<ProjectStatusBadge>`, customer name (clickable link to project, not to Holded — that's the role of `CustomerLink`), aggregates compact (precio_total). Hover row → row gets a subtle bg highlight. Click row → navigates to `/projects/{id}` (push to nav stack via the existing pattern).

A flat list of these rows lives under a single `<section>` with the heading "Usado en proyectos" and a count chip.

## Generalization of `<AddChildModal>`

Today the modal accepts `parentModuleId`. We rename to a kind-agnostic `parentId: string` and let the callsite own which mutation hook to call.

- New prop shape:
  ```tsx
  interface AddChildModalProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    parentId: string;              // was parentModuleId
    parentLabel?: string;          // optional header copy ("al módulo X" / "al proyecto Y")
    existingChildren: ChildSummary[];  // unchanged shape — array of {id, child_module_id?, child_component_id?}
    onConfirm: (input: { child_module_id?: string; child_component_id?: string; quantity: number }) => Promise<void>;
  }
  ```
- `ModuleEditPage` callsite updated in the same change: passes `parentId={module.id}` + uses `useAddChild()` from modules hooks.
- `ProjectEditPage` callsite: passes `parentId={project.id}` + uses `useAddProjectChild()`.
- No discriminator inside the modal — keeps the primitive simple and reusable.

## Pages

### `ProjectsListPage` — Figma 46:3

Standardised layout (matches `ComponentsListPage` / `ModulesListPage`):

- Header: title + subtitle.
- Toolbar row: search input + `<FiltersDrawer>` + "+ Nuevo proyecto" button.
- `<FiltersDrawer>` groups:
  - `status` — checkboxes for `Draft | Active | Delivered | Archived`.
  - `customer_id` — checkboxes generated from `useCustomers()`.
  - `include_archived` — single toggle ("Incluir archivados"). When ON, sends `?include_archived=true`.
- Table columns: Código (mono), Nombre, Cliente (CustomerLink compact — name + holded_id chip), Estado (badge), NATO agregado, Tier, Precio total, Fecha entrega estimada, Acciones (ver + borrar (soft-delete)).
- Default rows exclude `Archived`. The toggle flips this.
- Loading / error / empty states (consistent with other lists).
- Pagination via `<DataTablePagination>`.

### `ProjectDetailPage` — Figma 46:878

- Sticky `<DetailPageHeader closeTo="/projects" rightSlot={<EditarBtn /> + <BorrarBtn />}>` where `BorrarBtn` opens `<ConfirmDeleteDialog>` for soft-delete.
- `<ProjectHeaderCard project={project} />` with `NatoScoringSummaryCard` in the right slot.
- Section "Contiene" with `<ModulesHierarchyTable directChildren={project.children} expandable emptyMessage="Este proyecto no contiene módulos ni componentes." />`.
- Section "Histórico de precios" — `<HistoricoPreciosChart points={priceHistory.points} />` + week/month/year toggle.
- Section "Histórico de eventos" — table of `stock_events` from `useProjectStockEvents(id)` (project-scoped consumption rows; ordered by date desc).

### `ProjectEditPage` — Figma 46:4038

Same shape as `ModuleEditPage` / `ComponentEditPage`:

- Sticky `<DetailPageHeader>` with X (resets nav stack, navigates to `/projects` in create / `/projects/:id` in edit) + nav controls + right slot `Cancelar` + `Crear proyecto` / `Guardar cambios`.
- Form fields (react-hook-form + zod, same patterns as the other edit pages):
  - Código (required, max 40)
  - Nombre (required, max 200)
  - Descripción (textarea)
  - Estado (Select, the 4 statuses)
  - Cliente (Select from `useCustomers()` + "+ Nuevo cliente" link inline → `<CreateCustomerModal>`)
  - Fecha inicio (date input)
  - Fecha entrega estimada (date input)
  - Fecha entrega real (date input) — visible only when `Estado === "Delivered"`. If user moves to Delivered without filling it, the BE auto-sets it to today.
  - Notas (textarea)
- Audit strip in edit (Fecha de creación / Última modificación).
- Section "Contiene" with `<ModulesHierarchyTable directChildren onRemoveChild />` + "+ Añadir hijo" button opening `<AddChildModal>`.
- Create-mode "+ Añadir hijo" hand-off: same pattern as `ModuleEditPage` — submit form first (POST), then navigate to `/projects/{newId}/edit?add_child=1`, then a `useEffect` on the edit page detects the query param + opens the modal once the detail loads.

## "Usado en proyectos" sections (cross-feature)

### `ComponentDetailPage`

Below the existing "Pertenece a" section (which lists module parents), add a new section:

```tsx
<section className="rounded-lg border border-border bg-white p-4 shadow-sm">
  <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-text-secondary">
    Usado en proyectos
  </h2>
  {projectsUsing.isLoading ? (
    <p className="text-sm text-text-secondary">Cargando proyectos…</p>
  ) : projectsUsing.data && projectsUsing.data.length > 0 ? (
    <ul className="divide-y divide-border">
      {projectsUsing.data.map((p) => (
        <li key={p.id}>
          <ProjectsHierarchyRow project={p} />
        </li>
      ))}
    </ul>
  ) : (
    <p className="text-sm text-text-secondary">
      Este componente no se usa todavía en ningún proyecto.
    </p>
  )}
</section>
```

Hook: `useComponentProjectsUsing(id)`.

### `ModuleDetailPage`

Identical structure, fed by `useModuleProjectsUsing(id)`. Empty copy: "Este módulo no se usa todavía en ningún proyecto.".

## TanStack Query hooks

Single-endpoint wrappers, mirroring the modules hooks shape:

```ts
useProjects({ filters, page, pageSize })      → ["projects", "list", { ... }]
useProjectDetail(id)                          → ["projects", "detail", id]
useCreateProject()                            → POST + invalidates ["projects","list"]
useUpdateProject()                            → PATCH + invalidates detail + list
useDeleteProject()                            → DELETE (soft) + invalidates list + sets status=Archived locally
useAddProjectChild()                          → POST + invalidates detail + relevant "projects-using"
useRemoveProjectChild()                       → DELETE edge + same invalidations
useProjectPriceHistory(id, period, enabled)   → ["projects", "price-history", id, period]
useProjectStockEvents(id, enabled)            → ["projects", "stock-events", id]

useCustomers()                                → ["customers", "list"]
useCreateCustomer()                           → POST + invalidates ["customers","list"]

useComponentProjectsUsing(componentId)        → ["components", "projects-using", componentId]
useModuleProjectsUsing(moduleId)              → ["modules", "projects-using", moduleId]

useConfig()                                   → ["config"] with long staleTime (10 min)
```

## Copy

- All user-visible copy in Spanish (titles, buttons, empty states, error banners).
- Code, comments, logs in English.
- Status badge labels are EXACTLY the enum values (`Draft`, `Active`, `Delivered`, `Archived`) — no translation, to match how the data is stored.
- "Pertenece a" stays for the module-parent list on Component/Module detail. The new section is "Usado en proyectos" so there's zero ambiguity about which surface the row drives.

## Sidebar

`Sidebar.tsx` already has "Proyectos" with the `FolderKanban` icon as the first nav item. No changes needed — the active-route highlight already works because we computed it from `useLocation()` in the module-management change.

## Tests

### Component tests (Vitest)

- `<ProjectStatusBadge>`: each of the 4 statuses renders the right colour and label; tooltip lists all four.
- `<CustomerLink>`: URL built from `useConfig()`; explicit `holded_url` overrides; absence of config gracefully renders disabled text.
- `<ProjectHeaderCard>`: all fields present; right slot accepts arbitrary node.
- `<ProjectsHierarchyRow>`: renders code + name + status; click navigates.

### Page tests (Vitest)

- `ProjectsListPage`:
  - default request to `/projects` does NOT include Archived rows (assert MSW handler called without `include_archived`).
  - toggling "Incluir archivados" re-fetches with the param.
  - search input debounce + URL sync.
  - empty state.
- `ProjectEditPage`:
  - create-mode form validation (code required).
  - edit-mode prefill.
  - "+ Añadir hijo" in create-mode triggers save-and-continue (intercept POST, expect navigate to `/projects/{newId}/edit?add_child=1`).
- `ProjectDetailPage`:
  - BOM table renders rows from `useProjectDetail`.
  - "Usado en proyectos" empty + populated.
  - soft-delete dialog copy ("Mover a Archivados" + "Archivar"). Confirming calls DELETE + invalidates list.

### Hook tests

- `useProjects`: filters / pagination state propagates correctly to the query key.

### E2E (Playwright `@smoke`)

- Full create flow including "+ Añadir hijo" via the finder.
- Navigate from a `ComponentDetailPage` → "Usado en proyectos" → project detail; assert the nav stack `<` `>` records the jump.
- Soft-delete: archive a project → it disappears from default list → toggle "Incluir archivados" → it reappears with the Archived badge.
