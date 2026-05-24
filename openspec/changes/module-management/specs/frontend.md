# Frontend spec — module-management

## Refactors compartidos (commit 1 del change)

Movemos los componentes ya validados de `features/components/components/` a un namespace neutro reusable por components + modules (+ futuro projects).

### Mover sin renombrar (drop-in con import paths nuevos)

| Origen | Destino |
|---|---|
| `features/components/components/NatoScoreBadge.tsx` | `features/shared/badges/NatoScoreBadge.tsx` |
| `features/components/components/TierBadge.tsx` | `features/shared/badges/TierBadge.tsx` |
| `features/components/components/StockStatusBadge.tsx` | `features/shared/badges/StockStatusBadge.tsx` |
| `features/components/components/NatoScoreHelpPopover.tsx` | `features/shared/badges/NatoScoreHelpPopover.tsx` |
| `features/components/components/TierHelpPopover.tsx` | `features/shared/badges/TierHelpPopover.tsx` |
| `features/components/components/PeriodToggle.tsx` | `features/shared/charts/PeriodToggle.tsx` |
| `features/components/components/HistoricoPreciosChart.tsx` | `features/shared/charts/HistoricoPreciosChart.tsx` (con `mode` prop) |
| `features/components/rubrics.ts` | `features/shared/rubrics.ts` (TIER + NATO rubrics) |

Mover los enums compartidos:

| Origen (en `features/components/types.ts`) | Destino |
|---|---|
| `TIER_VALUES`, `TierValue` | `features/shared/enums.ts` |
| `NATO_SCORE_VALUES`, `NatoScoreValue` | `features/shared/enums.ts` |
| `TIPO_ALMACENAMIENTO_VALUES`, `TipoAlmacenamientoValue` | `features/shared/enums.ts` |
| `FAMILY_VALUES`, `FamilyValue` | (queda en components — no aplica a módulos) |

`features/components/types.ts` re-exporta los enums movidos para no romper imports externos en commits intermedios.

### Extraer `<FiltersDrawer>` genérico

Extraer de `ComponentsFiltersDrawer` la lógica de:
- Render del trigger ("Filtros · 2 activos") con badge contador.
- Drawer/Popover con grupos plegables.
- Render de chips de seleccionados (con × para deseleccionar).
- Aplicar / Limpiar.

API propuesta:

```ts
type FilterGroup<T extends string | number> = {
  key: string;
  label: string;
  options: Array<{ value: T; label: string; chip?: ReactNode }>;
  multi?: boolean;
};

<FiltersDrawer
  groups={[
    { key: "families", label: "Familia", options: ... , multi: true },
    { key: "nato_scores", label: "NATO", options: ... , multi: true },
    { key: "tiers", label: "Tier", options: ... , multi: true },
  ]}
  value={filters}
  onApply={(next) => setFilters(next)}
/>
```

`ComponentsFiltersDrawer.tsx` se queda como wrapper concreto que solo declara los `groups`. `AddChildModal` del feature de módulos lo consume con groups similares restringidos a la búsqueda de componentes.

### Extender `HistoricoPreciosChart`

Añadir prop `mode: "supplier-breakdown" | "module-aggregate"`. En `supplier-breakdown` (default — comportamiento actual) pinta N series, una por supplier. En `module-aggregate` pinta una sola serie (color brand) con tooltip mostrando precio total formateado en EUR.

Firma:

```ts
interface HistoricoPreciosChartProps {
  mode?: "supplier-breakdown" | "module-aggregate";
  // supplier-breakdown:
  prices?: SupplierPrice[];
  suppliers?: Supplier[];
  // module-aggregate:
  series?: Array<{ date: string; price: string }>;
}
```

## Estructura del feature `modules/`

```
frontend/src/features/modules/
├── api/
│   └── modules-api.ts
├── hooks/
│   ├── use-modules.ts
│   ├── use-module-detail.ts
│   ├── use-module-tree.ts
│   ├── use-module-price-history.ts
│   ├── use-module-mutations.ts        # create/update/delete
│   └── use-module-children-mutations.ts  # addChild/updateChild/removeChild
├── pages/
│   ├── ModulesListPage.tsx
│   ├── ModuleDetailPage.tsx
│   └── ModuleEditPage.tsx             # mode: create | edit
├── components/
│   ├── ModulesHierarchyTable.tsx
│   ├── ModuleHeaderCard.tsx
│   ├── ModulePriceHistoryModal.tsx
│   ├── AddChildModal.tsx
│   └── AggregateTooltips.tsx          # tooltips de precio/NATO/Tier/Stock agregados
└── types.ts
```

