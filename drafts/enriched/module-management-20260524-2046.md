<!-- BEGIN_ENRICHED_USER_STORY -->
# Enriched User Story

design-linked: true
scope:
  backend: true
  frontend: true
source: Manual
reference: N/A — backlog US (Módulos) · Figma 46:5593 / 46:10347 / 47:11452 / 47:12460

## Title
Module management — catálogo + árbol jerárquico (módulos + componentes) + agregaciones de precio/NATO/Tier + edición + picker reutilizando componentes UI

## Problem / Context
Los módulos son el nivel intermedio del árbol Proyecto → Módulo → Componente. Hoy `/modules` es solo un placeholder; el equipo no puede modelar ensamblajes reusables ni ver el precio total que cuesta producir uno. El Figma tiene 4 pantallas que cubren el ciclo completo:

- Lista (Figma **46:5593**) — tabla jerárquica expandible con módulos y sus componentes hijos en el mismo nivel visual; columnas Nombre · Tipo · SKU · Ubicación · Versión · Precio · Stock · NATO · Acciones.
- Detalle (Figma **46:10347**) — header card del módulo con metadatos + precio total + NATO/Tier agregado + tabla "Contiene" + sección "Pertenece a" (padres).
- Edición (Figma **47:11452**) — formulario con los mismos campos del header + tabla "Contiene" editable con botón "+ Añadir componente".
- Picker (Figma **47:12460**) — modal "Añadir componente" listando el catálogo + opcionalmente sub-módulos; los ya añadidos aparecen greyed con badge "Ya añadido". El usuario pidió expresamente extender el modal con buscador + filtros equivalentes al catálogo de componentes (`ComponentsFiltersDrawer`).

Los módulos son un **catálogo reusable** (no instancias de proyecto). El mismo módulo o componente puede ser hijo de N padres distintos (estructura DAG). Cada relación lleva una **cantidad** explícita.

## Desired Outcome
Un usuario autenticado puede: abrir `/modules`, ver la tabla con módulos expandibles, buscar y entrar al detalle; crear un módulo nuevo en `/modules/new`; abrir `/modules/:id/edit` y modificar metadatos, añadir/eliminar hijos con cantidad, ajustar versión; ver el precio total agregado (suma recursiva de `precio_hijo × cantidad`) con tooltip de desglose; ver el `nato_score` y `tier` agregados como "los más arriesgados" de los hijos (Score min léxico `F<D<C<B<A<A+`, Tier MIN numérico donde Tier 1 = más crítico); ver un histórico de precios del módulo (serie temporal agregada servida por BE) que reutiliza el componente `HistoricoPreciosChart` de componentes. La sidebar de "Módulos" pasa de placeholder a página real.

## Acceptance Criteria (raw)

### Modelo de datos (decisiones validadas con el usuario)

- **Quantity por hijo**: explícita (columna `quantity SMALLINT NOT NULL CHECK > 0`) en la fila de la relación. El precio agregado multiplica por la cantidad.
- **Reuso (DAG)**: un módulo o un componente puede ser hijo de N padres. La sección "Pertenece a" lista todos los padres. No hay restricción de "1 padre".
- **Detección de ciclos**: validación en BE al añadir un módulo como hijo — si el `child_module_id` está en el cierre transitivo de los descendientes del candidato, rechazar 422 `MODULE_CYCLE_DETECTED`.
- **Scoring OTAN del módulo**: AGREGADO PURO. No hay tabla `module_nato_scorings`. El detalle computa al vuelo:
  - `nato_score = MIN(hijos_recursivos)` con orden léxico `F < D < C < B < A < A+`
  - `tier = MIN(hijos_recursivos)` (numérico — Tier 1 = más arriesgado)
  - `expires_at = MIN(hijos_recursivos.current_nato_scoring.expires_at)`, null-safe
  - Tooltip on hover del badge: muestra qué hijo contribuye el peor score/tier y la fecha de caducidad más próxima.
- **Stock del módulo**:
  - Campo editable `stock INTEGER NOT NULL DEFAULT 0` — módulos ya ensamblados en almacén.
  - Tooltip derivado (computado al vuelo, no persistido): "puedes ensamblar N más" = `min(hijo.stock // hijo.quantity_requerido)` agregando recursivamente.
- **Clave de negocio**: `sku` único case-insensitive vía índice funcional `lower(sku)`. No hay `mpn`.
- **Histórico de precios agregado**: endpoint BE `GET /api/v1/modules/{id}/price-history` que devuelve la serie (fecha, precio_total) agregando recursivamente — para cada fecha, suma `quantity × precio_vigente_hijo_a_esa_fecha` (usando `supplier_prices` del proveedor preferente del componente al `qty_tier=100`).

