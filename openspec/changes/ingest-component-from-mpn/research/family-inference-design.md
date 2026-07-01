# Inferencia de familia — diseño (live probes 2026-06-13)

## 1. Qué señal de categoría da cada proveedor

| proveedor | campo de categoría | ¿ID estable? | ¿path / breadcrumb? | ¿localizado? | ¿estándar normalizado (UNSPSC/ECLASS)? |
|---|---|---|---|---|---|
| **DigiKey** | `Products[].Category.CategoryId` (+ cadena `ChildCategories[].CategoryId/ParentId/Name`) | **SÍ.** Entero estable en cada nodo. *Probado invariante a locale*: `1N4148W` devolvió la cadena `19 > 2042 > 2085 > 280` byte-idéntica bajo `X-DIGIKEY-Locale-Language` es/de/en (informe DIGIKEY, `has_stable_id`). | **SÍ.** Breadcrumb raíz→hoja completo dentro de la respuesta de `keyword`, descendiendo `ChildCategories[0]` (DIGIKEY, `category_tree`). | NOMBRES sí (header `Locale-Language`); **IDs NO** se localizan (DIGIKEY, `localized`). | **NO.** Sólo ECCN (`ExportControlClassNumber`) y HTS (`HtsusCode`); ningún UNSPSC/ECLASS/ETIM (DIGIKEY, `has_normalized_standard`). |
| **TME** | `data.products.elements[].category.id` (+ `.name`) | **SÍ.** Entero estable. *Probado invariante*: `1N4148W`→`112791` y `GRM188R71H104KA93D`→`113537` idénticos en EN/ES/PL/DE/FR. El objeto `category` sólo tiene `{id, name}` (TME, `has_stable_id`). | **NO.** Sólo nombre de hoja; sin endpoint de árbol (todos 404: `/products/categories` → `E_API_ACTION_NOT_FOUND`) (TME, `category_tree` + `gotchas`). | ID invariante; el NAME es de-facto English-only en esta cuenta (`language=ES/PL/DE` no tradujo ni `description`) (TME, `localized`). | **NO.** Nada: ni UNSPSC, ni ECLASS, ni ECCN, ni HS (TME, `has_normalized_standard`). |
| **Mouser** | `SearchResults.Parts[].Category` (string de hoja localizado) | **NO.** No existe `CategoryId`/`CategoryCode`/GUID en ninguna parte; sólo el nombre de hoja (MOUSER, `has_stable_id`). | **NO.** Hoja única, sin parentId ni endpoint de árbol; las únicas rutas son partnumber/keyword/keywordandmanufacturer/manufacturerlist (MOUSER, `category_tree`). | **SÍ y BLOQUEADO** al locale de la API key (aquí español, mouser.es). `Accept-Language` y `?countryCode/?currencyCode` fueron **ignorados** (MOUSER, `localized` + `gotchas`). | **NO.** Sólo HTS (USHTS/CNHTS/TARIC…) y ECCN, demasiado gruesos (`8541` cubre diodos+transistores; `8542` cubre MCU+sensores+LDO) (MOUSER, `has_normalized_standard`). |
| **Farnell** | *Ninguno.* Mejor señal = `attributes[] attributeLabel=='tariffCode'` (código HS) + `displayName` | **NO** hay ID de categoría a ningún `responseGroup`; `nationalClassCode` fue `null` en los 10 MPN. Sí hay `sku` y `tariffCode` estables, pero **no son IDs de categoría** (FARNELL, `has_stable_id`). | **NO.** Sin breadcrumb; `/catalog/categories`→HTTP 596, `term=category:<id>`→HTTP 400 (FARNELL, `category_tree`). | `displayName` y los `attributeLabel` SÍ (por `storeInfo.id`, default es.farnell.com→español); `tariffCode` y `sku` **estables** es==uk (FARNELL, `localized`). | **NO** UNSPSC/ECLASS, pero `tariffCode` (HS) **sí** está presente y es la mejor señal estable (p. ej. `85411000`=diodos, `85322400`=cerámicos) (FARNELL, `has_normalized_standard`). |

**Lectura clave:** sólo **DigiKey y TME** dan ID estable + invariante a locale. Mouser y Farnell **no tienen ID de categoría**; Farnell salva la situación con `tariffCode` (HS, estable) y Mouser sólo con el nombre de hoja localizado (frágil).

---

## 2. Estrategia de inferencia recomendada

### Decisión: enfoque **(d) blended/layered**, no una sola técnica

