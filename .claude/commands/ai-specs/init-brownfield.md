---
name: "ai-specs: Init Brownfield"
description: Adopt an existing codebase into the SDD workflow. Discovers stack, documents architecture, generates technical and functional baselines.
category: Workflow
tags: [standards, brownfield, bootstrap, baseline, adoption]
---

# ai-specs:init-brownfield — Adopt an Existing System

This is the adoption command for existing (brownfield) projects.
It analyzes the current codebase and produces everything needed to start working with the SDD/OpenSpec workflow on top of what already exists.

**It populates or updates two baselines:**

- `ai-specs/specs/*` — Technical baseline (standards, data model, API spec, dev guide)
- `openspec/specs/*` — Functional baseline (capabilities and behavior specs)

**It does NOT:**

- Modify existing source code
- Restructure the project
- Delete anything

---

## Narrative

The command follows four explicit phases:

1. **Discover** — Understand the current state of the system
2. **Normalize** — Generate technical standards that reflect reality
3. **Baseline** — Capture functional capabilities as OpenSpec specs
4. **Prepare** — Leave the project ready for incremental SDD changes

---

## Phase 1: Discover Current State

### 1.1 Validate template availability

Check that both template files exist:

- `ai-specs/specs/templates/backend-standards-template.mdc`
- `ai-specs/specs/templates/frontend-standards-template.mdc`

If any template is missing → FAIL immediately, show missing path, stop.

### 1.2 Optional Integrations (MCP)

Same as init-greenfield: offer Notion, Jira, Figma MCP auth if available.
If any MCP is authenticated, use it to gather existing project context (architecture docs, existing tickets, design systems).

### 1.3 Automated stack detection

Before asking the user anything, analyze the codebase to detect:

**Package/dependency files** (read and parse):
- `package.json`, `package-lock.json`, `pnpm-lock.yaml`, `yarn.lock`
- `requirements.txt`, `pyproject.toml`, `Pipfile`
- `go.mod`, `Cargo.toml`, `Gemfile`, `pom.xml`, `build.gradle`
- `composer.json`, `.csproj`, `*.sln`

**Configuration files** (detect conventions):
- `.eslintrc*`, `.prettierrc*`, `biome.json`, `deno.json`
- `tsconfig.json`, `jsconfig.json`
- `Dockerfile`, `docker-compose.yml`
- `.github/workflows/*`, `.gitlab-ci.yml`, `Jenkinsfile`
- `.env`, `.env.example`
- `openapi.yaml`, `openapi.json`, `swagger.*`

**Source structure** (detect architecture):
- Map top-level directories under `src/`, `app/`, `lib/`, `server/`, `client/`, `frontend/`, `backend/`, `packages/`
- Identify architectural patterns (MVC, DDD layers, feature-based, etc.)
- Detect monorepo vs single repo

**Existing tests** (detect testing approach):
- Look for `__tests__/`, `test/`, `tests/`, `spec/`, `cypress/`, `e2e/`, `playwright/`
- Identify frameworks from config files or imports

**Database/ORM** (detect data layer):
- Migration files, schema files, Prisma schema, TypeORM entities, Sequelize models, Drizzle config
- Database connection strings in config (type only, never capture credentials)

**API layer** (detect API style):
- Route files, controller files, resolver files (GraphQL)
- Existing OpenAPI/Swagger specs
- REST vs GraphQL vs gRPC indicators

### 1.4 Present findings and confirm

Present the detected stack as a structured summary:

```
## Detected Stack

### Backend
- Language: TypeScript (Node.js 20)
- Framework: Express 4.18
- Architecture: Feature-based (src/features/*)
- Auth: Passport.js (JWT strategy)
- Validation: Zod

### Data
- Database: PostgreSQL (detected from docker-compose)
- ORM: Prisma 5.x
- Migrations: Prisma Migrate (prisma/migrations/)

### API
- Style: REST
- OpenAPI: Yes (docs/openapi.yaml)
- Error format: { error: string, code: number }
- Versioning: URL prefix (/api/v1/)

### Frontend
- Framework: React 18 + Vite
- State: Zustand
- Routing: React Router v6
- Styling: Tailwind CSS
- Components: Radix UI

### Testing
- Unit: Vitest
- E2E: Playwright
- Coverage: ~62% (estimated from test file count)

### Tooling
- Lint: ESLint (flat config)
- Format: Prettier
- CI: GitHub Actions
- Monorepo: No
```

