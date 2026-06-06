# Project management — design

## Diseño de datos

### `customers`

Tabla mínima id-link contra Holded. Se llena por seed ahora y por la US futura de "Holded sync"; no tiene UI propia en este change más allá del select + modal inline en el edit de proyecto.

| Columna | Tipo | Notas |
|---|---|---|
| `id` | UUIDv4 PK | `server_default gen_random_uuid()` |
| `holded_id` | `varchar(64)` NOT NULL | Identificador Holded. UNIQUE case-insensitive vía `lower(holded_id)`. |
| `name` | `varchar(200)` NOT NULL | Denormalizado para sobrevivir caídas / renames de Holded. |
| `holded_url` | `varchar(500)` NULL | Override explícito. Si NULL, el FE construye `${HOLDED_BASE_URL}/contact/{holded_id}`. |
| `notas` | `text` NULL | |
| `created_at` / `updated_at` | `timestamptz` | |

**Indexes**: `uq_customers_holded_id_lower (lower(holded_id))`.

### `projects`

Top de la jerarquía. `code` lo escribe el usuario (no auto-generado, es la identidad de negocio). El `status` es enum DB-enforced. Borrar = soft-delete (transición a `Archived`).

| Columna | Tipo | Notas |
|---|---|---|
| `id` | UUIDv4 PK | |
| `code` | `varchar(40)` NOT NULL | Único case-insensitive vía `lower(code)`. Editable; nada referencia `code`. |
| `name` | `varchar(200)` NOT NULL | |
| `description` | `text` NULL | |
| `status` | `varchar(20)` NOT NULL DEFAULT `'Draft'` | CHECK in `('Draft', 'Active', 'Delivered', 'Archived')`. |
| `customer_id` | UUIDv4 NULL | FK → `customers.id` ON DELETE SET NULL. |
| `fecha_inicio` | `date` NULL | |
| `fecha_entrega_estimada` | `date` NULL | |
| `fecha_entrega_real` | `date` NULL | Se auto-rellena al pasar a `Delivered` si no se pasó explícito. |
| `notas` | `text` NULL | |
| `created_at` / `updated_at` | `timestamptz` | |

**Indexes**: `uq_projects_code_lower (lower(code))`, `ix_projects_name_lower (lower(name))`, `ix_projects_status (status)`, `ix_projects_customer_id (customer_id)`.

### `project_children`

Espejo exacto de `module_children`: arista polimórfica XOR a módulo o componente, con partial UNIQUE indexes por par parent+hijo. Sin cycle detection porque los proyectos no son hijos de nadie.

| Columna | Tipo | Notas |
|---|---|---|
| `id` | UUIDv4 PK | |
| `parent_project_id` | UUIDv4 NOT NULL | FK → `projects.id` ON DELETE CASCADE |
| `child_module_id` | UUIDv4 NULL | FK → `modules.id` ON DELETE CASCADE |
| `child_component_id` | UUIDv4 NULL | FK → `components.id` ON DELETE CASCADE |
| `quantity` | `smallint` NOT NULL CHECK `> 0` | Repetir hijo = subir `quantity`. |
| `sort_order` | `integer` NOT NULL DEFAULT 0 | |
| `notes` | `text` NULL | |
| `created_at` / `updated_at` | `timestamptz` | |

**Constraints**:
- CHECK XOR: `(child_module_id IS NOT NULL)::int + (child_component_id IS NOT NULL)::int = 1`.

**Partial UNIQUE**:
- `uq_project_children_parent_child_module (parent_project_id, child_module_id) WHERE child_module_id IS NOT NULL`.
- `uq_project_children_parent_child_component (parent_project_id, child_component_id) WHERE child_component_id IS NOT NULL`.

**Non-unique indexes**: `(parent_project_id, sort_order)`, `(child_module_id)`, `(child_component_id)`.

### Migración sobre `stock_events`

`stock_events.project_id` existía como `uuid NULL` sin FK (la entidad no existía). Esta change materializa la FK:

```sql
ALTER TABLE stock_events
  ADD CONSTRAINT fk_stock_events_project
  FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE SET NULL;
```