Ninguna técnica aislada cubre los 4 proveedores: (a) tablas por `category_id` sólo aplican a DigiKey/TME; (b) keyword es lo único disponible para Mouser; Farnell necesita `tariffCode` + keyword. Se recomienda un **pipeline en capas con preferencia por la señal más fuerte por proveedor**, y resolver un único `family` por componente mediante **voto entre los proveedores que respondieron** (porque el endpoint ya consulta los 4 — component_lookup_service.py itera todos los adapters).

### Capas de inferencia (orden de confianza, de mayor a menor)

1. **Capa 1 — Tabla `{supplier + category_id → family}` (IDs estables).** Primaria para **DigiKey** (`CategoryId` de raíz + hoja) y **TME** (`category.id`). Es el camino más robusto: IDs probados invariantes a locale (DIGIKEY/TME `has_stable_id`), nunca se rompen al cambiar `Locale-Language`. Para DigiKey, **clave principal = LEAF `CategoryId`** con fallback a ROOT, porque la raíz colisiona: root `19` = Diodos **y** Transistores, root `32` = Microcontroladores **y** Fuentes de alimentación (DIGIKEY `recommendation` + `gotchas`). Desambiguar con la hoja (`280`→Diodos vs `278`→Transistores; `685`→MCU vs `699`→LDO).
2. **Capa 2 — Tabla `{tariffCode prefix → family}` (Farnell).** HS estable es==uk. Limpio para `8541 1xxx`→Diodos, `8541 2xxx`→Transistores, `8542 31xx`→Microcontroladores, `8532`→Condensadores, `8533`→Resistencias, `8536`→Conectores (FARNELL `recommendation`).
3. **Capa 3 — Keyword/substring sobre el nombre de categoría** (normalizado NFKD, case- y accent-insensitive). Primaria para **Mouser** (única señal: nombre de hoja español) y **desambiguador obligatorio** para el bucket IC de Farnell `85423990`, que colisiona Sensores (ACS712) **vs** Fuentes (LD1117) (FARNELL `recommendation` STAGE 2). También fallback para IDs DigiKey/TME aún no presentes en la tabla.
4. **Capa 4 — Paramétrico (fallback débil, opcional).** Presencia de labels diagnósticos (p. ej. Farnell `'Tipo de Canal'`→MOSFET/Transistor, `'Encapsulado del Diodo'`→Diodo) (FARNELL `category_fields`). Sólo como último recurso antes de "sin clasificar"; no fiable porque `attributes[]` puede venir vacío (GRM188… en FARNELL `gotchas`).

### Cómo interactúa con el MERGE existente (mouser>digikey>tme>farnell)

**Problema crítico detectado en el código actual:** el merge de `_merge_fields` (component_lookup_service.py:129) hace "primer no-nulo gana" sobre `family_hint`, y la prioridad por defecto es `["mouser","digikey","tme","farnell","rs"]` (config.py:131). Es decir, **hoy el `family_hint` de Mouser GANA al de DigiKey** — exactamente la señal más débil (nombre localizado, sin ID) pisa a la más fuerte (CategoryId estable). Esto debe corregirse.

**Recomendación: la inferencia de familia NO debe correr sobre el "ganador del merge".** El merge de prioridad es correcto para campos de *presentación* (name, description, package, precio), pero **no** para la familia. En su lugar:

- Cada adapter aporta su **propia** señal cruda (`supplier_category_id` + `category_name` + para Farnell `tariff_code`), **sin** colapsarla por prioridad de presentación.
- Un resolutor de familia dedicado (`FamilyInferenceService`) recibe **todas** las señales por-proveedor, aplica las capas 1→4 a **cada** proveedor para obtener una familia-candidata por proveedor, y luego **vota**.
- **Voto ponderado por confianza de la señal**, no por la prioridad de presentación:
  - peso alto: candidato vía Capa 1 (DigiKey leaf id, TME id) — señal estable.
  - peso medio: Capa 2 (Farnell tariffCode no ambiguo).
  - peso bajo: Capa 3 (keyword sobre nombre — Mouser, o desambiguación).
- **Desempate:** mayor confianza agregada; si empata, **DigiKey leaf id** es el árbitro (mejor señal probada, DIGIKEY `has_stable_id`), luego TME id, luego Farnell tariff, y Mouser keyword sólo como refuerzo. Esto **invierte** efectivamente la prioridad de presentación *sólo para family*.

### Fallback de no-match / ambigüedad

