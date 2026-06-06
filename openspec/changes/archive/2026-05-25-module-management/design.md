# Module management — design

## Diseño de datos

### `modules`

Catálogo de módulos reusables (no instancias de proyecto). Cada módulo tiene metadatos editables + `stock` propio (ensamblados en almacén). Las agregaciones de precio/NATO/Tier se computan al vuelo desde los hijos — no se persisten.

| Columna | Tipo | Notas |
|---|---|---|
| `id` | UUIDv4 PK | `server_default gen_random_uuid()` |
| `sku` | `varchar(100)` NOT NULL | Único case-insensitive vía `lower(sku)` |
| `name` | `varchar(200)` NOT NULL | |
| `description` | `text` NULL | |
| `version` | `varchar(40)` NOT NULL DEFAULT `'v1.0'` | Free-text; no implica versionado real |
| `fabricante` | `varchar(120)` NULL | E.g. "Custom Assembly" |
| `location` | `varchar(100)` NULL | E.g. `G-M-01` |
| `tipo_almacenamiento` | `varchar(80)` NULL | FE-enforced `Gaveta | Almacén` |
| `stock` | `integer` NOT NULL DEFAULT 0 | Ensamblados disponibles |
| `notas` | `text` NULL | |
| `fecha_creacion` | `date` NULL | User-supplied |
| `created_at`/`updated_at` | `timestamptz` | Server-defaulted |

Indexes:
- Functional unique `uq_modules_sku_lower (lower(sku))`
- `lower(name)` para búsqueda

### `module_children`

Aristas del DAG. Una fila por relación padre→hijo. El hijo es **XOR** un módulo o un componente.

| Columna | Tipo | Notas |
|---|---|---|
| `id` | UUIDv4 PK | |
| `parent_module_id` | UUIDv4 NOT NULL | FK → `modules.id` ON DELETE CASCADE |
| `child_module_id` | UUIDv4 NULL | FK → `modules.id` ON DELETE CASCADE |
| `child_component_id` | UUIDv4 NULL | FK → `components.id` ON DELETE CASCADE |
| `quantity` | `smallint` NOT NULL | CHECK `> 0` |
| `sort_order` | `integer` NOT NULL DEFAULT 0 | Para orden estable en la UI |
| `notes` | `text` NULL | |
| `created_at`/`updated_at` | `timestamptz` | |

CHECK constraints:
- `(child_module_id IS NOT NULL)::int + (child_component_id IS NOT NULL)::int = 1` — XOR
- `child_module_id <> parent_module_id` — no self-reference directa

UNIQUE partial:
- `(parent_module_id, child_module_id) WHERE child_module_id IS NOT NULL` — un mismo módulo no se duplica como hijo del mismo padre; si hace falta N, va en `quantity`.
- `(parent_module_id, child_component_id) WHERE child_component_id IS NOT NULL` — idem para componentes.

Indexes:
- `(parent_module_id, sort_order)`
- `(child_module_id)`
- `(child_component_id)`

## Aggregations (computadas, no persistidas)

Para un módulo `M`, definimos los siguientes valores derivados que el endpoint `GET /api/v1/modules/{id}` hidrata server-side:

### Precio agregado (`precio_total`)

```
precio_total(M) = Σ child ∈ children(M):
    if child es componente C:
        quantity × current_price_per_100_eur(C)
    if child es módulo M':
        quantity × precio_total(M')   # recursivo
```

`current_price_per_100_eur(C)` ya lo hidrata `components` desde `supplier_prices` (latest qty_tier=100 del preferred supplier).

**Tooltip de desglose** (FE): on hover sobre el precio rosa, lista contributors `Hijo: Q × precio = subtotal`.

### NATO score agregado

Orden léxico definido (peor primero): `F < D < C < B < A < A+`.

```
nato_score(M) = MIN_orden_lex(
    map(child ∈ children_recursivos_componente(M), c → c.nato_score)
)
```

**Sólo los componentes hoja contribuyen** (los módulos intermedios no tienen `nato_score` propio — su agregado es éste). Si no hay descendientes componente, `nato_score = NULL`.

### Tier agregado

```
tier(M) = MIN_numeric(
    map(child ∈ children_recursivos_componente(M), c → c.tier)
)
```

Tier 1 = más crítico = peor. MIN numérico = el peor. NULL si sin descendientes componente.

### Fecha de caducidad de scoring agregada

```
expires_at(M) = MIN(
    map(child ∈ children_recursivos_componente(M),
        c → c.current_nato_scoring.expires_at if c.current_nato_scoring)
)
```

Null-safe. Si ningún componente tiene scoring activo, NULL.

### Stock ensamblable derivado (`buildable_stock`)