### Backend

- Nueva tabla `modules`:
  - `id` UUIDv4, PK
  - `sku` `varchar(100)`, not null — unique funcional `lower(sku)`
  - `name` `varchar(200)`, not null
  - `description` `text`, nullable
  - `version` `varchar(40)`, not null, default `'v1.0'`
  - `fabricante` `varchar(120)`, nullable
  - `location` `varchar(100)`, nullable — ubicación física en almacén (e.g. `G-M-01`)
  - `tipo_almacenamiento` `varchar(80)`, nullable — FE-enforced enum `Gaveta | Almacén`
  - `stock` `integer`, not null, default `0` — módulos ya ensamblados
  - `notas` `text`, nullable
  - `fecha_creacion` `date`, nullable
  - `created_at` / `updated_at` `timestamptz`
- Nueva tabla `module_children`:
  - `id` UUIDv4, PK
  - `parent_module_id` UUIDv4, FK → `modules.id` ON DELETE CASCADE
  - `child_module_id` UUIDv4, FK → `modules.id` ON DELETE CASCADE, nullable
  - `child_component_id` UUIDv4, FK → `components.id` ON DELETE CASCADE, nullable
  - `quantity` `smallint`, not null, CHECK `> 0`
  - `sort_order` `integer`, not null, default `0`
  - `notes` `text`, nullable
  - `created_at` / `updated_at` `timestamptz`
  - CHECK `(child_module_id IS NOT NULL) <> (child_component_id IS NOT NULL)` (XOR — un hijo es módulo o componente, no los dos)
  - CHECK `child_module_id <> parent_module_id` (no self-reference directa)
  - UNIQUE `(parent_module_id, child_module_id) WHERE child_module_id IS NOT NULL` y UNIQUE `(parent_module_id, child_component_id) WHERE child_component_id IS NOT NULL` (un mismo hijo no se duplica — si necesitas N, va en `quantity`)
  - Índices: `(parent_module_id, sort_order)`, `(child_module_id)`, `(child_component_id)`
- Migración Alembic aplica + reverse cleanly.
- Domain entities `Module` (frozen dataclass) y `ModuleChild` en `backend/app/domain/entities/`. Repository Protocol `ModuleRepository`.
- Implementación SQLAlchemy del repositorio.
- Servicio `ModuleService` con métodos:
  - `list(filters, page, page_size)` — paginado + búsqueda
  - `get_tree(module_id)` — devuelve el módulo + sus hijos recursivos (limitado a una profundidad razonable, e.g. 8, para evitar runaway)
  - `get_with_aggregates(module_id)` — devuelve `Module` + computed `precio_total`, `aggregated_nato_score`, `aggregated_tier`, `aggregated_expires_at`, `buildable_stock`, lista de padres
  - `create(payload)`
  - `update(module_id, payload)`
  - `delete(module_id)` — 204
  - `add_child(module_id, payload)` — valida no-cycle + tipo único
  - `remove_child(module_id, child_id)`
  - `update_child_quantity(module_id, child_id, quantity)`
  - `list_price_history(module_id, period)` — serie temporal agregada
- Pydantic schemas:
  - `ModuleResponse` (con agregados hidratados server-side)
  - `ModuleSummaryResponse` (subset para filas de tabla `parents`)
  - `ModuleChildResponse` (con `child_module: ModuleSummaryResponse | null` O `child_component: ComponentSummaryResponse | null` hidratado)
  - `ModuleTreeResponse` (recursivo, profundidad limitada)
  - `ModuleCreateRequest`, `ModuleUpdateRequest`
  - `AddChildRequest` (`child_module_id` XOR `child_component_id` + `quantity` ≥ 1)
  - `UpdateChildQuantityRequest`
  - `ModulePriceHistoryResponse` (`Array<{ date: string; price: string }>`)
- Endpoints (todos protegidos con `require_user`):
  - `GET    /api/v1/modules` — paginado, `?q=` (matches lower(sku)/lower(name)/lower(description) ILIKE), `?page`, `?page_size` (default 25, max 100). Cada item lleva `aggregated_*` hidratados.
  - `POST   /api/v1/modules` — 201; 409 `MODULE_SKU_ALREADY_REGISTERED` en duplicado.
  - `GET    /api/v1/modules/{id}` — 200 con `ModuleResponse` (incluye agregados, lista de `children` con su componente/módulo hidratado, lista de `parents`).
  - `PATCH  /api/v1/modules/{id}` — actualización parcial. `id`, `created_at`, `updated_at` inmutables.
  - `DELETE /api/v1/modules/{id}` — 204; idempotente.
  - `GET    /api/v1/modules/{id}/tree` — árbol recursivo limitado a depth=8.
  - `POST   /api/v1/modules/{id}/children` — 201 + 422 `MODULE_CYCLE_DETECTED` / 422 `CHILD_ALREADY_PRESENT` / 422 `INVALID_CHILD_REFERENCE`.
  - `PATCH  /api/v1/modules/{id}/children/{child_id}` — actualiza `quantity` / `notes`.
  - `DELETE /api/v1/modules/{id}/children/{child_id}` — 204; idempotente.
  - `GET    /api/v1/modules/{id}/price-history?period=year|month|week` — serie temporal agregada.
