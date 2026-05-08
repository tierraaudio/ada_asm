---
name: "ai-specs: Init Greenfield"
description: Generate definitive backend and frontend standards from templates for a new (greenfield) project
category: Workflow
tags: [standards, templates, bootstrap]
---

Generate missing definitive standards files for this repository using the provided templates and the project's actual tech stack.

Goal:
Create (or update if empty) the following files:

- ai-specs/specs/backend-standards.mdc
- ai-specs/specs/frontend-standards.mdc

Templates:

- ai-specs/specs/templates/backend-standards-template.mdc
- ai-specs/specs/templates/frontend-standards-template.mdc

---

## Steps

---

### 0. Validate template availability

Check that both template files exist.

If any template is missing:

- FAIL immediately
- Show the missing path
- Do not continue

---

### 1. Optional Integrations (MCP)

This project includes support for external integrations via MCP (Model Context Protocol).

The following tools can be connected optionally:

- [ ] Notion (User stories / documentation)
- [ ] Jira (Issue management via Atlassian)
- [ ] Figma (Design system / UI components)

These integrations are not required.  
If none are authenticated, the project will continue operating in manual mode without disruption.

Authentication (per user):

1. Open Claude Code in this repository.
2. Run the command `/mcp`.
3. For each integration you want to enable, click **Authenticate**.
4. Complete the login process in your browser.

Quick Verification:

After authentication, test the connection:

- Notion → “List my databases” or “Search pages containing ‘Spec’”
- Jira → “Search issues assigned to me”
- Figma → “List recent team files”

If you choose not to connect any tools now, you may proceed with the workflow normally.

If any MCP integration is authenticated, you may use it to gather relevant project context before asking questions in Step 2.

- If Notion is connected, search for architecture, technical decisions, or existing specifications.
- If Jira is connected, identify project keys or recurring issue patterns.
- If Figma is connected, inspect the primary design system or UI constraints.

Use this information to reduce redundant questions.

### 2. Collect project stack information

Before asking questions, verify whether relevant information has already been retrieved from MCP integrations.

Use the AskUserQuestion tool to gather the necessary stack details.

Minimum required information:

Backend:
- Language
- Framework
- Architecture pattern
- Validation approach
- Authentication strategy
- Background jobs (if any)

Data:
- Database
- ORM / Query builder
- Migration strategy

API:
- REST or GraphQL
- OpenAPI version (if applicable)
- Error response format
- Versioning strategy

Testing:
- Unit testing framework
- Integration / e2e framework
- Coverage expectations

Frontend:
- Framework
- State management approach
- Routing
- Styling solution
- Component library (if any)

Tooling:
- Linting
- Formatting
- CI/CD
- Monorepo or single repo

If any answer is vague or missing, ask follow-up questions.

---

### 3. Generate backend standards

Create:

ai-specs/specs/backend-standards.mdc

Rules:

- Use the template for STRUCTURE ONLY (headings and section order).
- Do NOT copy template example content verbatim.
- Replace generic placeholders with stack-specific rules.
- Provide concrete conventions and commands.
- Do not invent tools not confirmed by the user.

Must include:

- Folder structure conventions
- API patterns
- Data access patterns
- Error handling conventions
- Authentication rules
- Logging conventions
- Testing rules
- Migration strategy
- Definition of Done for backend changes

---

### 4. Generate frontend standards

Create:

ai-specs/specs/frontend-standards.mdc

Rules:

- Use the template for STRUCTURE ONLY.
- Do NOT copy example content verbatim.
- Provide stack-specific conventions.

Must include:

- Component structure conventions
- State management patterns
- Styling conventions
- Accessibility baseline
- Testing strategy
- Definition of Done for frontend changes

---

### 5. Generate Docker scaffolding

Based on the confirmed stack from Step 2, generate the following files at the project root:

#### 5.1 `Dockerfile` (backend)

Create `backend/Dockerfile` (or `Dockerfile` if monolith):