`stock_events.project_name_snapshot` y los campos `customer_*_snapshot` se mantienen sin tocar — el ledger es append-only y debe sobrevivir borrados / renames.

## Agregaciones

`ProjectService.compute_aggregates(project_id, *, project_quantity_in_root=1)` reusa la fórmula del módulo. Walk recursivo:

```
project_children → module_children (recursivo, ya soportado por ModuleService) → components (hojas)
project_children → components (rama directa hoja)
```

Para cada componente hoja, propagamos la cantidad efectiva (`project_qty × module_qty × ... × component_qty`).

**Outputs** (todos NULL si el proyecto está vacío, `buildable_stock=0`):

- `precio_total` (Decimal EUR): `Σ leaf_qty_propagated × leaf.current_price_per_100_eur / 100`.
- `aggregated_nato_score`: MIN lexicográfico (`F < D < C < B < A < A+`) entre hojas.
- `aggregated_tier`: MIN numérico (Tier 1 = peor).
- `aggregated_expires_at`: MIN de `expires_at` de las clasificaciones activas.
- `buildable_stock`: cuántas unidades enteras del proyecto se pueden ensamblar dado el stock actual. Para hijos módulo: `min(module.stock // module_qty_required, recursive_buildable(module))`. Para hijos componente: `component.stock // component_qty_required`. El proyecto entero es el `MIN` sobre todas las ramas.

**Performance**: la consulta se mantiene en un `WITH RECURSIVE` con `depth_limit = 8` (igual que módulos). N+1 evitado para `current_price_per_100_eur` y `supplier_stock_summary` reutilizando el `_hydrate_current_prices` y `latest_summary_for_components` ya existentes en el componente repo.

## Servicios y errores

- `ProjectService` (mirror de `ModuleService`): `list_projects`, `get_detail` (bundle: project + aggregates + children + customer summary), `create`, `update`, `soft_delete`, `add_child`, `update_child`, `remove_child`, `compute_aggregates`, `list_price_history`, `list_stock_events`.
- `CustomerService`: `list`, `get`, `create`, `update`, `delete`.
- Errores RFC 7807 con códigos estables:
  - `PROJECT_NOT_FOUND` (404), `PROJECT_CODE_ALREADY_REGISTERED` (409), `INVALID_CHILD_REFERENCE` (422), `CHILD_ALREADY_PRESENT` (422), `INVALID_STATUS_TRANSITION` (422, p.ej. no permitido revertir de `Archived` sin `include_archived` flag explícito; mantengo simple — permitimos todas las transiciones por ahora).
  - `CUSTOMER_NOT_FOUND` (404), `CUSTOMER_HOLDED_ID_ALREADY_REGISTERED` (409).

## API surface

Toda autenticada con `Depends(require_user)`, errores RFC 7807. Layout exacto en `specs/api.md`.

**Projects**: `GET/POST /api/v1/projects`, `GET/PATCH/DELETE /api/v1/projects/{id}` (DELETE = soft-delete), `GET/POST /api/v1/projects/{id}/children`, `PATCH/DELETE /api/v1/projects/{id}/children/{child_id}`, `GET /api/v1/projects/{id}/price-history`, `GET /api/v1/projects/{id}/stock-events`.

**Customers**: CRUD completo en `/api/v1/customers/*`.

**Cross-feature**: `GET /api/v1/components/{id}/projects-using`, `GET /api/v1/modules/{id}/projects-using` — devuelven `ProjectSummary[]` (sin children, con aggregates) para alimentar la nueva sección "Usado en proyectos".

**Config**: `GET /api/v1/config` → `{holded_base_url}` para que el FE construya el link a Holded sin baked-in URL.

## Frontend — composición

### Estructura