## Rutas (App.tsx)

```tsx
<Route path="/modules" element={<ModulesListPage />} />
<Route path="/modules/new" element={<ModuleEditPage mode="create" />} />
<Route path="/modules/:id" element={<ModuleDetailPage />} />
<Route path="/modules/:id/edit" element={<ModuleEditPage mode="edit" />} />
```

## Páginas

### `ModulesListPage` (Figma 46:5593)

- Header con título "Módulos" + subtitle + botón "+ Nuevo módulo" (link a `/modules/new`).
- Search bar (debounced).
- `ModulesHierarchyTable` con todas las raíces (paginado server-side).
- Cada fila lleva botón Eye → `/modules/:id`.
- Click en chevron expande/colapsa hijos inline (consumiendo `useModuleTree(id)` lazily).

### `ModuleDetailPage` (Figma 46:10347)

- Top bar: X close → `/modules` · "Editar Módulo" → `/modules/:id/edit`.
- `ModuleHeaderCard`:
  - Pink hex icon + name + version pill.
  - Descripción.
  - Grid 4 cols: Fecha creación, Última modificación, Versión, SKU.
  - Grid 4 cols: Fabricante, Ubicación, Tipo almacenamiento, Botón "Ver histórico de precios".
  - Stock (con tooltip "Puedes ensamblar N más") · Precio total (rosa, con tooltip de desglose).
  - NATO Scoring row: NatoScoreBadge + TierBadge + Caduca + Info icon (tooltip "Peor scoring viene de hijo X").
- "Contiene" section: `ModulesHierarchyTable` filtrado al subtree de este módulo, readonly (no expand recursivo en este tab, solo direct children).
- "Pertenece a" section: lista de padres con link a su detalle. Empty state cuando no tiene padres.
- Botón "Ver histórico de precios" abre `ModulePriceHistoryModal`.

### `ModuleEditPage` (Figma 47:11452 + 47:12460)

- Top bar: X / Cancelar / "Guardar cambios".
- Form (zod + react-hook-form):
  - Nombre del módulo, Descripción.
  - Versión, SKU (en create es required + único; en edit es editable pero 409 surfacing).
  - Fabricante, Ubicación, Tipo almacenamiento (Select), [Histórico button].
  - Stock (input number ≥ 0), Precio total (readonly, computado server-side al guardar).
  - NATO Scoring (readonly — display del agregado actual).
- "Contiene" section editable: tabla con direct children + botón "+ Añadir componente" → abre `AddChildModal`. Cada fila tiene icono delete (mutación remove).
- "Pertenece a" section: readonly.

## `AddChildModal` (Figma 47:12460 + extensión solicitada)

- Modal Dialog.
- Tabs (o segmented control): "Componentes" / "Módulos" — para distinguir el origen del hijo.
- Search bar (reusa `useTableSearch`).
- `FiltersDrawer` con grupos `families`/`nato_scores`/`tiers` para componentes; `[stock buckets, sku prefix]` para módulos (a definir en implementación; partir simple).
- Lista paginada con cards/rows clicables. Cada row muestra: icon + MPN/SKU · name · price.
- Estado "ya añadido" cuando `(parent_id, child_id)` ya existe en `module.children` → grey + pink "Ya añadido", click deshabilitado.
- Al click en una fila no-añadida → submenu/popover con input `quantity` (default 1, min 1) + botón "Añadir".
- Reusa `componentsApi.list` y `modulesApi.list`.
- Bloquea seleccionarse a sí mismo (en modo "Módulos", el actual queda greyed con badge "El propio módulo").

## Tests

- Vitest:
  - zod schemas (`moduleCreateSchema`, `moduleUpdateSchema`, `addChildSchema`).
  - `AggregateTooltips` con datos mockeados — verifica el desglose listado.
  - `ModulesHierarchyTable` — expand/collapse + lazy load.
  - `AddChildModal` — filtros, "ya añadido", quantity input + confirm.
- E2E Playwright @smoke:
  - Login → `/modules` → expand "Módulo Sensor Ambiental" → click en componente hijo → lands en `/components/:id`.
  - Login → crear módulo nuevo → añadir 2 componentes con quantity=3 cada uno → verificar precio total = `Σ price × 3`.