Use AskUserQuestion to confirm:
- "Is this accurate? Anything to correct or add?"

For anything NOT detected, ask follow-up questions (same as init-greenfield would, but only for gaps).

### 1.5 Architecture deep-dive

After stack confirmation, analyze and present:

**Module/capability map:**
- List the main modules, features, or bounded contexts found
- For each: brief description of what it appears to do (based on file/folder names, route names, model names)
- Estimated size (small/medium/large based on file count)

Example:
```
## Detected Modules

1. **auth** — Authentication and session management (src/features/auth/)
   Routes: /api/v1/auth/login, /register, /refresh, /logout
   Models: User, Session
   Size: Medium (~15 files)

2. **products** — Product catalog and search (src/features/products/)
   Routes: /api/v1/products (CRUD), /search
   Models: Product, Category
   Size: Large (~25 files)

3. **orders** — Order processing (src/features/orders/)
   Routes: /api/v1/orders (CRUD), /checkout
   Models: Order, OrderItem
   Size: Medium (~18 files)

4. **notifications** — Email and push notifications (src/features/notifications/)
   Routes: internal only (no public API)
   Models: Notification, NotificationPreference
   Size: Small (~8 files)
```

Use AskUserQuestion:
- "Is this module map correct? Any modules I missed or misidentified?"
- "Are there any modules that are deprecated, legacy, or should be excluded from specs?"

---

## Phase 2: Normalize Standards

Generate technical standards that **reflect the existing codebase**, not a theoretical ideal.

### 2.1 Generate backend standards

Create: `ai-specs/specs/backend-standards.mdc`

Rules:
- Use the template for STRUCTURE ONLY (headings and section order)
- Do NOT copy template example content verbatim
- **Document what IS, not what SHOULD BE** — standards must match the existing codebase
- If the codebase uses a pattern (e.g., feature-based folders), document that as the standard
- If the codebase is inconsistent in some area, note it and propose a convention (marked as PROPOSED)
- Provide concrete conventions and commands based on existing tooling

**Parity with init-greenfield — MANDATORY:** The generated document MUST be indistinguishable in format, sections, and level of detail from one generated by `init-greenfield`. The only difference is that data is extracted from the existing code instead of asked to the user. It MUST include all sections that init-greenfield requires:
- Folder structure conventions
- API patterns
- Data access patterns
- Error handling conventions
- Authentication rules
- Logging conventions
- Testing rules
- Migration strategy
- Definition of Done for backend changes

### 2.2 Generate frontend standards

Create: `ai-specs/specs/frontend-standards.mdc`

Same rules as backend: document existing reality, flag inconsistencies as PROPOSED.

**Parity with init-greenfield — MANDATORY:** Same parity rule as backend. The document MUST include all sections that init-greenfield requires:
- Component structure conventions
- State management patterns
- Styling conventions
- Accessibility baseline
- Testing strategy
- Definition of Done for frontend changes

### 2.3 Generate data model documentation (MANDATORY)

Create: `ai-specs/specs/data-model.md`

Use the template at `ai-specs/specs/templates/data-model-template.md` for STRUCTURE ONLY.

Process:
1. **Scan all model/entity/schema definitions** in the codebase:
   - ORM models (Prisma schema, TypeORM entities, Sequelize models, Mongoose schemas, Drizzle schemas, etc.)
   - Database migration files (to understand field types, constraints, indexes)
   - If no ORM: raw SQL schema files, or infer from code that interacts with the DB
2. **For each entity/model, document:**
   - Name and purpose
   - All fields with types, constraints, and validation rules
   - Primary keys, foreign keys, unique constraints, indexes
   - Relationships (one-to-many, many-to-many, etc.)
3. **Generate an Entity Relationship Diagram** in Mermaid format showing all entities and their relationships
4. **Document key design principles** observed in the data layer (normalization level, soft deletes, timestamps, audit fields, etc.)

Rules:
- Be exhaustive — every model in the codebase must appear in this document
- Use the actual field names, types, and constraints from the code
- If validation rules exist (Zod schemas, class-validator decorators, Joi schemas, etc.), include them
- If a model has no clear purpose from naming alone, inspect its usage in services/controllers to describe it

### 2.4 Generate API specification (MANDATORY)

Create: `ai-specs/specs/api-spec.yml`

