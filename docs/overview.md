# ada_asm — Project Overview

Working document — high-level synthesis of the project before standards and detailed specs are filled in. Built from the current Notion backlog and Figma design file.

## What it is

ADA ASM is an internal **asset management** system that organises electronic components, modules, and projects, and keeps them in sync with the company's operational tools (accounting/ERP, electronic catalog, supplier price lists).

## Domain model

The system manages a hierarchical tree of assets, where every leaf is either a `Componente` (component) or a `Módulo` (module).

```
Proyecto
  └─ Módulo (may contain other Módulos or Componentes; tree of unlimited depth)
       └─ Componente (leaf — has name, description, datasheet link, warehouse location, current price)
```

- A `Módulo` price is computed as the sum of the current prices of its children.
- Both `Componente` and `Módulo` are mirrored as products in the external ERP (see Integrations).

### Component classification — Tier

Every `Componente` carries a **Tier** that reflects the complexity of the part and the risk of using a non-NATO source for it. The Tier is a leaf property; `Módulo` and `Proyecto` aggregate the worst (highest-risk) Tier of their descendants.

| Tier   | Typology                              | Risk      |
| ------ | ------------------------------------- | --------- |
| Tier 1 | Chips and microcontrollers            | Very high |
| Tier 2 | Sensors                               | High      |
| Tier 3 | Passive components                    | Medium    |
| Tier 4 | Plastics, boards, connectors          | Low       |

### Component classification — NATO Scoring

In parallel, every `Componente` carries a **NATO Scoring** that captures whether the part has been manufactured under NATO supply-chain rules. The score doubles as the audit trail when a `Proyecto` declares itself NATO-compliant: the project's worst component score becomes the project's score.

| Score | Label                                              | Meaning                                |
| ----- | -------------------------------------------------- | -------------------------------------- |
| A+    | 100 % OTAN — all components verified               | Best case                              |
| A     | OTAN — components from OTAN countries              |                                        |
| B     | Allied OTAN — components from allied countries     |                                        |
| C     | Neutral — review required                          |                                        |
| D     | High risk — component origin not verified          |                                        |
| F     | Not OTAN — components from non-OTAN countries      | Blocks NATO-compliant projects         |

`Módulo` and `Proyecto` aggregate the worst NATO score of their descendants, mirroring the Tier rule.

### Roadmap properties — to spec when the entities land

Captured here so they are not forgotten when we draft the US that introduces each entity:

- **`Componente`** will also store `tier`, `nato_score`, plus per-supplier history.
- **`Módulo`** and **`Proyecto`** will surface a `rolled_up_tier` and a `rolled_up_nato_score` derived from their tree.
- **Supplier-side time series** — beyond the daily price snapshot already planned (US 8), we will also keep a **daily stock snapshot per supplier per component** (for availability alerts and lead-time analytics). Same shape as `PriceSnapshot` (append-only, partitioned by month).

## External integrations

| System  | Role                                                                                                                                         |
| ------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| Holded  | Accounting/ERP. Two-way sync of `Proyecto`, `Módulo` and `Componente` (as Holded products). No native webhooks → polling / event capture.    |
| KiCAT   | Electronic component catalog. Each `Componente` links to its datasheet and the current supplier price.                                       |
| Suppliers (multiple) | Source of price tiers (10 / 100 / 1000 units) pulled daily into a price time series for components and modules.                   |

## Backlog (Notion database `ada_asm`)

Eight tasks captured at this point. Sequencing TBD.

| #  | Title                                                            | Summary                                                                                              |
| -- | ---------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| 1  | Login en ASM 1.0                                                 | User/password login + password recovery. Tech choice must allow per-project roles/permissions later. |
| 2  | Creación de proyecto en ASM automático desde Holded              | Pull projects from Holded into ASM; capture create + edit events.                                    |
| 3  | Creación de Módulo en ASM                                        | UI + entity for `Módulo`; allows hierarchical grouping of components.                                |
| 4  | Creación de Componentes en ASM                                   | UI + entity for `Componente` (name, description, datasheet link, warehouse location).                |
| 5  | Creación / Actualización de componentes en Holded — Productos    | Push components to Holded as products. API only allows one-by-one operations → progress counter UI.  |
| 6  | Creación / Actualización de un módulo en Holded                  | Push modules to Holded as products with rolled-up price.                                             |
| 7  | Actualización de componentes en KiCAT                            | Sync component data fields and supplier price/datasheet links into KiCAT.                            |
| 8  | Bulk update diario de precios de componentes y módulos           | Daily job: fetch supplier prices for 10/100/1000 units → store as a date-stamped time series.        |

## UI scope (Figma — `pMUgDI7rbRRzVWLCJhoVnY`)

Seven top-level frames, all 1459×1043 (desktop). They share a common `DashboardLayout` (header + sidebar of 256 px + central container of 1203 px).

| Frame                    | Purpose                          |
| ------------------------ | -------------------------------- |
| Vista Proyectos          | Project list                     |
| Vista Detalle Proyecto   | Project detail                   |
| Vista Editar Proyecto    | Project edit                     |
| Eliminar Proyecto        | Project deletion confirmation    |
| Vista Módulos            | Module list / hierarchy          |
| Vista añadir módulo      | New module form                  |
| Vista Componentes        | Component list / edit            |

## Sources

- Notion database (backlog): https://www.notion.so/35a04e35e0538081ba5ec03cdfa67199
- Notion parent page (`Proyectos SDD`): https://www.notion.so/31a04e35e053807c819dcd5c9c43b2fb
- Figma design file (`ada_asm`): https://www.figma.com/design/pMUgDI7rbRRzVWLCJhoVnY/ada_asm

## Open questions to resolve before / during init

- **Stack:** language, framework, database, hosting target — not yet decided.
- **Auth:** which technology will be chosen for the login layer to allow future per-project roles/permissions.
- **Integrations:** API contracts with Holded and KiCAT (endpoints, auth, rate limits).
- **Pricing rules:** how the "current price" of a `Componente` is selected when several suppliers are available; rounding/currency rules; behaviour when a supplier price is missing.
- **Design system:** Figma tokens, components and Code Connect mappings have not been inspected yet.
- **Permissions model:** scope of "per-project roles" (only access, or also edit/approve flows).