```
features/projects/
  api/projects-api.ts           # axios + tipos compartidos con BE
  api/customers-api.ts
  api/config-api.ts
  hooks/use-projects.ts         # list + filtros (status, customer, include_archived)
  hooks/use-project-detail.ts
  hooks/use-project-mutations.ts # create / update / soft-delete / add-child / remove-child
  hooks/use-project-price-history.ts
  hooks/use-project-stock-events.ts
  hooks/use-customers.ts
  hooks/use-create-customer.ts
  hooks/use-config.ts            # cacheado long-stale
  hooks/use-projects-using.ts    # devuelve dos hooks: useComponentProjectsUsing, useModuleProjectsUsing
  components/ProjectHeaderCard.tsx
  components/ProjectStatusBadge.tsx
  components/CustomerLink.tsx
  components/CreateCustomerModal.tsx
  pages/ProjectsListPage.tsx
  pages/ProjectDetailPage.tsx
  pages/ProjectEditPage.tsx
  types.ts                      # Project, ProjectSummary, ProjectChild, ProjectStatus, Customer

features/shared/badges/ProjectsHierarchyRow.tsx   # NUEVO compartido (lista plana)
```

### Reutilización (sin variantes nuevas)

| Existente | Reutilizado para |
|---|---|
| `DashboardLayout`, `DetailPageHeader`, `DetailNavStack` / Controls | layout + sticky bar + back/forward |
| `FiltersDrawer` | `status[]` + `customer_id[]` + `include_archived` toggle |
| `DataTablePagination` | lista de proyectos |
| `ConfirmDeleteDialog` | soft-delete dialog (copy "Mover a Archivados", confirm "Archivar") |
| `ModulesHierarchyTable` (con `directChildren` + `onRemoveChild`) | BOM en detail + edit |
| `AddChildModal` | finder "+ Añadir hijo" — generalizado a `parentId`+`parentKind: 'module' \| 'project'` |
| `FamilyChip`, `NatoScoreBadge`, `TierBadge`, `StockStatusBadge`, `NatoScoringSummaryCard` | UI compartida |
| `HistoricoPreciosChart` | gráfico de precio histórico del proyecto (single line, modo agregado) |

### Páginas

- **ProjectsListPage** (Figma 46:3): header + search input + FiltersDrawer (`status[]`, `customer_id[]`, `include_archived` toggle) + botón "+ Nuevo proyecto" + tabla con columnas Código · Nombre · Cliente · Estado (badge) · NATO agregado · Tier · Precio total · Fecha entrega estimada · Acciones (ver + borrar). Filas Archived se excluyen por defecto.
- **ProjectDetailPage** (Figma 46:878): sticky `DetailPageHeader` con "Editar proyecto" + `ProjectHeaderCard` (left meta · right `NatoScoringSummaryCard`) + "Contiene" usando `<ModulesHierarchyTable directChildren expandable />` + "Histórico de precios" (chart) + "Histórico de eventos" (tabla de stock_events del proyecto).
- **ProjectEditPage** (Figma 46:4038): misma forma que `ModuleEditPage` / `ComponentEditPage`. Form fields: Código (required, mutable), Nombre, Descripción, Estado (Select), Cliente (Select con inline `+ Nuevo cliente` → `CreateCustomerModal`), Fecha inicio, Fecha entrega estimada, Fecha entrega real (visible solo si Estado=`Delivered`; auto-set a hoy al guardar si está vacía), Notas. Audit strip en edit. "Contiene" con `<ModulesHierarchyTable directChildren onRemoveChild />` + "+ Añadir hijo" → `<AddChildModal>`. En create mode, "+ Añadir hijo" hace save-and-continue (POST proyecto → navigate `/projects/{newId}/edit?add_child=1` → modal auto-abre on load).

### "Usado en proyectos" — secciones nuevas en pantallas existentes

- En `ComponentDetailPage`, debajo de "Pertenece a", nueva sección "Usado en proyectos" alimentada por `useComponentProjectsUsing(id)` → renderiza `<ProjectsHierarchyRow>` por proyecto. Click navega → `/projects/{id}` (entra en el nav stack `<` `>`). Empty: "Este componente no se usa todavía en ningún proyecto".
- Idem en `ModuleDetailPage`.

### Generalización de `AddChildModal`

Hoy `AddChildModal` acepta `parentModuleId`. Propongo dos opciones (definir antes de tocar):