- **Dejar `family` vacío para corrección manual en UI** (no best-guess silencioso) cuando: ningún proveedor produce candidato, o el voto queda dividido sin árbitro claro entre dos familias de igual peso. Razón: un best-guess incorrecto se propaga a tier/NATO y al árbol de activos; un vacío es visible y corregible. Esto respeta el principio del CLAUDE.md de "Question Assumptions".
- **Registrar (log)** cada `category_name`/`category_id`/`tariff_code` no mapeado para crecer la tabla (MOUSER/TME/FARNELL `recommendation` lo piden explícitamente).
- Guardar **siempre** la categoría cruda ganadora en el componente (ver §4) para auditar y refinar reglas sin re-ingestar.

---

## 3. Tabla de mapeo inicial (semilla)

Derivada **exclusivamente** de los `per_mpn` de los 4 informes. `—` = la sonda no cubrió esa familia para ese proveedor (gap).

| our_family | DigiKey CategoryId (leaf / root) + nombre | TME category.id + nombre | Mouser keyword (ES, observado) | Farnell señal (tariffCode / displayName) |
|---|---|---|---|---|
| **Diodos** | `280` leaf / `19` root — "Single Diodes" (cadena `19>2042>2085>280`) | `112791` "SMD universal diodes" | "diodo" — *"Diodos de conmutación de señal pequeña"* | `85411000` / "Diodo de Señal Pequeña" |
| **Transistores** | `278` leaf / `19` root — "Single FETs, MOSFETs" (`19>2045>2088>278`) | `112826` "SMD N channel transistors" | "mosfet"/"transistor" — *"MOSFET"* | `85412900` / "MOSFET de Potencia" |
| **Microcontroladores** | `685` leaf / `32` root — "Microcontrollers" (`32>2012>685`) | `113637` "8-bit AVR family"; `112866` "ST microcontrollers" | "microcontrolador"/"mcu"/"arm" — *"Microcontroladores (MCU) de 8 bits"*, *"Microcontroladores ARM (MCU)"* | `85423190` / "MCU de 8 Bits", "MCU, 32BIT" |
| **Sensores** | `525` leaf / `25` root — "Current Sensors" (`25>525`). *Ojo:* BME280 cayó en board `795`/root `33`→Módulos | `112576` "Hall Sensors"; `113691` "Environmental Sensors" | "sensor" — *"Sensores de corriente montados en placa"*, *"Sensores de calidad del aire"* | `85423990` / "Sensor de Corriente Lineal, Efecto Hall" **(bucket ambiguo, requiere keyword)** |
| **Condensadores** | `60` leaf / `3` root — "Ceramic Capacitors" (`3>60`) | `113537` "MLCC SMD capacitors" | "condensador"/"mlcc"/"capacit" — *"Condensadores de cerámica multicapa (MLCC- SMD/SMT)"* | `85322400` / "Condensador de Cerámica Multicapa" |
| **Resistencias** | `52` leaf / `2` root — "Chip Resistor - Surface Mount" (`2>52`) | `100300` "SMD resistors" | "resistor"/"resistencia" — *"Resistores de película gruesa - SMD"* | `85332100` / "Resistencia SMD de Tipo Chip" |
| **Conectores** | `314` leaf / `20` root — "Headers, Male Pins" (`20>2027>314`) | `112937` "Pin headers" | "conector"/"cabecera"/"alojamiento"/"header" — *"Alojamientos de cables y cabecera"* | `85366930` / "Conector de Pines" |
| **Fuentes de alimentación** | `699` leaf / `32` root — "Voltage Regulators - LDO" (`32>2025>699`) | `112880` "LDO fixed voltage regulators" | "regulador"/"ldo"/"fuente"/"dc-dc" — *"Reguladores de voltaje LDO"* | `85423990` (vía proxy LD1117) / "Regulador de Tensión LDO" **(bucket ambiguo = mismo HS que ACS712 Sensores)** |
| **Módulos** | `795` leaf / `33` root — "Sensor Evaluation Boards" (`33>2041>795`) — caso BME280 breakout | **— gap** (TME mapeó BME280 a `113691` Sensores, no a módulo) | **— gap** (ninguna sonda devolvió categoría de módulo en Mouser) | `84733020` (BME280→SEN0236 breakout) / keyword "placa"/"módulo"/"shield"/"Gravity" |

### Gaps explícitos a cubrir manualmente

