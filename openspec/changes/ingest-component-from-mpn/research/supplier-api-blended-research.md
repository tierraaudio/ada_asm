# Investigación de APIs de proveedores — Síntesis para la ingesta de ada_asm

## 1. Datasheets — matriz de disponibilidad

| proveedor | campo | ¿PDF directo descargable server-side? (evidencia del live test) | caveats |
|---|---|---|---|
| **Mouser** | `SearchResults.Parts[].DataSheetUrl` | **NO.** GET con UA de navegador → HTTP 200 pero `Content-Type: text/html`, `server: AkamaiGHost`, body de 13897 bytes "Access to this page has been denied" (Akamai Bot Manager, cookie `AKA_A2`). HEAD con UA por defecto → connection reset (`http_code 000`). UA navegador + Referer + cookies calentadas NO lo evita. | Campo **frecuentemente vacío**: los 11 registros NE555P y ambos STM32F407VGT6 devolvieron `''`; solo apareció poblado en un registro LM358. Requiere navegador headless / egress residencial para los bytes reales. Almacenar la URL, realizar el binario aparte. |
| **DigiKey** | `Products[].DatasheetUrl` (keyword/productdetails); también `/media` → `MediaLinks[]` con `MediaType=='Datasheets'` | **MIXTO.** (1) PDF directo: el valor primario de NE555P `ti.com/lit/ds/symlink/na555.pdf?ts=…` → HTTP/2 200, `application/pdf`, 2.26 MB, **sin UA de navegador, sin auth, sin hotlink protection** (curl por defecto y Chrome UA = headers idénticos). (2) NO directo: variantes hermanas (NE555PSR/PS/PW) → wrapper interstitial `ti.com/general/docs/suppproductinfo.tsp?...` que resuelve (incluso con `-L`) a HTTP/2 200 `text/html` (página de descargo), NO un PDF. | El host es el dominio del fabricante (ti.com), no digikey.com → comportamiento por UA varía según fabricante. La URL lleva un querystring `ts=` (cache-buster) que cambia por respuesta: NO usar como clave de dedupe. HEAD + validar `Content-Type==application/pdf` antes de tratar como archivo. |
| **TME** | `/products/files` → `data.elements[].documents.elements[]` donde `type=='DTE'` | **NO.** `curl -sIL` del DTE url → HTTP/2 403, `text/html`, `server: cloudflare` + `cf-mitigated: challenge`. UA de navegador NO ayuda (sigue 403, magic bytes `<!DOCTYP` = página de challenge HTML, no `%PDF`). Añadir Referer `https://www.tme.eu/` tampoco (sigue 403, `cf-mitigated: challenge`, `cf-ray`). | URL protocol-relative `//www.tme.eu/Document/<hash>/<file_name>`; `file_name` lleva la extensión `.pdf` real. Host de documentos detrás de Cloudflare JS challenge → NO sirve el PDF a IP de datacenter vía curl/httpx. Solo la metadata (url, file_name, size, language) llega por la API autenticada. |
| **Farnell / element14** | `keywordSearchReturn.products[].datasheets[].url` (+ `.description`, `.type`) | **SÍ.** Dos sabores live-testeados: (1) Farnell-hosted `http://www.farnell.com/datasheets/2287727.pdf` → HTTP 200, `application/pdf`, **un redirect http→https, sin UA de navegador ni auth** (verificado: LM358N 262KB, 1N4148, ATMEGA328P-PU 31MB). (2) Third-party-hosted `https://4donline.ihs.com/images/VipMasterIC/...pdf?hkey=...` → HTTP 200 `application/pdf` directo (STM32F407 5.8MB); el `hkey` es parte de la URL y debe preservarse. | `datasheets[]` es **SPARSE/OPCIONAL**: presente solo cuando Farnell tiene datasheet de ese SKU exacto. NE555P (sku 3006909) NO devolvió `datasheets[]`; LM358N/1N4148/ATMEGA328P-PU/STM32F407 sí. El comentario del adapter "Basic/Large response group does not include datasheet URLs" es **INEXACTO**. Aparece con `responseGroup` en {medium, large, prices}. Seguir redirects (`-L`), preservar querystring completo, validar `Content-Type==application/pdf`. |

### Cadena de adquisición recomendada (parar al primer éxito)

1. **Preferir la URL de Farnell** cuando exista `datasheets[]`: es el único de los cuatro con PDF directo descargable server-side comprobado (Farnell-hosted y IHS-hosted, ambos `application/pdf` sin navegador). *Por qué:* es la vía más barata y fiable que no requiere fetcher browser-grade (reportes Farnell + Mouser/DigiKey/TME confirman que los otros tres tienen bloqueos o son inconsistentes).
2. **URL de DigiKey** cuando el valor primario sea un PDF directo de fabricante (p.ej. `ti.com/lit/ds/symlink/*.pdf`). Validar `Content-Type` porque la misma familia mezcla PDFs directos con wrappers `.tsp` HTML (reporte DigiKey).
3. **Patrón fabricante-directo determinista** (TI/ST/onsemi/Espressif/Nordic) — ver más abajo; mejor calidad y menos fricción legal (reporte FALLBACKS).
4. **Octopart / Nexar** como descubridor cross-supplier de la URL canónica (`best_datasheet` / `documents[].url`) — solo como *puntero para fetch+store propio*, nunca hot-link (restricción ToS, ver abajo).
5. **Reuso cross-supplier**: si falla Mouser, probar la URL DigiKey/TME/Farnell del mismo MPN (los cuatro se consultan). 
6. **Último recurso: "solo link", `datasheet_pdf = null`**, mostrar URL externa en UI. Nunca scrapear sitios HTML agregadores (alldatasheet, datasheetcatalog, octopart.com HTML): baja calidad, ToS-hostiles, inestables.