Rules:
- Use the confirmed language/framework from Step 2.
- Multi-stage build when appropriate (build + runtime).
- Install only production dependencies by default.
- Expose the correct port for the framework.
- Use a non-root user for runtime.
- Include a health check endpoint if the framework supports it.

#### 5.2 `Dockerfile` (frontend)

Create `frontend/Dockerfile` (if frontend exists):

Rules:
- Use a build stage (e.g., `node:*-alpine` for Node projects) + a lightweight serve stage (e.g., `nginx:alpine` or `serve`).
- Copy build artifacts only to the serve stage.
- Expose the correct port (default 3000 or 80 for nginx).
- Support environment variables at build time via build args (e.g., `VITE_API_URL`).

#### 5.3 `docker-compose.yml`

Create `docker-compose.yml` at the project root:

Rules:
- Include services for: database (if any), backend, frontend, and a migration/seed step if applicable.
- Use the confirmed database from Step 2 (e.g., `postgres:16-alpine`).
- Backend depends on database (with healthcheck).
- Frontend depends on backend.
- Use environment variables for all configuration (DB connection, API URLs, CORS origins).
- **API URL convention**: The `VITE_API_URL` (or equivalent) MUST point to the backend's **base URL only** (e.g., `http://localhost:8000`). Route prefixes like `/api/v1` are the backend's responsibility — do NOT duplicate them in env vars.
- **CORS**: Backend `CORS_ORIGINS` MUST include both `localhost:<frontend-port>` AND the machine hostname pattern (e.g., `http://*.local:<frontend-port>`) for LAN access.
- Map ports to host (use standard ports, document if changed).
- Include a named volume for database persistence.
- Add `.dockerignore` files to backend and frontend directories.

#### 5.4 `.dockerignore` files

Create `.dockerignore` in each service directory:

- Exclude: `node_modules/`, `__pycache__/`, `.git/`, `.env`, `*.pyc`, `.venv/`, `dist/`, `build/`
- Keep it minimal and relevant to the stack.

---

### 6. Generate pre-commit configuration

Create `.pre-commit-config.yaml` at the project root.

Rules:
- Use the `pre-commit` framework (https://pre-commit.com).
- Include hooks based on the confirmed stack from Step 2:

**Always include:**
- `trailing-whitespace`
- `end-of-file-fixer`
- `check-yaml`
- `check-added-large-files`
- `detect-private-key` (security baseline)

**Backend (based on language):**
- Python: `ruff` (linting + formatting), `mypy` (if type checking confirmed)
- Node/TS: defer to frontend hooks
- Other: ask the user for preferred linter

**Frontend (based on framework):**
- React/Vue/Angular with TypeScript: `eslint`, `prettier`
- If a component library has specific lint rules, include them

**Data:**
- If SQL migrations exist: `sqlfluff` or equivalent (optional, ask user)

Also create a brief section in the README (or a `CONTRIBUTING.md` note) explaining:
- How to install: `pip install pre-commit && pre-commit install`
- How to run manually: `pre-commit run --all-files`
- That hooks run automatically on `git commit`

---

### 7. Report results

Display a clear summary:

- Which files were created
- Which templates were used
- The confirmed stack assumptions
- Docker services configured
- Pre-commit hooks configured

---

## Output On Success

## Standards Initialized

Created:
- ai-specs/specs/backend-standards.mdc
- ai-specs/specs/frontend-standards.mdc
- docker-compose.yml
- backend/Dockerfile (or Dockerfile)
- frontend/Dockerfile (if applicable)
- .pre-commit-config.yaml

Templates used:
- ai-specs/specs/templates/backend-standards-template.mdc
- ai-specs/specs/templates/frontend-standards-template.mdc

Stack configuration has been applied to all generated files.

---

## Output On Error (Missing Template)

## Init Standards Failed

Missing template:
- <path>

Add the template file and retry.

---

## Guardrails

- Templates define STRUCTURE ONLY (never copy example content).
- Never invent stack details — always confirm with the user.
- Keep standards concrete and actionable.
- Do not overwrite existing standards without explicit confirmation.