- **Módulos** sólo tiene señal real en **DigiKey** (`795`/root `33`) y **Farnell** (`84733020` + keyword). **No hay ID de TME ni keyword de Mouser** para Módulos en estas sondas — sembrar por keyword genérico y crecer con logs.
- **Mouser y Farnell no aportan ningún `category_id`** para ninguna familia (sólo nombre/HS); sus columnas son keyword/tariff por diseño.
- `AMS1117-3.3` **no existe** en TME ni Farnell (resuelven a `LD1117`); confirmar `manufacturer_symbols`/`resolved_mpn` antes de confiar (TME/FARNELL `gotchas`). El mapeo de *categoría* sigue siendo válido (LDO→Fuentes), pero la *identidad* del MPN difiere.

---

## 4. Esquema de datos para el mapeo

### Decisión: **tabla semilla `component_family_rules` en DB**, NO un dict en código

Razones: las reglas son **datos que crecen con el tiempo** (todos los informes piden "log misses to grow the table"), deben ser versionables y editables por operación **sin redeploy**, y deben poder refinarse cuando se detecta un mis-mapping en la UI. Un dict en código exigiría PR+deploy por cada categoría nueva. Se entrega como **migración + seed** (datos iniciales de §3), pero la tabla es la fuente de verdad en runtime.

```
component_family_rules
  id                UUID PK
  supplier          text NOT NULL          -- 'digikey' | 'tme' | 'mouser' | 'farnell'
  match_type        text NOT NULL          -- 'category_id' | 'tariff_prefix' | 'name_keyword'
  match_value       text NOT NULL          -- '280' | '8541' | 'diodo'  (normalizado NFKD/lower para name_keyword)
  family            text NOT NULL          -- una de las 9 familias internas
  confidence        smallint NOT NULL       -- peso para el voto: id=100, tariff=70, keyword=40
  priority          smallint NOT NULL DEFAULT 0  -- desempate intra-supplier (leaf>root, específico>genérico)
  enabled           boolean NOT NULL DEFAULT true
  notes             text                    -- p.ej. 'leaf 280, chain 19>2042>2085>280'
  created_at, updated_at
  UNIQUE (supplier, match_type, match_value)
```

Índice por `(supplier, match_type, match_value)` para lookup O(1). Las reglas `name_keyword` se cargan en memoria y se evalúan por substring normalizado.

### Trazabilidad en el componente (auditoría sin re-ingesta)

Almacenar en `Component` (o tabla satélite `component_family_provenance`) la **categoría cruda ganadora** junto a la familia inferida, para que un mis-mapping sea auditable y las reglas se refinen sin re-ingestar:

```
componente:
  family                        -- la inferida (o '' si quedó para corrección manual)
  family_inferred_supplier      -- proveedor que ganó el voto (p.ej. 'digikey')
  family_inferred_match_type    -- 'category_id' | 'tariff_prefix' | 'name_keyword'
  raw_category_id               -- '280' (DigiKey leaf) o '112791' (TME) — NULL para Mouser/Farnell
  raw_category_name             -- 'Single Diodes' / 'SMD universal diodes' / nombre Mouser ES
  raw_tariff_code               -- '85411000' (Farnell/Mouser HTS) si aplica
  family_confidence             -- score agregado del voto
  family_needs_review           -- bool: true si vacío o voto ambiguo → la UI lo marca
```

Beneficio: cuando alguien corrige `family` en la UI, se puede (a) auto-proponer una nueva fila en `component_family_rules` a partir de `raw_category_id`/`raw_category_name` guardados, y (b) re-clasificar en lote por `raw_category_id` sin volver a llamar a las APIs.

### Cambios mínimos de código que esto implica (señalados, no implementados)

1. **`SupplierQuote`** (supplier_quote.py): añadir `supplier_category_id: str | None` y `supplier_category_name: str | None` (y opcional `tariff_code` para Farnell/Mouser). Hoy sólo existe `family_hint` (un único string).
2. **DigiKey adapter** (digikey.py:267): hoy hace `Category.Name` = **ROOT** ("Discrete Semiconductor Products"). **Bug confirmado** (DIGIKEY `gotchas`): hay que **descender `ChildCategories[0]`** hasta la hoja y capturar leaf+root `CategoryId`. Sin esto no se distingue Diodos de Transistores.
3. **TME adapter** (tme.py:284): hoy **descarta `category.id`**; capturarlo en `supplier_category_id`.
4. **Mouser adapter** (mouser.py:159): mantener `Category` string como `supplier_category_name` (no hay id).
5. **Farnell adapter** (farnell.py:227): hoy `family_hint=None` (cero señal); extraer `tariffCode` + `displayName` del payload `large` que **ya** se descarga (FARNELL `gotchas`: "no extra call needed").
6. **Nuevo `FamilyInferenceService`** que vota como en §2, **separado** del `_merge_fields` de presentación.