### Notas de implementación de descarga (reporte FALLBACKS, live-probed)

- **Normalizar URL primero**: añadir esquema a las protocol-relative de TME (`//host/...` → `https://host/...`).
- **Seguir redirects** (`-L`) **siempre** y **validar el `Content-Type` final == `application/pdf` Y magic bytes `%PDF`** — no confiar en la extensión. Si es `text/html` (interstitial Mouser/Akamai, wrapper `.tsp` de TI, challenge Cloudflare de TME) → tratar como fallo y pasar al siguiente origen.
- **User-Agent es load-bearing y contraintuitivo, por host**:
  - **TI** y **Espressif**: limpios, `200 application/pdf` con cualquier UA.
  - **onsemi**: `200 PDF` SOLO con UA tipo `curl/8.0`; cualquier UA de navegador → `403 AkamaiGHost`. Nota sufijo `-d` + minúsculas.
  - **Mouser/DigiKey-CDN (`mm.digikey.com`, Cloudflare)**: enviar UA tipo navegador + `Accept`/`Accept-Language`; ante 403/503 challenge → fallback.
  - **ST**: fingerprinting TLS/HTTP — todo intento server-side con curl (HTTP/2 y HTTP/1.1, curl UA y headers de navegador completos) muere con `INTERNAL_ERROR`, `http_code=000`; incluso WebFetch browser-grade hizo timeout. ST efectivamente necesita **headless browser real / proxy residencial**, o sourcear el doc idéntico desde un mirror de proveedor. Marcar ST como "hard direct source".
- **Estrategia per-host UA + retry** con UA alternativo ante 403. Setear `Referer` a la página de producto cuando aplique protección hotlink.
- Registrar **source + URL final + sha256** de lo descargado.

### Patrones fabricante-directo verificados (reporte FALLBACKS)

| Fabricante | Patrón URL | Estado server-side (probado) |
|---|---|---|
| **Texas Instruments** | `https://www.ti.com/lit/ds/symlink/<partlower>.pdf` | `200 application/pdf`, cualquier UA. **Mejor caso.** |
| **STMicroelectronics** | `https://www.st.com/resource/en/datasheet/<id>.pdf` (`<id>` = parte o doc-code `dm…`/`cd…`) | URL válida, pero **servidor bloquea fetches datacenter/curl (fingerprint). Necesita headless/proxy.** |
| **onsemi** | `https://www.onsemi.com/download/data-sheet/pdf/<part>-d.pdf` (o `…/pdf/datasheet/<part>-d.pdf`) | `200 application/pdf` **solo con UA tipo curl**; UA navegador → 403. Sufijo `-d` + minúsculas. |
| **Espressif** | `https://documentation.espressif.com/<doc>_datasheet_en.pdf` | `200 application/pdf`, cualquier UA. **Limpio.** |
| **Nordic / Microchip / NXP / Infineon / Bosch Sensortec** | Portal de docs propio predecible por-doc, pero el **revision/doc-id no siempre es derivable solo del MPN**. | Mixto: el patrón existe pero suele necesitar el doc-id → descubrir vía supplier/Octopart, luego fetch directo del host del fabricante. |

**Caveat clave:** el *template* de URL es predecible, pero el *token de filename exacto* (revisiones `-d`, `dm…`, `bst-…-ds000`) no siempre es función pura del MPN. Algoritmo realista: derivar fabricante → probar patrón con MPN → si 404, usar la URL exacta del agregador → fetch directo del host del fabricante.

### Octopart / Nexar (reporte FALLBACKS)

- Octopart v4 = "Nexar Legacy API"; Nexar = GraphQL en `https://api.nexar.com/graphql/`, OAuth2 client-credentials. Expone `best_datasheet` y `documents[]` con `url, source, mimetype, size_bytes, num_pages, created`. Excelente para *descubrir* la URL canónica cuando los 4 fallan.
- **Free tier**: ~1000 parts, hasta 100 matched parts/query (cifras inconsistentes en su propia doc: lifetime vs mensual). Apto solo para enriquecimiento de fallback de bajo volumen.

### Almacenamiento en Azure Blob (reporte FALLBACKS)

**Patrón: descargar-una-vez, guardar-en-Blob, servir-vía-backend.**
- Contenedor privado `datasheets`, blobs keyed por **content hash** para deduplicar PDFs idénticos entre MPNs: `datasheets/<sha256>.pdf`. Filas DB mapean `component_id → blob path, source_url, source, fetched_at, sha256, content_type, num_pages`.
- **Contenedor PRIVADO** (sin acceso anónimo). Servir vía **backend proxy** (`GET /components/{id}/datasheet` valida authz y hace stream del blob, o 302 a un **user-delegation SAS** corto, read-only, single-blob, minutos — firmado con managed identity, no con account key).
- Auth a storage desde el backend con **managed identity del Container App + `Storage Blob Data Reader/Contributor`**, no connection strings (consistente con el trabajo RBAC de Key Vault Secrets-User reciente).
- Esto **esquiva todos los caveats de fetch**: se busca la URL frágil upstream *una vez* en ingest (con retries/headless para ST), luego se sirve copia propia limpia siempre.

### Nota ToS / legal (reporte FALLBACKS)

