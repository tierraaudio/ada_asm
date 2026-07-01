<!--
scope:
  backend: true
  frontend: true
design-linked: false
-->

## Why

Hoy crear un componente es 100% manual: el operador teclea MPN, nombre, familia, fabricante, datasheet, precios... uno a uno. Ya consultamos los 4 supplier APIs en el lookup, pero solo usamos una fracción mínima de lo que devuelven — y lo que extraemos lo **descartamos** tras pre-rellenar el form (no se persiste el blended, ni el datasheet binario, ni los paramétricos, ni el ciclo de vida). Además la familia se infiere fatal (el `family_hint` localizado de Mouser pisa el `CategoryId` estable de DigiKey por un bug de prioridad del merge).

Esta change cierra el hueco: **dado un MPN, poblar automáticamente todos los campos posibles** desde los 4 proveedores (datos mostrados + un blended extra que guardamos "por si acaso" y para procesos backend), **descargar y archivar el datasheet** en Azure Blob, **inferir la familia interna** de forma robusta, y **registrar el componente** para que el sync diario ya existente le acumule histórico de precio/stock desde la primera noche. Se integra en el frontend desde el inicio (el flujo "Nuevo componente"). La carga masiva (initial bulk ingestion) queda **fuera** de esta change — la abordaremos aparte reutilizando este pipeline.

Investigación de respaldo (probes en vivo con credenciales reales, 2026-06-12/13): `research/supplier-api-blended-research.md` y `research/family-inference-design.md`.

## What Changes

- **Nuevo: ingesta por MPN.** `POST /api/v1/components/ingest` (protegido, RFC 7807) **y** `python -m app.scripts.ingest_component <MPN>` (ejecutable en local vía docker exec y en prod como Container App Job one-off). Ambos comparten el mismo servicio de aplicación. Flags/body opcionales para los campos que los proveedores NO dan: `ubicacion`, `stock_inicial`, `holded_id`. El scoring OTAN se deja sin crear (manual por rúbrica en la UI).
- **Nuevo: SKU interno autogenerado** a partir de la familia inferida (prefijo de familia + secuencia), como en el seed. La entrada es el **MPN del fabricante**, no el SKU.
- **Nuevo: inferencia de familia robusta.** Tabla seed `component_family_rules` ({supplier, match_type, match_value} → familia), `FamilyInferenceService` con resolución por prioridad de señal (DigiKey leaf id → TME id → Farnell HS → Mouser keyword → vacío+`needs_review`), separado del merge de presentación. Se guarda la categoría cruda ganadora en el componente para auditar y re-clasificar sin re-llamar a las APIs.
- **Nuevo: descarga y archivo de datasheet.** Cadena de adquisición (Farnell directo → DigiKey-si-PDF → patrón fabricante → fallback link-only), descarga server-side con estrategia per-host de User-Agent, validación de `Content-Type==application/pdf` + magic bytes, y **almacenamiento en Azure Blob privado** (`datasheets/<sha256>.pdf`, dedupe por hash) servido vía backend proxy / SAS de user-delegation con managed identity.
- **Nuevo: blended de datos extra persistido** (hoy descartado): ciclo de vida (lifecycle/EOL/last-buy/sustituto), compliance (RoHS/REACH/MSL), export/aduanas (ECCN/HTS, `country_of_origin` ya es columna), logística (MOQ/múltiplo/lead-time/peso/reeling), imagen, paramétricos (tabla de specs), e identidad (SKU proveedor, IDs de marca/categoría, aliases).
- **Modificado: adapters extraen más señal.** `SupplierQuote` gana `supplier_category_id`, `supplier_category_name`, `tariff_code` y los campos blended. Se arreglan bugs hallados en los probes: DigiKey toma la categoría **raíz** en vez de la hoja (no distingue Diodos de Transistores); Farnell devuelve `family_hint=None` y le falta `versionInfo.versionNumber` (se queda en field-set base); TME descarta `category.id`; Mouser reporta over-limit como HTTP 200 en `Errors[]` (no 429).
- **Modificado: el lookup ya no colapsa la familia por prioridad de presentación** — el merge sigue para name/description/package/precio, pero la familia se resuelve en el servicio de inferencia con todas las señales por-proveedor.
- **Frontend:** el flujo "Nuevo componente" dispara la ingesta por MPN (prefill + creación), muestra los nuevos campos relevantes (imagen, lifecycle, datasheet archivada) y marca `needs_review` cuando la familia quedó sin inferir.

## Capabilities

### New Capabilities
- `component-ingestion`: pipeline que, dado un MPN, orquesta lookup→blend→inferencia de familia→descarga de datasheet→creación del componente→registro para sync diario. Expuesto como endpoint API + script CLI, reutilizados luego por la bulk ingestion.
- `datasheet-archival`: adquisición server-side del PDF de datasheet (cadena de fallback + estrategia per-host), almacenamiento dedup en Azure Blob privado, y servido autenticado vía backend.
- `family-inference`: derivación determinista de la familia interna desde las taxonomías heterogéneas de los proveedores vía tabla de reglas seed editable, con resolución por prioridad de señal y fallback a revisión manual.

### Modified Capabilities
- `supplier-integration`: `SupplierQuote` y los 4 adapters se amplían para capturar category-id/name, tariff_code y el blended extra; se corrigen los bugs de extracción de categoría (DigiKey hoja, Farnell tariff+version, TME id, Mouser Errors[]).
- `component-mpn-lookup`: la respuesta del lookup transporta los nuevos campos y las señales de categoría por-proveedor; la familia deja de mergear-se por prioridad de presentación.
- `component-catalog`: nuevas columnas escalares en `components` (lifecycle_status, last_buy_date, discontinued, end_of_life, moq, order_multiple, lead_time_days, unit_weight_kg, image_url, datasheet blob/source/sha256, provenance de familia) + nuevas tablas (`component_parameters`, `component_compliance`, `component_documents`, `component_cross_refs`, `component_family_rules`) + snapshot `raw_payload` JSONB por oferta de proveedor.

## Impact

- **Backend**: `app/application/services/` (nuevo `component_ingestion_service`, `family_inference_service`, `datasheet_service`), `app/infrastructure/suppliers/*` (los 4 adapters + `SupplierQuote`), `app/application/services/component_lookup_service.py` (merge de familia), nuevas migraciones Alembic (columnas + 5 tablas), nuevos repos, `app/api/v1/routers/` (endpoint ingest + servido de datasheet), `app/scripts/ingest_component.py`, seed de `component_family_rules`.
- **Infra**: Azure Storage Account (reutilizar el del broker o uno nuevo) con contenedor privado `datasheets`; rol `Storage Blob Data Contributor` para la managed identity del backend (patrón RBAC consistente con KV); módulo bicep + secret/env wiring. Container App Job one-off para el CLI en prod.
- **Frontend**: flujo "Nuevo componente" (form `ComponentEditPage` create mode) integra la ingesta; nuevos campos en el detalle; badge `needs_review` de familia.
- **Quota**: presupuesto ~1000 calls/día por proveedor; DigiKey es el cuello (5-7 calls/componente completo). El ingest hace la foto completa; el sync diario sigue refrescando solo precio/stock/lifecycle (1 call). Paramétricos/media/docs se pueblan en el ingest, no en cada sync.
- **Fuera de scope**: bulk/initial ingestion (otra change), scoring OTAN automático (sigue manual), RS Online (credenciales aún no funcionan).
- **Tamaño**: change grande. Las `tasks` se fasearán (schema/migraciones → adapters+SupplierQuote → family-inference → datasheet → ingest service → API/CLI → frontend) para entregar en baby-steps con TDD.