Process:
1. **Check if an OpenAPI/Swagger spec already exists** in the project (common locations: `docs/`, `swagger/`, root, `api/`)
   - If found and up-to-date: adopt it — copy or symlink into `ai-specs/specs/api-spec.yml`
   - If found but outdated: use as starting point, update by scanning routes
   - If not found: generate from scratch
2. **Scan all route/endpoint definitions:**
   - Express routes (`router.get/post/put/delete/patch`)
   - NestJS controllers and decorators
   - FastAPI/Flask/Django URL patterns
   - GraphQL resolvers and schema definitions
   - Any route registration pattern in the codebase
3. **For each endpoint, document:**
   - HTTP method and path
   - Request parameters (path, query, body) with types
   - Request body schema (derive from validation schemas if available)
   - Response schema and status codes (derive from controller return types and error handlers)
   - Authentication requirements (which middleware/guards are applied)
   - Rate limiting or other middleware
4. **Output as valid OpenAPI 3.x YAML**

Rules:
- Every route in the codebase must be documented
- Derive schemas from actual validation/DTO definitions when possible
- If response types are unclear, mark with `# TODO: verify response schema`
- Include authentication schemes (Bearer, API key, session, etc.)
- Include error response formats (derive from error handling middleware)

### 2.5 Generate development guide (MANDATORY)

Create: `ai-specs/specs/development_guide.md`

Use the template at `ai-specs/specs/templates/development_guide-template.md` for STRUCTURE ONLY.

Process:
1. **Scan for setup/run instructions** — README, Makefile, docker-compose, package.json scripts, Procfile
2. **Document:**
   - Prerequisites (Node version, Docker, environment variables from .env.example)
   - How to install dependencies
   - How to run the project locally (dev mode)
   - How to run tests
   - How to run migrations
   - How to build for production
   - CI/CD pipeline overview (from .github/workflows or equivalent)
   - Deployment process (if detectable)
   - Environment variables (name and purpose, never actual values)

### 2.6 Adopt existing documentation

If any of the above files already exist in the project at non-standard locations (e.g., an OpenAPI spec at `docs/openapi.yaml`, or a data model doc in `docs/`):

- Ask the user: "I found existing documentation at `<path>`. Do you want me to adopt it into `ai-specs/specs/` or generate fresh from the codebase?"
- If adopting: copy into `ai-specs/specs/` and verify completeness against actual code
- If generating fresh: use the existing doc as reference but scan the codebase for accuracy

---

## Phase 3: Baseline Functional Specs

Generate OpenSpec specs that capture the current functional behavior of the system.

### 3.1 Generate capability specs

For each feature/functionality identified in Phase 1.5, create:

`openspec/specs/<feature-name>/spec.md`

**Granularity rule — CRITICAL:** Generate ONE spec per independently observable feature, at the same granularity level that `new-us` would produce for each user story. Do NOT consolidate multiple features into a single spec.

**Separation criteria:** If a capability could be a standalone user story, it gets its own spec. Examples:
- CRUD operations on an entity → one spec
- Dashboard/analytics view → separate spec
- Navigation/layout (sidebar, navbar) → separate spec
- Seed data / demo data → separate spec
- Authentication → separate spec
- Each distinct UI view that is not just a sub-component → separate spec

**Anti-pattern:** Do NOT group "companies CRUD + companies UI + seed data" into a single "companies" spec. These are separate features.

Format (following OpenSpec conventions):

```markdown
# <Feature Name> Specification

## Purpose
<Brief description of what this feature does in the system>

## Requirements

### Requirement: <Name>
The system <SHALL|MUST|SHOULD> <behavior description>.

#### Scenario: <Scenario name>
- **GIVEN** <precondition>
- **WHEN** <action>
- **THEN** <expected outcome>
```

Rules:
- **Use LITE spec format** — short, behavior-first requirements
- **Only spec observable behavior** — what the API does, what the UI shows, not internal implementation
- **Derive from routes, models, and tests** — use existing tests as scenario sources when available
- **Mark confidence levels:**
  - Requirements derived from tests or explicit API contracts → high confidence (no marker needed)
  - Requirements inferred from code reading → mark with `<!-- inferred -->`
  - Requirements guessed from naming/structure → mark with `<!-- estimated -->`
- **Don't over-spec** — it's better to have 3 solid requirements than 15 guesses
- **Group by feature**, not by technical layer or module

### 3.2 Present baseline summary