- Las datasheets son **obras con copyright** del fabricante. Almacenar+servir internamente a empleados autenticados (herramienta privada tras login) es materialmente distinto de re-hostear público; riesgo práctico bajo si se mantiene privado y el PDF sin modificar (no quitar avisos de copyright/marca).
- **Regla contractual dura de Nexar/Octopart** (verificada): NO cachear datos >24h, NO self-hostear contenido (datasheets/imágenes incluidas), NO quitar avisos propietarios. → Usar Nexar **solo para descubrir** la URL del fabricante; luego **fetch+store del PDF desde el host del fabricante**, gobernado por sus términos (gratis/permisivos), nunca persistir "la datasheet de Octopart" >24h.
- **ToS de proveedores** tienden a *linkear* en vez de *re-hostear* su media. Postura segura: guardar el PDF del host del **fabricante** cuando se identifique, mantener links de proveedor como puntero de registro.

---

## 2. Blended de datos extra — esquema unificado

Campos EXTRA que vale la pena guardar ahora (más allá de name/description/manufacturer/family/datasheet/package/prices/stock ya almacenados). Cobertura: **4/4 = todos los proveedores**, parcial indicado por proveedor.

### Ciclo de vida (lifecycle / obsolescencia / last-buy)

| unified_field_name | mouser path | digikey path | tme path | farnell path | tipo | por qué guardarlo |
|---|---|---|---|---|---|---|
| `lifecycle_status` | `Parts[].LifecycleStatus` (null/EOL/Obsolete/NRND) | `Products[].ProductStatus.Status` (+ `.Id`; enum vía `FilterOptions.Status`) | `data.products.elements[].product_status[]` (enum: AVAILABLE_WHILE_STOCKS_LAST / NOT_IN_OFFER / CANNOT_BE_ORDERED / BLOCKED_FOR_ZBL_*) | `products[].productStatus` (STOCKED/DIRECT_SHIP/NO_LONGER_STOCKED/NO_LONGER_MANUFACTURED) + `releaseStatusCode` (4=Active,6=To-be-disc,7=Disc) | string/enum | **4/4 (semántica distinta por proveedor).** Señal núcleo de obsolescencia → alertas EOL y last-time-buy para inventario. Mapear a vocabulario propio. |
| `discontinued` | (vía `LifecycleStatus` + `IsDiscontinued` doc-only) | `Products[].Discontinued` (bool) | (vía `product_status[]`) | (vía `releaseStatusCode=7`) | bool | Parcial nativo (DigiKey explícito). Flag de descontinuación. |
| `end_of_life` | (vía `LifecycleStatus`) | `Products[].EndOfLife` (bool) | (vía `product_status[]`) | (vía `releaseStatusCode=6/7`) | bool | Parcial nativo. EOL explícito. |
| `last_buy_date` | — | `Products[].DateLastBuyChance` (ISO\|null) | — | — | string ISO | **Solo DigiKey.** Fecha last-time-buy para planificación de compra final. |
| `suggested_replacement` | `Parts[].SuggestedReplacement` (MPN) | (vía `/substitutions` SubstituteType=Direct) | (vía `/products/similar`) | (`related{}` solo dice si existen, no cuáles) | string/array | Parcial. Sucesor directo para EOL → sugerencia automática de sustituto. |

### Compliance (RoHS / REACH / MSL)

| unified_field_name | mouser path | digikey path | tme path | farnell path | tipo | por qué guardarlo |
|---|---|---|---|---|---|---|
| `rohs_status` | `Parts[].ROHSStatus` ('RoHS Compliant'/'No') | `Products[].Classifications.RohsStatus` | **NO disponible en V2** | `products[].rohsStatusCode` (YES/NO/NA) + `attributes[]` rohsCompliant/rohsPhthalatesCompliant | string | **3/4 (TME no expone).** Badge regulatorio; siempre poblado en Mouser. |
| `reach_svhc` | `Parts[].REACH-SVHC` (array, doc-only/raro) | `Products[].Classifications.ReachStatus` ('REACH Unaffected') | **NO disponible en V2** | `attributes[]` donde label=`SVHC` ('No SVHC (27-Jun-2018)') | string/array | Parcial. Cumplimiento REACH/SVHC. SVHC solo dentro de `attributes[]` en Farnell. |
| `moisture_sensitivity_level` | (vía `ProductAttributes[]` por categoría) | `Products[].Classifications.MoistureSensitivityLevel` | (vía parameters, no estándar) | `attributes[]` donde label=`MSL` | string | Parcial nativo (DigiKey explícito). Nivel JEDEC MSL para manejo SMD. |
| `hazardous_flags` | `Parts[].ProductCompliance` parcial | `[/pricing]` `ContainsLithium` / `ContainsMercury` (bool) | — | `attributes[]` `hazardous` | bool/string | Parcial. Hazmat para envío/regulatorio. En DigiKey **solo en endpoint `/pricing`**. |

### Export / aduanas (ECCN / HTS / TARIC, país de origen)