- Errores RFC 7807 con códigos estables: `MODULE_NOT_FOUND`, `MODULE_SKU_ALREADY_REGISTERED`, `MODULE_CYCLE_DETECTED`, `CHILD_ALREADY_PRESENT`, `INVALID_CHILD_REFERENCE`.
- Nuevo script `python -m app.scripts.seed_modules` que inserta los módulos del Figma (`Módulo Sensor Ambiental`, `Sistema Potencia BLDC`, `Etapa Driver`) con sus hijos componentes y sub-módulos; al menos un caso de DAG (un mismo componente reusado en dos módulos). Idempotente (refuse + `--reset`).
- Tests pytest (gate 80%):
  - Unit: `ModuleService` con repos mockeados — validación de ciclos (3 niveles), XOR de hijos, cantidad ≥ 1.
  - Unit: cálculo de agregados (precio recursivo con quantities, MIN tier, MIN score, MIN expires_at, buildable_stock).
  - Integration: cada endpoint — happy + 401 + 404 + 422 + 409.
  - Seeder: happy + refuse + reset.

### Frontend

#### Refactor / componentes compartidos (movimientos previos al feature)

Como parte de este change movemos primero los componentes reutilizables de `frontend/src/features/components/components/` a un módulo neutro `frontend/src/components/feature/` (o equivalente) para que módulos los consuma sin acoplarse a la feature de componentes. Si el movimiento es pesado, la alternativa es re-export desde `features/shared/`:

- `DataTablePagination` (ya está en `src/components/ui/`) → se mantiene.
- `NatoScoreBadge`, `TierBadge`, `StockStatusBadge` → mover a `src/features/shared/badges/` (o equivalente) y actualizar imports.
- `HistoricoPreciosChart` → aceptar `mode: "supplier-breakdown" | "module-aggregate"` para servir ambos casos. En modo agregado pinta una sola serie (precio total) y tooltip personalizado.
- `PreciosDeHoyTable`, `StockDisponibleChart` → no usados en módulos en esta iteración, se quedan donde están.
- `ComponentsFiltersDrawer` → extraer la lógica de filtros (chips de seleccionados, popover de selección múltiple) a un primitive reutilizable `<FiltersDrawer>` que permita declarar los grupos. En módulos lo usamos con (Familia + NATO + Tier + Stock-status) restringidos a los hijos en el picker.
- `useTableSearch` (debounced search bar wrapper) — si no existe, extraerlo.

#### Páginas y componentes nuevos

- `frontend/src/features/modules/types.ts` — `Module`, `ModuleSummary`, `ModuleChild`, `ModuleTreeNode`, `ModuleWithAggregates`, etc.
- `frontend/src/features/modules/api/modules-api.ts` — `list`, `get`, `create`, `update`, `delete`, `getTree`, `listPriceHistory`, `addChild`, `updateChild`, `removeChild`.
- `frontend/src/features/modules/hooks/` — `use-modules`, `use-module-detail`, `use-module-tree`, `use-module-price-history`, `use-module-mutations`, `use-module-children-mutations`.
- `frontend/src/features/modules/components/`:
  - `ModulesHierarchyTable.tsx` — tabla con filas expandibles (Radix Collapsible o hand-rolled) para mostrar el árbol del list y del "Contiene". Una sola tabla compartida entre ambos contextos.
  - `ModuleHeaderCard.tsx` — análogo a `ComponentHeaderCard`. Metadatos + agregados (Precio total + NATO + Tier + Caducidad). Slot para botón "Ver histórico de precios".
  - `ModulePriceHistoryModal.tsx` — abre `HistoricoPreciosChart` con la serie agregada del BE + `PeriodToggle` (reutilizado).
  - `AddChildModal.tsx` — modal del picker (Figma 47:12460). Lista combinada de componentes + módulos del catálogo con buscador + filtros (`FiltersDrawer` extraído) + estado "ya añadido" + input `quantity` antes de confirmar. Reusa `componentsApi.list` y `modulesApi.list`. Bloqueado para evitar autoreferencia.