Show a summary of generated specs:

```
## Functional Baseline Generated

| Capability | Requirements | Scenarios | Confidence |
|---|---|---|---|
| auth | 4 | 8 | High (from tests) |
| products | 6 | 12 | Medium (from routes + models) |
| orders | 5 | 9 | Medium (from routes) |
| notifications | 2 | 3 | Low (inferred from code) |

Total: 17 requirements, 32 scenarios across 4 capabilities
```

Use AskUserQuestion:
- "Review the generated specs? I can show any capability in detail."
- "Any capabilities that need more detail or corrections?"

---

## Phase 4: Prepare for Future Changes

### 4.1 Update openspec/config.yaml

Update the config with discovered project context:

```yaml
schema: spec-driven

context: |
  Tech stack: <detected stack summary>
  Architecture: <detected pattern>
  Project type: brownfield (adopted <date>)
  Key conventions: <brief list>
```

### 4.2 Verify project readiness

Run a quick checklist:

- [ ] `ai-specs/specs/backend-standards.mdc` exists and has content
- [ ] `ai-specs/specs/frontend-standards.mdc` exists and has content
- [ ] `ai-specs/specs/data-model.md` exists and documents all models
- [ ] `ai-specs/specs/api-spec.yml` exists and documents all endpoints
- [ ] `ai-specs/specs/development_guide.md` exists
- [ ] `openspec/specs/` has at least one capability spec
- [ ] `openspec/config.yaml` has project context

**Parity checklist (brownfield-specific):**
- [ ] `backend-standards.mdc` has the same sections as init-greenfield would generate (folder structure, API patterns, data access, error handling, auth, logging, testing, migration, Definition of Done)
- [ ] `frontend-standards.mdc` has the same sections as init-greenfield would generate (component structure, state management, styling, accessibility, testing, Definition of Done)
- [ ] Number of functional specs reflects each independently observable feature (NOT consolidated by module)
- [ ] `data-model.md` includes ER diagram in Mermaid format (as per template)
- [ ] `api-spec.yml` uses valid OpenAPI 3.x format with all endpoints documented

### 4.3 Report results

Display a final summary:

```
## Brownfield Adoption Complete

### Technical Baseline (ai-specs/specs/)
- ✓ backend-standards.mdc (from detected Express/TypeScript stack)
- ✓ frontend-standards.mdc (from detected React/Vite stack)
- ✓ data-model.md (12 models, 85 fields, ER diagram)
- ✓ api-spec.yml (23 endpoints, OpenAPI 3.x, auth schemes documented)
- ✓ development_guide.md (setup, scripts, CI/CD, env vars documented)

### Functional Baseline (openspec/specs/)
- ✓ auth/spec.md (4 requirements, 8 scenarios)
- ✓ products/spec.md (6 requirements, 12 scenarios)
- ✓ orders/spec.md (5 requirements, 9 scenarios)
- ✓ notifications/spec.md (2 requirements, 3 scenarios)

### Ready For
- /ai-specs:new-us → create new user stories
- /opsx:new → create changes with delta specs
- /opsx:explore → investigate the codebase

### Recommendations
- [ ] Review generated specs and correct any inaccuracies
- [ ] Add scenarios for critical business logic not captured
- [ ] Consider running /opsx:explore on the most complex module
```

---

## Guardrails

- **Never modify source code.** This command only generates documentation and spec files.
- **Never generate Docker, docker-compose, or pre-commit files.** Brownfield assumes these already exist. Only document them in `development_guide.md`.
- **Never invent stack details.** If detection fails, ask the user.
- **Document what IS, not what SHOULD BE.** Standards must reflect the actual codebase. Improvements go in future changes.
- **Prefer accuracy over completeness.** A small accurate baseline beats a large inaccurate one.
- **Mark uncertainty.** Use confidence markers on inferred specs.
- **Respect existing documentation.** If the project already has docs (OpenAPI, README, etc.), adopt them rather than regenerating.
- **Don't overwrite existing specs.** If `openspec/specs/` already has content, ask before modifying.
- **Output parity with init-greenfield.** Generated standards MUST have the same sections, format, and level of detail as init-greenfield output. The only difference is that data comes from the existing codebase instead of user input.
- **Feature-level spec granularity.** Each independently observable feature gets its own spec. Never consolidate multiple features into one spec.
- Templates define STRUCTURE ONLY (never copy example content).