| unified_field_name | mouser path | digikey path | tme path | farnell path | tipo | por qué guardarlo |
|---|---|---|---|---|---|---|
| `eccn` | `Parts[].ProductCompliance[]` ComplianceName=`ECCN` ('EAR99') | `Products[].Classifications.ExportControlClassNumber` ('EAR99') | **NO en V2** | `attributes[]` `usEccn` ('EAR99') / `euEccn` ('NLR') | string | **3/4 (TME no).** Control de exportación. |
| `hts_code` | `Parts[].ProductCompliance[]` ComplianceName=`USHTS`/`TARIC`/`CNHTS`/`CAHTS`/`JPHTS`/`MXHTS`/`BRHTS`/`KRHTS` | `Products[].Classifications.HtsusCode` ('8542.39.0070') | **NO en V2** | `attributes[]` `tariffCode` ('85423990') | string | **3/4 (TME no).** Clasificación arancelaria/aduanas para landed cost. Mouser da el set multi-país más rico. |
| `country_of_origin` | `Parts[].TradeCompliance[]` ComplianceName='País de origen' (valor localizado) | — | **NO en V2** | `products[].countryOfOrigin` (ISO-2, 'MX') | string | Parcial. Origen para aduanas/aranceles (p.ej. Section 301). Mouser localizado; Farnell ISO limpio. |
| `country_of_assembly` | `Parts[].TradeCompliance[]` ComplianceName='País de origen del ensamblaje' | — | — | — | string | **Solo Mouser.** Origen de ensamblaje (localizado). |
| `tariff_active` | — | `Products[].ProductVariations[].TariffActive` (bool) | — | — | bool | **Solo DigiKey.** Indica que aplica arancel de importación → landed cost difiere de StandardPricing. |

### Logística (MOQ / mult / packaging / lead time / peso / EAN)

| unified_field_name | mouser path | digikey path | tme path | farnell path | tipo | por qué guardarlo |
|---|---|---|---|---|---|---|
| `moq` | `Parts[].Min` | `Products[].ProductVariations[].MinimumOrderQuantity` | `data.products.elements[].minimal_amount` | `products[].translatedMinimumOrderQuality` (typo API: es MOQ) | int | **4/4.** Cantidad mínima de pedido. |
| `order_multiple` (SPQ step) | `Parts[].Mult` | `Products[].ProductVariations[].StandardPackage` (¡keyword=0, **`/pricing`=50** correcto!) | `data.products.elements[].multiples` | `products[].orderMultiples` (v1.1+, requiere versionNumber) | int | **4/4.** Múltiplo de orden / SPQ. DigiKey: usar `/pricing` para SPQ fiable. Farnell requiere bump a v1.1. |
| `max_order_qty` | `Parts[].SalesMaximumOrderQty` | `Products[].ProductVariations[].MaxQuantityForDistribution` (0=sin tope) | — | — | int | Parcial. Cantidad máxima por pedido. |
| `pack_size` / `packaging` | `Parts[].ProductAttributes[]` (Empaquetado/Cantidad estándar) | `Products[].ProductVariations[].PackageType` + `FilterOptions.Packaging` | `data.products.elements[].packing.elements[]` ({id:TB1,amount:50}) | `products[].packSize` + `packageName` (v1.1+) | array/int | **4/4.** Tipo de empaque + qty por pack para costeo pack-aware. |
| `lead_time` | `Parts[].LeadTime` ('42 Días', localizado) | `Products[].ManufacturerLeadWeeks` (string '6', semanas) | `[/products/data]` `data.elements[].deliveries` (null si en stock) | `products[].stock.leastLeadTime` (días, 92) | string/int | **4/4 (unidades distintas).** Lead time para ETA de reposición. Mouser localizado, DigiKey semanas-string, Farnell días. |
| `factory_stock` | `Parts[].FactoryStock` (string, often '0') | `Products[].ManufacturerPublicQuantity` | — | — | int | Parcial. Stock de fábrica como señal secundaria. |
| `incoming_stock_schedule` | `Parts[].AvailabilityOnOrder[]` ({Quantity,Date} ISO) | (no en keyword) | `[/products/data]` `deliveries` | `products[].stock.expectedStock` ({level,date}, v1.1+) | array | Parcial. Stock entrante fechado para ETA preciso. |
| `unit_weight` | `Parts[].UnitWeightKg.UnitWeight` (kg, float) | — | `data.products.elements[].weight.value` + `.unit` ('g') | **NO en schema** (sin weight/dimensiones) | float | Parcial (Mouser kg, TME g). Peso unitario para shipping/landed-cost. |
| `reeling` | `Parts[].Reeling` (bool) | (vía `PackageType` Tape&Reel) | (vía `packing`) | `products[].reeling` (bool) | bool | Parcial nativo. Disponibilidad cut-tape/reel. |
| `restriction_region` | `Parts[].RestrictionMessage` (localizado) | (vía `MarketPlace`/stock) | (vía `product_status[]` BLOCKED_*) | (vía `productStatus`) | string | Parcial. Flag de no-vendible en región → evitar quotes incomprables. |

### Media (imagen)

| unified_field_name | mouser path | digikey path | tme path | farnell path | tipo | por qué guardarlo |
|---|---|---|---|---|---|---|
| `image_url` | `Parts[].ImagePath` (thumbnail '_t'; **detrás de Akamai** — no descargable curl/httpx) | `Products[].PhotoUrl` (mm.digikey.com CDN, **descarga directa `image/jpeg`** sin UA/auth; richer en `/media`) | `assets.primary_photo.{prime,thumbnail,high_resolution}` (cloudimg.io CDN, watermarked+signed, **SÍ resuelve**) | `products[].image.{baseName,vrntPath}` (ensamblar URL) o `mainImageURL`/`thumbNailImageURL` (v1.3+) | string URL | **4/4 (descargabilidad varía).** Thumbnail para UI. DigiKey y TME directos; Mouser tras Akamai (browser-grade); Farnell hay que ensamblar la URL o bump a v1.3. |

### Paramétricos (attributes / specs)