- `frontend/src/features/modules/pages/`:
  - `ModulesListPage.tsx`
  - `ModuleDetailPage.tsx`
  - `ModuleEditPage.tsx` (`mode: "create" | "edit"` — mismo patrón que `ComponentEditPage`).
- Rutas en `App.tsx`:
  - `/modules` → `ModulesListPage`
  - `/modules/new` → `ModuleEditPage mode="create"`
  - `/modules/:id` → `ModuleDetailPage`
  - `/modules/:id/edit` → `ModuleEditPage mode="edit"`
- Reusa: `NatoScoreBadge`, `TierBadge`, `StockStatusBadge` (ya con tooltips on hover), `PeriodToggle`, `DataTablePagination`, `HistoricoPreciosChart` (modo agregado), `<Dialog>`, `<Select>`.
- Quantity en el picker: pedirla EN el modal antes de confirmar (decisión del usuario).
- Tooltip de Precio agregado en la tabla del list: on hover sobre el precio rosa, muestra desglose `Hijo A: 8.50 × 1 = 8.50 / Hijo B: 5.90 × 1 = 5.90 / …`.
- Tooltip de NATO/Tier agregado: on hover, muestra qué hijo contribuye el peor score/tier.
- Tooltip de Stock: muestra "Ensamblados: N · Puedes ensamblar N más con stock vigente".
- Tipo almacenamiento Select con enum `Gaveta | Almacén` (reusa `TIPO_ALMACENAMIENTO_VALUES` de `features/components/types.ts` — extraer a `features/shared/enums.ts`).

### Tests (frontend)

- Vitest: schemas zod, componentes nuevos (`AddChildModal` con filtros + estado "ya añadido", `ModulesHierarchyTable` con expand/collapse, `ModuleHeaderCard` con agregados + tooltips), hooks (`useModuleTree` con paginación, `useModulePriceHistory` con period toggle).
- E2E Playwright @smoke: usuario autenticado entra a `/modules`, expande un módulo, navega al detalle, abre el picker en modo edición y añade un componente con quantity=3, guarda, vuelve al detalle y verifica que el precio agregado refleja el cambio.

### Documentación

- `ai-specs/specs/data-model.md`: nuevas entidades `Module` y `ModuleChild`. Aggregations explicadas en una subsección "Aggregations" referenciada desde ambas entidades.
- `ai-specs/specs/api-spec.yml`: nuevos endpoints + schemas (`Module`, `ModuleChild`, `ModuleTree`, `ModulePriceHistory`, `AddChildRequest`).
- `ai-specs/specs/development_guide.md`: nuevo comando `seed_modules`.

## Constraints / Notes

- Pixel-perfect en lg (1024+). El visual de la tabla jerárquica del list es la pieza más cara — usa `Radix Collapsible` o equivalente con animación discreta.
- DAG: hay que cuidar el detector de ciclos. Implementación recursiva con `WITH RECURSIVE` en PostgreSQL al hacer `add_child`. Si la consulta detecta que `child_module_id` ya cuelga (directa o indirectamente) del `parent_module_id` candidato, rechazar.
- Buildable stock: cálculo recursivo. Cachear el resultado en memoria por request si el árbol es grande (el endpoint `/modules/{id}` lo hidrata una vez).
- No introducimos versionado real en esta iteración — `version` es un string libre (e.g. "v1.2"). Snapshots / inmutabilidad histórica quedan fuera de scope.
- KiCAT / Holded sync para módulos: out of scope.
- El movimiento `features/components/components/*` → compartido se hace al principio del change para que el feature de componentes siga compilando. Tests existentes adaptan sus imports en el mismo commit.
- Empezamos por scaffolding BE (modelos + repos + service + endpoints + seed) → luego FE (refactor compartidos → list → detail → edit → picker → histórico modal). Se fracciona en commits/PRs incrementales pero el change es uno solo.

## Design References

Figma File:
https://www.figma.com/design/pMUgDI7rbRRzVWLCJhoVnY/ada_asm

Referenced Nodes:
- https://www.figma.com/design/pMUgDI7rbRRzVWLCJhoVnY/ada_asm?node-id=46-5593 — Módulos · lista jerárquica
- https://www.figma.com/design/pMUgDI7rbRRzVWLCJhoVnY/ada_asm?node-id=46-10347 — Módulo · detalle
- https://www.figma.com/design/pMUgDI7rbRRzVWLCJhoVnY/ada_asm?node-id=47-11452 — Módulo · edición
- https://www.figma.com/design/pMUgDI7rbRRzVWLCJhoVnY/ada_asm?node-id=47-12460 — Modal "Añadir componente" desde edición

<!-- END_ENRICHED_USER_STORY -->