---

## 5. Gotchas

**Localización**
- **Mouser está bloqueado al locale de la API key** (español, mouser.es). `Accept-Language`, `?countryCode` y `?currencyCode` fueron **ignorados** (MOUSER `localized`/`gotchas`). Toda regla `name_keyword` de Mouser es implícitamente español-only y se rompe en silencio si la key cambia de región → **fijar esta suposición en un test** (MOUSER `recommendation`).
- **DigiKey nombres se localizan** por `X-DIGIKEY-Locale-Language` (hoy el adapter envía Language=en, así que llegan en inglés), pero los **IDs no**. Por eso la tabla DigiKey/TME debe clavar sobre `category_id`, nunca sobre el nombre (DIGIKEY/TME `localized`).
- **Farnell**: `displayName` y `attributeLabel` se localizan por `storeInfo.id` (default es.farnell.com→español); `tariffCode`/`sku` estables es==uk. Los keywords de desambiguación del bucket IC deben usar **stems españoles** ("Sensor"/"Efecto Hall", "Regulador"/"LDO") (FARNELL `localized`/`recommendation`).
- **TME**: el `name` vino en inglés incluso pidiendo ES/PL/DE en esta cuenta; no asumir que localiza ni que no — clavar en el `id` (TME `localized`).

**Fuzzy keyword matching**
- Normalizar **NFKD + lower + strip de acentos** para robustez (MOUSER `recommendation`). Los nombres de hoja de Mouser son **cientos y abiertos**: tratar el matcher como best-effort con fallback "unmapped" + log (MOUSER `gotchas`).
- **Colisión HS Farnell `85423990`**: mapea **a la vez** a Sensores (ACS712) y a Fuentes/reguladores (LD1117). `tariffCode` por sí solo **no** divide el bucket IC → keyword de nombre es **obligatorio** ahí (FARNELL `recommendation` STAGE 2 + `gotchas`).
- **HS de Mouser demasiado grueso**: `8541` cubre diodos **y** transistores; `8542` cubre MCU+sensores+LDO. Usar HTS sólo como sanity backstop para familias limpias (`8532`=Condensadores, `8533`=Resistencias, `8536`=Conectores), nunca como discriminador primario (MOUSER `recommendation`/`gotchas`).

**Proveedores sin ID estable**
- **Mouser y Farnell no tienen ID de categoría** → un `{supplier_category_id→family}` es imposible para ellos; van por nombre (Mouser) y tariffCode+nombre (Farnell) (MOUSER/FARNELL `has_stable_id`). No buscar taxonomía en `ProductAttributes` (Mouser, sólo packaging) ni en `nationalClassCode` (Farnell, `null` en los 10 MPN).
- **Sin endpoint de árbol fiable**: TME `/products/categories`→404; Farnell `/catalog/categories`→596; DigiKey `/products/v4/categories`→404 (usar `/products/v4/search/categories`, ojo: usa clave `Children`, no `ChildCategories`). Las tablas id→family se **curan a mano** y se versionan como datos (TME/FARNELL/DIGIKEY `category_tree`/`gotchas`).
- **`_pick_product` puede elegir la parte equivocada**: `BME280` resuelve a un **breakout board** en DigiKey (MPN 2652, root 33→Módulos), Farnell (SEN0236→`84733020`) y TME (R&D breakout), mientras que el die desnudo sería Sensores. Esto es problema de **selección de producto, no de taxonomía**: forzar match exacto de MPN antes de confiar en la familia (DIGIKEY/FARNELL/TME `gotchas`). Igual con `2N7002→2N7002NXAKR`, `STM32F407VGT6→…TR`, `AMS1117-3.3→LD1117` (categoría idéntica, identidad distinta).

**Familias no vistas en las sondas**
- **Módulos** está infra-cubierto: sólo DigiKey (`795`/root `33`) y Farnell (`84733020`) lo tocaron, y **vía el accidente BME280-breakout**, no por un MPN de módulo intencional. **No hay ID de TME ni keyword de Mouser** para Módulos → sembrar por keyword genérico ("modulo"/"placa de desarrollo"/"kit"/"shield") y **crecer con logs de no-match**.
- **`AMS1117-3.3` ausente** en TME y Farnell; **Farnell no lo stockea** en absoluto (`numberOfResults=0`) → para esa parte Farnell no aporta familia. Partes commodity chinas faltan a menudo (TME/FARNELL `gotchas`).
- Cualquier `category_id`/`tariffCode`/nombre **no presente en la semilla** debe → familia vacía + `needs_review` + log, **nunca** un best-guess silencioso (todos los informes `recommendation`).