| unified_field_name | mouser path | digikey path | tme path | farnell path | tipo | por qué guardarlo |
|---|---|---|---|---|---|---|
| `parameters` (spec table) | `Parts[].ProductAttributes[]` ({AttributeName(localizado),AttributeValue}) | `Products[].Parameters[]` ({ParameterId,ParameterText,ValueText}; key estable=ParameterId) | `[/products/parameters]` `data.elements[].parameters.elements[]` ({id,name,values[]}) — **call aparte** | `products[].attributes[]` ({attributeLabel(localizado),attributeValue,attributeUnit}) — mezclado con compliance | array key/value | **4/4.** Tabla paramétrica (voltaje/frecuencia/temp/package/mounting). Núcleo del detalle de componente y búsqueda paramétrica. DigiKey usa ParameterId estable; Mouser/Farnell labels localizados; TME y DigiKey/Farnell mezclan o requieren endpoint extra. |

### Identidad (series, SKU proveedor, EAN/GTIN, cross-refs)

| unified_field_name | mouser path | digikey path | tme path | farnell path | tipo | por qué guardarlo |
|---|---|---|---|---|---|---|
| `supplier_sku` | `Parts[].MouserPartNumber` (puede ser 'N/A' en rollups) | `Products[].ProductVariations[].DigiKeyProductNumber` | `data.products.elements[].symbol` | `products[].sku` | string | **4/4** (ya parseado parcialmente). SKU del proveedor; en Mouser filtrar 'N/A'. |
| `manufacturer_id` | (`ActualMfrName` doc-only) | `Products[].Manufacturer.Id` (296) | `data.products.elements[].manufacturer.id` (77) | `products[].brandId` (1000062) | int/string | **3/4 (Mouser solo nombre).** FK estable de marca para dedupe cross-supplier. |
| `category_id` | (`MouserProductCategory` doc-only) | `Products[].Category.CategoryId` (32) | `data.products.elements[].category.id` (112875) | (vía attributes, no id top-level) | int | Parcial. FK de categoría para árbol/faceting. |
| `base_product_number` | (vía `AlternatePackagings`) | `Products[].BaseProductNumber.Name` ('NE555') | — | — | string | **Solo DigiKey.** Agrupa hermanos de packaging bajo una parte base. |
| `aliases` / `other_names` | `Parts[].AlternatePackagings[].APMfrPN` (¡leading space, trim!) | `Products[].OtherNames[]` (22 valores) | (vía `/products/related`) | — | array | Parcial. Señal fuerte de matching/dedupe y linking cross-supplier. DigiKey el más rico (22 aliases). |
| `ean_gtin` | — | — | `data.products.elements[].ean` (**frecuentemente vacío** '') | — | string | **Solo TME** (y poco fiable). EAN/GTIN como barcode; no usar como join key. |
| `series` | — | `Products[].Series.{Id,Name}` | — | — | string | **Solo DigiKey.** Serie de producto. |
| `alternate_packagings` (SKU hermanos) | `Parts[].AlternatePackagings[].APMfrPN` | `Products[].ProductVariations[]` (inline) / `/alternatepackaging` | (vía `/products/similar`) | `products[].packagingOptions[]` ({type,sku}, v1.3+) | array | Parcial. Variantes de packaging (tube/tray/T&R/cut-tape) como cross-references de sourcing. |

---

## 3. Recomendación de almacenamiento

### A) Columnas nuevas en `components` (escalares de alto valor, consultables/filtrables)

Campos atómicos que se consultan, filtran u ordenan frecuentemente y tienen (cuasi) 4/4 cobertura o son críticos de negocio:

- **Ciclo de vida**: `lifecycle_status` (enum normalizado propio), `last_buy_date`, `discontinued`, `end_of_life`. Justificación: drivers directos de alertas EOL y decisiones de sourcing; se filtran en listados. 4/4 en señal de lifecycle.
- **Logística core**: `moq`, `order_multiple`, `lead_time_days` (normalizado a días), `unit_weight_kg` (normalizado a kg). Justificación: 4/4 (MOQ/mult), necesarios para calcular cantidades comprables válidas y costeo; columnas porque entran en cálculos.
- **Media**: `image_url`. Justificación: el reporte DigiKey señala que `PhotoUrl` se fetchea hoy pero se descarta porque `SupplierQuote` no tiene campo de imagen → añadir `image_url` es el fix concreto. Para la datasheet, ver §1 (Blob + columnas `datasheet_blob_path`, `datasheet_source_url`, `datasheet_sha256`).

Nota: lifecycle/lead_time/MOQ llegan con **unidades y vocabularios distintos por proveedor** (Mouser localizado, DigiKey semanas-string, Farnell días/códigos) → las columnas guardan el **valor normalizado**; el crudo va al JSONB (abajo).

### B) JSONB por-proveedor (snapshot del payload crudo)

Una columna/tabla `supplier_payload` JSONB por oferta de proveedor (o tabla `supplier_offers` con `raw_payload jsonb`), guardando el objeto crudo tal cual (`MouserPart` / `Product` de DigiKey / `data.products.elements[]` de TME / `products[]` de Farnell). Justificación:
- Los reportes muestran **decenas de campos doc-only o raros** (Mouser: `StandardCost`, `IPCCode`, `RTM`, `PID`, `MultiSimBlue`; DigiKey: facetas `FilterOptions`, `SearchLocaleUsed`; Farnell: `discountReason`, `vatHandlingCode`, `inventoryCode`) que no justifican columna pero conviene no perder.
- Permite re-parsear sin re-pegarle a la API (presupuesto de quota, §4).
- Guardar junto al payload: `SearchLocaleUsed`/locale efectivo (DigiKey), `prices.currency/type/tax.rate` (TME), `storeInfo.id` (Farnell) → hace los precios self-describing y reproducibles (los cuatro reportes advierten que el precio es locale/currency-dependiente: EU key de Mouser en EUR coma-decimal, DigiKey EUR, TME NET+VAT, Farnell sin currency en payload).