```
buildable_stock(M) = MIN over child ∈ children(M):
    if child es componente C:
        C.stock // child.quantity
    if child es módulo M':
        (M'.stock + buildable_stock(M')) // child.quantity   # tanto ensamblados como ensamblables del sub-módulo cuentan
```

**Tooltip de Stock** (FE): "Ensamblados: M.stock · Puedes ensamblar buildable_stock(M) más".

## Detección de ciclos

Al hacer `POST /api/v1/modules/{parent_id}/children` con `child_module_id = X`:

```sql
WITH RECURSIVE descendants(id) AS (
    SELECT child_module_id FROM module_children
        WHERE parent_module_id = :child_candidate_id
          AND child_module_id IS NOT NULL
    UNION ALL
    SELECT mc.child_module_id FROM module_children mc
        JOIN descendants d ON mc.parent_module_id = d.id
        WHERE mc.child_module_id IS NOT NULL
)
SELECT 1 FROM descendants WHERE id = :parent_id LIMIT 1;
```

Si retorna fila → 422 `MODULE_CYCLE_DETECTED`. Adicionalmente, validar `child_candidate_id != parent_id` antes de la query (caso trivial).

## Histórico de precios agregado

`GET /api/v1/modules/{id}/price-history?period=year|month|week`

Implementación BE:

1. Obtener el árbol recursivo de componentes hoja con su `quantity_propagada` (producto de quantities a lo largo del camino).
2. Determinar el conjunto de fechas relevantes = unión de `valid_from` de todos los `supplier_prices` (qty_tier=100, supplier=componente.preferred) de cada hoja, dentro del rango del period.
3. Para cada fecha `d`:
   ```
   precio_total(d) = Σ hoja:
       quantity_propagada × precio_vigente(hoja, d)
   ```
   donde `precio_vigente(hoja, d)` = el `supplier_prices.price` con mayor `valid_from <= d` para esa hoja.
4. Devolver `Array<{ date, price }>` ordenado.

Si una hoja no tiene `proveedor_preferente_id` o no tiene `supplier_prices`, su contribución a esa fecha es 0 (no rompe).

FE: reusa `HistoricoPreciosChart` con `mode="module-aggregate"` — una sola serie, color brand, tooltip mostrando la fecha y el total formateado en EUR.

## Refactor de componentes compartidos

| Antes | Después | Por qué |
|---|---|---|
| `features/components/components/NatoScoreBadge.tsx` | `features/shared/badges/NatoScoreBadge.tsx` | Usado en components + modules + (futuro) projects |
| `features/components/components/TierBadge.tsx` | `features/shared/badges/TierBadge.tsx` | Idem |
| `features/components/components/StockStatusBadge.tsx` | `features/shared/badges/StockStatusBadge.tsx` | Idem |
| `features/components/components/PeriodToggle.tsx` | `features/shared/charts/PeriodToggle.tsx` | Usado en components charts + module charts |
| `features/components/components/HistoricoPreciosChart.tsx` | `features/shared/charts/HistoricoPreciosChart.tsx` | Extensión multi-modo |
| `features/components/components/ComponentsFiltersDrawer.tsx` | `features/shared/filters/FiltersDrawer.tsx` + `features/components/components/ComponentsFiltersDrawer.tsx` (wrapper concreto) | Genérico + wrapper específico |
| `features/components/types.ts` (enums) | `features/shared/enums.ts` + re-export desde `features/components/types.ts` | Compartido sin acoplar |

Los tests existentes adaptan sus imports en el mismo commit del movimiento.

## Identificadores y nombres

- Slug del change: `module-management`.
- Migración: `20260526_0900_module_management__modules_and_children.py` (aprox).
- Tabla principal: `modules`.
- Tabla relación: `module_children`.
- Códigos de error: `MODULE_NOT_FOUND`, `MODULE_SKU_ALREADY_REGISTERED`, `MODULE_CYCLE_DETECTED`, `CHILD_ALREADY_PRESENT`, `INVALID_CHILD_REFERENCE`.

## Decisiones rechazadas (documentadas)

- **Entidad `module_nato_scorings` propia**: descartada en favor del agregado puro. Si en el futuro hace falta override manual, se añade en un change posterior sin migrar lo ya implementado.
- **`ltree` para path**: descartado en favor del modelo DAG con `module_children`. `ltree` asume árbol estricto con un único padre por nodo; el DAG requiere consultas recursivas (`WITH RECURSIVE`) que PostgreSQL maneja bien sin extensión adicional.
- **Pedir quantity inline en la tabla "Contiene"**: el usuario eligió pedirla en el modal del picker. Más estricto, evita filas con quantity=1 olvidadas.
- **`mpn` para módulos**: descartado — los módulos no vienen de un fabricante externo, sólo `sku` interno.