**Bug de prioridad ya en el código (no en los informes, hallado en el repo):** `_merge_fields` (component_lookup_service.py:129) + `supplier_lookup_priority=["mouser",…]` (config.py:131) hacen que el `family_hint` de **Mouser pise al de DigiKey** — la señal más débil gana. La inferencia de familia debe correr en un servicio de voto aparte (§2), no sobre el `family_hint` ganador del merge de presentación.

---

Archivos relevantes (rutas absolutas):
- `/Users/jon/Documents/Github/ada_asm/ada_asm/backend/app/domain/entities/supplier_quote.py` — `SupplierQuote`; añadir `supplier_category_id` / `supplier_category_name` (hoy sólo `family_hint`).
- `/Users/jon/Documents/Github/ada_asm/ada_asm/backend/app/application/services/component_lookup_service.py` — `_merge_fields` (línea 129) hace "primer no-nulo gana"; aquí está el bug de prioridad de `family_hint`.
- `/Users/jon/Documents/Github/ada_asm/ada_asm/backend/app/core/config.py` — `supplier_lookup_priority` default `["mouser","digikey","tme","farnell","rs"]` (línea 131).
- `/Users/jon/Documents/Github/ada_asm/ada_asm/backend/app/infrastructure/suppliers/digikey.py` — línea 267 toma `Category.Name` (ROOT, bug); debe descender `ChildCategories`.
- `/Users/jon/Documents/Github/ada_asm/ada_asm/backend/app/infrastructure/suppliers/tme.py` — línea 284 descarta `category.id`.
- `/Users/jon/Documents/Github/ada_asm/ada_asm/backend/app/infrastructure/suppliers/mouser.py` — línea 159, `Category` string localizado.
- `/Users/jon/Documents/Github/ada_asm/ada_asm/backend/app/infrastructure/suppliers/farnell.py` — línea 227, `family_hint=None` (cero señal; extraer `tariffCode`+`displayName`).
- `/Users/jon/Documents/Github/ada_asm/ada_asm/backend/app/domain/entities/component.py` — línea 26, `family: str = ""` (destino de la familia inferida).

---

## Anexo: ¿ID de categoría estable por proveedor?

- **digikey**: YES. Products[].Category.CategoryId is a stable integer, and every node in the ChildCategories chain has its own stable CategoryId + ParentId. PROVEN locale-invariant: re-fetched 1N4148W under X-DIGIKEY-Locale-Language es / de / en and the full id chain 19 > 2042 > 2085 > 280 was byte-identical while every Name localized (e.g. 'Single Diodes' -> 'Diodos simples' -> 'Einzeldioden'). This is the BEST normalized signal: build a one-time {CategoryId -> our_family} table and skip keyword matching.
- **tme**: yes — data.products.elements[].category.id (integer). Proven locale-invariant: 1N4148W returned id=112791 identically across EN/ES/PL/DE/FR; GRM188R71H104KA93D returned id=113537 across EN/PL/ES/DE. The `category` object contains exactly two keys: {id, name}. This makes a one-time {category_id -> our_family} lookup table the recommended, robust approach.
- **mouser**: no — NO stable category ID exposed. The full part object's only taxonomy field is `Category`, a localized leaf NAME string. Probed every part for keys containing id/categ/unspsc/class: the only match is `Category` itself. There is no CategoryId / CategoryCode / CategoryNumber / category GUID anywhere in the partnumber or keyword response. Path: SearchResults.Parts[].Category (string, not an id).
- **farnell**: no — there is NO category ID of any kind. element14's Product Search API exposes no `category`/`categoryId`/`categoryName`/breadcrumb on products at ANY responseGroup (small/medium/large/inventory confirmed live). The only category-LIKE candidate field, `products[].nationalClassCode`, was null on every one of the 10 MPNs. NOTE: there IS a stable PRODUCT id `products[].sku` (e.g. CRCW060310K0FKEA = 2122493, byte-identical on es.farnell.com and uk.farnell.com) and a stable `tariffCode` — but neither is a category id.