### C) Tablas nuevas (relaciones 1:N)

1. **`component_parameters`** (`component_id`, `supplier`, `param_key`, `param_label`, `param_value`, `param_unit`). Justificación: los cuatro devuelven specs paramétricos como N pares name/value (Mouser `ProductAttributes`, DigiKey `Parameters` con `ParameterId` estable, TME `parameters.elements`, Farnell `attributes`). Es la tabla paramétrica núcleo del detalle de componente y de la búsqueda paramétrica; **hoy completamente descartada**. Usar `ParameterId` (DigiKey) o `param id` (TME) como key estable; para Mouser/Farnell normalizar labels localizados.

2. **`component_compliance`** (`component_id`, `supplier`, `code_type`, `code_value`). Justificación: export/aduanas y compliance llegan como N pares code/value heterogéneos por proveedor (Mouser `ProductCompliance`/`TradeCompliance` con ECCN+*HTS+TARIC+país, DigiKey `Classifications`, Farnell dentro de `attributes[]` con labels English estables `usEccn/euEccn/tariffCode/SVHC/MSL`). Una tabla code_type→value absorbe la heterogeneidad (Mouser da el set multi-país más rico; TME **no expone ninguno** en V2). Alternativamente, los más universales (`rohs_status`, `eccn`, `hts_code`, `country_of_origin`) pueden subir a columnas si se filtran mucho.

3. **`component_documents`** (`component_id`, `supplier`, `doc_type`, `url`, `file_name`, `size_bytes`, `language`, `blob_path`, `sha256`, `content_type`, `fetched_at`). Justificación: TME (`documents.elements[]` con DTE/INS/LNK/YTB) y Farnell (`datasheets[]` con múltiples entradas y `type`) devuelven **varios documentos por parte**; una parte puede tener múltiples datasheets. Soporta el patrón Blob de §1 (provenance + dedupe por sha256).

4. **`component_cross_refs`** (`component_id`, `supplier`, `ref_type`, `ref_mpn`/`ref_sku`). Justificación: alternates/substitutes/aliases/alternate-packagings son N:N (Mouser `AlternatePackagings`, DigiKey `OtherNames`+`/substitutions`+`/alternatepackaging`, TME `/related`+`/similar`, Farnell `packagingOptions`). Útil para dedupe, linking cross-supplier y resiliencia de sourcing. Nota: DigiKey substitutions/recomendados/kits cuestan **llamadas extra** (§4) → poblar bajo demanda, no en cada sync.

5. **`supplier_price_breaks`** (ya existe el concepto `SupplierPriceBreak`): asegurar que guarda `quantity`, `unit_price`, `currency` y el `to`/upper-bound de Farnell (`prices[].to`, hoy ignorado, sentinel 999999999=∞) para bandas cerradas inequívocas.

---

## 4. Gotchas y límites por proveedor

### Mouser (reporte MOUSER)
- **Rate limit**: 30 req/min y **1000 req/día** por API key (el adapter ya enforcea 30/min en bucket `supplier:mouser`). **No hay headers de rate-limit** (ni X-RateLimit/RateLimit/Retry-After). Burst de 3 calls en <1s → todas HTTP 200 sin error de quota → throttling no es estrictamente per-second. Over-limit se reporta como **HTTP 200 con entry en el array top-level `Errors[]`** (mismo canal que `InvalidApiKey`), NO como 429. El adapter debería inspeccionar `Errors[]` en general (p.ej. 'TooManyRequests'), no confiar en status codes.
- **Auth**: `?apiKey=` query param (env `MOUSER_API_KEY`). Errores (incl. InvalidApiKey) llegan con HTTP 200 en `Errors[]`.
- **Quirk de localización**: la dev key resuelve a storefront **EU (mouser.es)** → PriceBreaks en EUR con coma decimal y símbolo ('0,507 €'); VALUES de Description/Category/LeadTime/ProductAttributes/TradeCompliance localizados a español (KEYS siempre English). Parsing locale-tolerant (el `_PRICE_NUMERIC_RE` ya maneja coma decimal). No keyear lógica sobre texto localizado.
- **Matching**: `search/partnumber` matchea por **MPN del fabricante** aunque el campo se llame `mouserPartNumber`; un MPN único devuelve MUCHAS filas (NE555P=11, LM358=116). `Parts[0]` no garantiza el MPN base exacto. Filtrar filas rollup con `MouserPartNumber=='N/A'` (solo datasheet, sin precio/stock).
- **No hay endpoint de detalle/parametrics separado**: todos los search endpoints v2 devuelven el mismo `MouserPart`. v1 deprecado pero mismo shape.
- **Presupuesto ingesta**: 1 call por fetch (search trae todo). 1000/día limita el batch diario.

