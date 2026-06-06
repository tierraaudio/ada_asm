# Module management — catálogo + árbol jerárquico + agregaciones + edición + picker

design-linked: true
scope:
  backend: true
  frontend: true
source: Manual
reference: drafts/enriched/module-management-20260524-2046.md (canonical), Figma 46:5593 · 46:10347 · 47:11452 · 47:12460

## Why

El árbol Proyecto → Módulo → Componente está incompleto: hoy solo existe el nivel hoja (Component). La pantalla `/modules` está stubbed y el equipo no puede modelar ensamblajes reusables, ver coste total de producir un módulo, ni componer un sub-módulo dentro de otro. El usuario quiere cerrar este hueco en una única US con las 4 pantallas del Figma (lista, detalle, edición, picker de hijos) y reutilizando deliberadamente los componentes React ya validados de `components/` (badges, tablas, charts, filtros, paginador).

## What changes

### Backend

- Nuevas tablas `modules` y `module_children` con migración Alembic reversible (ver `specs/data-model/modules.md`).
- Dominio: `Module`, `ModuleChild` (frozen dataclasses) + `ModuleRepository` (Protocol) + implementación SQLAlchemy.
- Servicio `ModuleService` con `list`, `get_with_aggregates`, `get_tree`, `create`, `update`, `delete`, `add_child` (con detección de ciclos vía `WITH RECURSIVE`), `update_child_quantity`, `remove_child`, `list_price_history`.
- Pydantic schemas en `app/api/v1/schemas/modules.py`.
- Router con 9 endpoints (CRUD + tree + price-history + sub-resource children).
- Errores RFC 7807: `MODULE_NOT_FOUND` (404), `MODULE_SKU_ALREADY_REGISTERED` (409), `MODULE_CYCLE_DETECTED` (422), `CHILD_ALREADY_PRESENT` (422), `INVALID_CHILD_REFERENCE` (422).
- Seeder `python -m app.scripts.seed_modules` que crea los módulos del Figma (`Módulo Sensor Ambiental`, `Sistema Potencia BLDC`, `Etapa Driver` anidado) con al menos un hijo compartido entre dos padres (DAG).
- 80 % coverage gate mantenido.

### Frontend (refactors compartidos primero)

- Mover badges (`NatoScoreBadge`, `TierBadge`, `StockStatusBadge`) y enums (`TIPO_ALMACENAMIENTO_VALUES`) a `features/shared/` (o `components/feature/`). Reusables desde components + modules sin acoplar dominios.
- Extraer `<FiltersDrawer>` genérico desde `ComponentsFiltersDrawer` — recibe la declaración de grupos como prop.
- Extender `HistoricoPreciosChart` con `mode: "supplier-breakdown" | "module-aggregate"` para servir el histórico agregado del módulo (una serie única, tooltip de desglose por hijo).
- (`PreciosDeHoyTable`, `StockDisponibleChart` no se mueven en esta iteración — sólo se usan en components hoy.)

### Frontend (módulos)

- `features/modules/`: `api`, `hooks`, `pages`, `components`, `types.ts`.
- Páginas: `ModulesListPage`, `ModuleDetailPage`, `ModuleEditPage` (`mode: "create" | "edit"`). Rutas `/modules`, `/modules/new`, `/modules/:id`, `/modules/:id/edit` registradas en `App.tsx`.
- Componentes nuevos: `ModulesHierarchyTable` (filas expandibles, una sola tabla compartida entre list y "Contiene"), `ModuleHeaderCard` (slot para "Ver histórico de precios"), `ModulePriceHistoryModal`, `AddChildModal` (picker con buscador + `FiltersDrawer` + input quantity antes de confirmar + estado "ya añadido").
- Tooltips on hover:
  - Precio agregado → desglose `Hijo A: 8.50 × 1 = 8.50 / …`.
  - NATO/Tier agregado → "Peor scoring viene de `<hijo>`".
  - Stock → "Ensamblados: N · Puedes ensamblar M más".

### Documentación

- `ai-specs/specs/data-model.md`: nuevas entidades + subsección "Aggregations".
- `ai-specs/specs/api-spec.yml`: 9 endpoints nuevos + schemas.
- `ai-specs/specs/development_guide.md`: `seed_modules` documentado.

## Decisiones de modelo (validadas con el usuario)

| Decisión | Elegido | Notas |
|---|---|---|
| **BOM quantity** | Explícita por hijo (`quantity SMALLINT > 0`) | Multiplica en agregación de precios y stock. |
| **Reuso** | DAG — un hijo puede pertenecer a N padres | Sección "Pertenece a" lista todos los padres. |
| **Detección de ciclos** | `WITH RECURSIVE` en BE al `add_child` | Rechaza con 422 `MODULE_CYCLE_DETECTED`. |
| **Scoring OTAN del módulo** | Agregado puro, sin entidad propia | `nato_score = MIN(F<D<C<B<A<A+)`, `tier = MIN numérico` (Tier 1 = peor), `expires_at = MIN`. |
| **Stock del módulo** | Editable + tooltip derivado | `stock` editable manual; tooltip muestra "puedes ensamblar N más" = `min(child.stock // child.quantity)`. |
| **Cantidad UX** | Pedida EN el modal del picker | `AddChildModal` exige `quantity` antes de confirmar. |
| **Clave de negocio** | `sku` único case-insensitive | Índice funcional `lower(sku)`. No hay `mpn`. |
| **Histórico de precios agregado** | Endpoint BE agregado | `GET /api/v1/modules/{id}/price-history` devuelve serie ya sumada. |

## Out of scope (esta iteración)

- Snapshots / versionado real de módulos (campo `version` es free-text por ahora).
- KiCAT / Holded sync para módulos.
- Asociar módulos a `Project` (Project no ha aterrizado todavía).
- Override manual del scoring agregado (entidad `module_nato_scorings`).
- Cache materializado de agregados (se computan al vuelo; si rinde mal, materializar es follow-up).

## Plan de implementación fraccionada (orientativo)

1. Refactors FE compartidos (mover badges + extraer `FiltersDrawer` + extender `HistoricoPreciosChart`).
2. BE: tablas + migración + dominio + repos + service (sin endpoints).
3. BE: endpoints CRUD + sub-resource children + tree.
4. BE: endpoint price-history agregado + tests + seeder.
5. FE: types + api + hooks.
6. FE: ModulesListPage + ModulesHierarchyTable.
7. FE: ModuleDetailPage + ModuleHeaderCard + tooltips agregados.
8. FE: ModuleEditPage + AddChildModal + integración con price-history modal.
9. Docs (data-model.md + api-spec.yml + development_guide.md) + E2E + cierre.