1. **Renombre + discriminator**: `parentId: string` + `parentKind: 'module' | 'project'`. El modal usa `parentKind` para la copy ("Añadir hijo al módulo X" vs "al proyecto X") y para invocar el endpoint correcto (`/modules/{id}/children` vs `/projects/{id}/children`). El callsite de modules se actualiza en el mismo change.
2. **Render-prop / inyección del mutate**: el modal recibe `onConfirm` con la firma payload + handler. Hoy ya es así; solo cambia el nombre `parentModuleId` → `parentId` para reducir acoplamiento. El padre orquesta qué hook llamar.

**Elegido**: opción 2 (menos invasiva). El modal pasa a recibir `parentId` (sin discriminator) + `onConfirm`. La copy del header recibe un prop opcional `parentLabel`. El responsable del endpoint correcto es el callsite. Esto evita meter conocimiento de "qué tipo de padre" dentro del primitive compartido.

## Soft-delete UX

- Botón "Borrar" en la fila de lista y en el detail page → abre `<ConfirmDeleteDialog>` con copy "Mover a Archivados" / confirm "Archivar".
- BE: `DELETE /api/v1/projects/{id}` → `status='Archived'`, 204.
- Lista por defecto excluye `Archived`. La barra de filtros tiene un toggle "Incluir archivados" → re-fetch con `?include_archived=true`. Archivados aparecen con su badge gris.
- Para "desarchivar": el usuario va al detail (vía toggle), pulsa Editar, cambia el `Estado` a algo distinto, guarda. No hay un botón "Unarchive" dedicado en este change.

## Customers — flujo mínimo

- Edit form: Select `Cliente` poblado desde `useCustomers()`. Junto al select, un botón `+ Nuevo cliente` abre `CreateCustomerModal` (campos: `holded_id` required, `name` required, `holded_url` opcional, `notas` opcional). Al confirmar, hace POST a `/api/v1/customers`, invalida el query key, selecciona el cliente recién creado.
- `CustomerLink` renderiza un `<a target="_blank" rel="noopener" href={config.holded_base_url + "/contact/" + holded_id}>{name}</a>` con un chip pequeño del `holded_id`. Sin tooltip extra (mantiene el patrón de FamilyChip).

## Sidebar / routing

- `Sidebar.tsx` ya tiene "Proyectos" como entrada con `FolderKanban`. Al pintar la ruta `/projects` con `ProjectsListPage`, queda destacado en negro automáticamente (no requiere cambios).
- `App.tsx`: reemplazar `<DashboardPlaceholder label="Proyectos · próximamente" />` por las 4 rutas.

## Seguridad / autorización

- Todos los endpoints con `Depends(require_user)`. No hay scoping por proyecto en este change — el modelo de membership se postpone a la US futura "Project memberships & roles".

## Decisiones explícitas

- **`code` mutable, sin auto-gen**: confirmado por usuario; el usuario controla la identidad legible.
- **Soft-delete vs hard-delete**: confirmado soft. El ledger histórico (`stock_events.project_id`) sobrevive.
- **Customer como tabla aparte con id-link**: confirmado. No replicamos contactos Holded ni datos sensibles.
- **"Usado en proyectos"**: sección separada (no tab dentro de "Pertenece a"). Confirma claridad: módulos pueden ser padres, proyectos solo "use" del componente/módulo.
- **Memberships fuera de scope**: confirmado.
- **`AddChildModal` generalizado**: discriminator-less (el padre orquesta el endpoint).

## Alternativas consideradas

- **Tabla genérica `tree_edges` con padre polimórfico** (project_id XOR module_id): atractivo a largo plazo pero rompería las queries recursivas existentes y migrar `module_children` introduce riesgo. Rechazado en favor de `project_children` separado — la duplicación de schema es mínima y la simplicidad operativa gana.
- **`status` como tabla aparte**: descartado, son 4 valores estables.
- **Auto-generación de `code`** (`PRY-YYYY-NNN`): rechazada por petición explícita del usuario (preferencia: el equipo aporta el código).
- **Hard-delete con bandera `force=true`**: fuera de scope; podemos añadir más tarde si aparece la necesidad.