### DigiKey (reporte DIGIKEY)
- **Rate limit**: tier estándar comúnmente **1000 req/día**; **HTTP 429** al agotar quota diaria (el adapter lo mapea a `SupplierRateLimitedError`). Sin techo per-minuto documentado; el adapter auto-throttlea a 60 req/min. **No se observaron headers X-RateLimit-*** en los 200.
- **Auth**: OAuth2 client_credentials → Bearer; **token ~599s (~10 min)**, el adapter lo cachea con 30s de headroom. Apps de producción suelen requerir un OAuth redirect URI registrado incluso para client_credentials. Host sandbox y prod = `api.digikey.com`; el entorno de las credenciales (sandbox vs prod) debe coincidir o se obtiene auth/empty.
- **Presupuesto ingesta CRÍTICO**: cada endpoint de enriquecimiento (`media`/`pricing`/`substitutions`/`recommendedproducts`/`associations`/`alternatepackaging`) es una **request SEPARADA facturable** contra la quota diaria → la foto completa de una parte cuesta **~5-7 calls**. Con 1000/día, eso son ~140-200 partes/día completas. **Batch/cache agresivo**; poblar enriquecimiento bajo demanda, no en cada sync.
- **Quirks de datos**: `StandardPackage` (SPQ) **no fiable en keyword (0) pero correcto en `/pricing` (50)** → llamar `/pricing` cuando importe SPQ. `MyPricing[]` siempre vacío con app-only (requiere token con cuenta de cliente). `ManufacturerLeadWeeks` es **string** ('6'), parsear defensivo. Flags hazmat `ContainsLithium`/`ContainsMercury` **solo en `/pricing`**. Keyword usa fuzzy matching (5 productos para NE555P) → usar `ExactMatches[]` o filtrar por `ManufacturerProductNumber` en vez del `_pick_product` first-match. `productdetails` devuelve el **mismo shape** que keyword (no más rico).
- **Paths inconsistentes**: la mayoría `/products/v4/search/{productNumber}/<action>` pero `packagetypebyquantity` es `/products/v4/search/packagetypebyquantity/{productNumber}`. NO existe `/products/v4/recommendedproducts` top-level (404) ni `/associatedproducts` (usar `/associations`). URL-encodear el productNumber.

### TME (reporte TME)
- **Rate limit**: sin límite per-minuto explícito en V2; throttling a nivel cuenta (histórico ~cap concurrencia/burst). El adapter auto-impone **20 req/min** en bucket `supplier:tme` (dos calls por fetch_by_mpn). No se observaron 429 durante el probe (un webfetch de la **página de ayuda pública** sí dio 429 — es el website, no la API).
- **Auth**: OAuth2 client-credentials, POST `/auth/token`, **HTTP Basic = TME_TOKEN(50ch):TME_APP_SECRET(20ch)**. **Token TTL solo 300s (5 min)** → cachear/reusar el JWT (devuelve refresh_token pero el adapter re-autentica vía Basic, que funciona).
- **Presupuesto ingesta**: enriquecer una parte completa necesita **hasta 5 calls autenticadas**: `/products/search` + `/products/data` (scope=prices,stock) + `/products/parameters` + `/products/files` + `/products/related|similar`. Todas salvo auth aceptan **múltiples `symbols[]=` por call** → batchear por symbol para recortar requests.
- **Quirks de shapes**: DOS shapes distintos — `/products/search` envuelve en `data.products.elements[]`; `/products/data|files|parameters|related|similar` en `data.elements[]` (sin nodo 'products'). `/products/data` SOLO acepta `scope[]` 'prices'/'stock' (parameters/files/photos/documents/delivery → 400 `E_INPUT_PARAMS_VALIDATION_ERROR`). `/products/related` y `/similar` toman **`symbol=` SINGULAR** (no `symbols[]`) y devuelven arrays de strings a resolver con segunda call.
- **live_probe failures**: `/products/autocomplete` → **403 `E_AUTHORIZATION_FAILED`** para esta cuenta/scope (no todas las acciones habilitadas por token). `/products/categories`, `/products/delivery-time`, `/products/photos`, `/products/documents` → **404 `E_API_ACTION_NOT_FOUND`** (nombres V1-style que NO existen en V2).
- **Sin compliance/export en V2**: **no hay RoHS, REACH, ECCN, HTS/TARIC/CN, ni country-of-origin** en ningún endpoint (confirmado escaneando nombres de parámetros). Sourcear esos de otro lado.
- **Otros**: URLs protocol-relative (prepend `https:`); imágenes watermarked+signed (no quitar query params o el CDN rechaza); `product_status[]` enums TME-specific (array vacío = normal/activo); EAN frecuentemente vacío (no usar como join key). Error envelope: `code`/`error_code` (6=validation,9=action-not-found,4=authz)/`error_data[]`.

### Farnell / element14 (reporte FARNELL)
- **Rate limit**: tier Free/Basic **2 calls/segundo, 1000 calls/día**. Throttling → **HTTP 429** al exceder 2/s o 1000/día. `resultsSettings.numberOfResults` máx 50/call (keyword paginado vía `offset`).
- **Auth**: API key de 24-char alfanumérica en query string (`callInfo.apiKey`/`userInfo.apiKey`; ambas casings aceptadas). **Sin IP whitelist** para Standard pricing; **Contract pricing requiere** `customerId` + `timestamp` + **HMAC-SHA1 `signature`**. **Key malo NO es 401** en el search endpoint → HTTP 200 con resultados vacíos o un envelope `Fault` (key muerto es indistinguible de no-match genuino).
- **Quirk de versionNumber (gap importante)**: el adapter NO envía `versionInfo.versionNumber` → obtiene el field set base 1.0-era incluso con `responseGroup=large`. Por eso faltaron en el probe: `productURL`, `mainImageURL`/`thumbNailImageURL`, `unitOfMeasureCode`, `packageName`, `orderMultiples`, `packagingOptions`, `productOverview`, `costIncTax`. **Bump a `versionNumber=1.4`** desbloquea todo sin cambiar endpoint.
- **Quirk de datasheets**: el comentario del adapter "Basic/Large no incluye datasheet URLs" es **WRONG** → `datasheets[]` SÍ aparece en `responseGroup` {medium,large,prices}, solo que sparse (NE555P sin; LM358N/1N4148/ATMEGA328P-PU/STM32F407 sí). Setear `datasheet_url=None` incondicional **descarta datos reales**.
- **Quirk de root key**: cambia con el tipo de term — `any:`/`id:` → `keywordSearchReturn`; `manuPartNum:` → `manufacturerPartNumberSearchReturn`; premier/element14 part → `premierFarnellPartNumberReturn`. El adapter **solo lee `body['keywordSearchReturn']`** → cualquier switch a `manuPartNum:` daría 0 resultados silenciosamente.
- **Quirks de datos**: **sin currency en payload** (`prices[].cost` es lo que implique `storeInfo.id`: es.farnell.com=EUR; `_currency_for_store` es la única fuente de verdad). Export/compliance (`tariffCode`/`usEccn`/`euEccn`/`rohsCompliant`/`SVHC`/`hazardous`/`MSL`/`productTraceability`) **NO son top-level** → filas dentro de `attributes[]` con labels English estables, mezcladas con paramétricos localizados. Labels paramétricos **localizados** al storefront (español en es.farnell.com) → query un store canónico (uk.farnell.com=English) o mapa de normalización. `unitOfMeasure` localizado ('CADA' ES vs 'EACH' UK) → preferir `unitOfMeasureCode` (v1.3). `translatedMinimumOrderQuality` es MOQ (typo 'Quality'). `related{}` solo dice SI existen alternativas (booleans), no cuáles, y las keys vienen **dobladas/mal escritas** (`containcontainRoHSAlternatives`) → match defensivo. `prices[].to=999999999` = ∞. **Sin campo de peso ni dimensiones** en el Search API. No hay endpoint de detalle separado: `/catalog/products` con responseGroup+versionNumber devuelve todo.
- **live_probe failure (artefacto de entorno, no de API)**: desde el sandbox, `api.element14.com` y los hosts de datasheet (`www.farnell.com/datasheets`, `4donline.ihs.com`) son alcanzables; los hosts **STOREFRONT/CDN `*.farnell.com`** (para imágenes de producto) están bloqueados (`rc=92`/HTTP 000, Akamai-fronted). Las URLs de imagen deberían resolver desde egress normal de servidor; confirmar `Content-Type: image/jpeg` en el primer fetch real. **Opción robusta**: enviar `versionNumber=1.3` y usar `mainImageURL`/`thumbNailImageURL` directos.

### Presupuesto de quota para ingesta + sync diario (síntesis)
- **Todos** comparten ~**1000 calls/día** (Mouser, DigiKey, Farnell explícitos; TME por cuenta). Mouser=30/min, Farnell=2/s, DigiKey~60/min self-throttle, TME=20/min self-throttle.
- **Costo por parte completa**: Mouser ~1 call; Farnell ~1 call (todo en `/catalog/products`); TME hasta 5 calls (batcheables vía `symbols[]`); DigiKey **5-7 calls** (cada enrichment endpoint factura aparte).
- **Implicación**: DigiKey es el cuello de botella de quota → con 1000/día, full-enrich ~140-200 partes/día. Estrategia: en el **sync diario** refrescar solo precio/stock/lifecycle (keyword/search, 1 call); poblar paramétricos/media/cross-refs/documentos **bajo demanda o en backfill espaciado**. Batchear TME por `symbols[]`. Cachear tokens (DigiKey 599s, TME 300s).

---

## Anexo: estado de los live probes

- **mouser**: ok — HTTP 200 with real MOUSER_API_KEY from .env. Probed NE555P (11 results), STM32F407VGT6 (2), GRM188R71H104KA93D (1), LM358 (116). Raw JSON saved to /tmp/mouser_ne555p.json, /tmp/mouser_stm32.json, /tmp/mouser_lm358.json, /tmp/mouser_murata.json. NOTE: this dev API key resolves to the EU storefront (mouser.es): PriceBreaks come back in EUR with comma decimals ('0,507 €'), and Description/Category/LeadTime/ProductAttributes/TradeCompliance string VALUES are localized to Spanish (e.g. 'En existencias', '42 Días', 'Empaquetado', 'País de origen'). Field KEYS are always English. Parsing must be locale-tolerant (the existing _PRICE_NUMERIC_RE already handles comma decimals).
- **digikey**: ok — OAuth2 client_credentials succeeded (token_type=Bearer, expires_in=599); POST /products/v4/search/keyword for "NE555P" returned HTTP 200, 37544 bytes, 5 Products + 1 ExactMatch (ProductsCount=11). Also probed live with HTTP 200: GET .../productdetails, .../media, .../pricing, .../substitutions (12 subs), .../recommendedproducts, .../associations, .../alternatepackaging (empty for this MPN). Headers: X-DIGIKEY-Client-Id + Locale Site=ES/Language=en/Currency=EUR. Credentials read from .env, never printed.
- **tme**: ok
- **farnell**: ok — HTTP 200 against https://api.element14.com/catalog/products with the real FARNELL_API_KEY and FARNELL_STORE_ID from .env (key never printed). term=any:NE555P returned keywordSearchReturn.numberOfResults=3, first product sku=3006909 TEXAS INSTRUMENTS NE555P. Probed multiple variants: es/uk/newark stores, responseGroup=large, term=manuPartNum: (different root), and 5 extra MPNs (LM358N, STM32F407VGT6, ATMEGA328P-PU, 1N4148, SN74HC595N) to capture datasheets[] and lifecycle status codes. Raw JSON saved to /tmp/farnell_ne555p.json and /tmp/ds_*.json.
