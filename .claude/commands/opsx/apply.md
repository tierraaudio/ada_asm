---
name: "OPSX: Apply"
description: Implement tasks from an OpenSpec change (Experimental). Uses scope metadata for FE/BE. If scope.frontend and design-linked are true, fetch design structure live from Figma MCP before implementing frontend tasks.
category: Workflow
tags: [workflow, artifacts, experimental, figma, mcp]
---

Implement tasks from an OpenSpec change.

**Input**: Optionally specify a change name (e.g., `/opsx:apply add-auth`). If omitted, check if it can be inferred from conversation context. If vague or ambiguous you MUST prompt for available changes.

---

## Steps

### 1. Select the change

If a name is provided, use it. Otherwise:
- Infer from conversation context if the user mentioned a change
- Auto-select if only one active change exists
- If ambiguous, run `openspec list --json` to get available changes and use the **AskUserQuestion tool** to let the user select

Always announce: "Using change: <name>" and how to override (e.g., `/opsx:apply <other>`).

---

### 2. Check status to understand the schema

```bash
openspec status --change "<name>" --json
```

Parse the JSON to understand:
- `schemaName`: The workflow being used (e.g., "spec-driven")
- Which artifact contains the tasks (typically "tasks" for spec-driven, check status for others)

---

### 3. Get apply instructions

```bash
openspec instructions apply --change "<name>" --json
```

This returns:
- Context file paths (varies by schema)
- Progress (total, complete, remaining)
- Task list with status
- Dynamic instruction based on current state

Handle states:
- If `state: "blocked"` (missing artifacts): show message, suggest using `/opsx:continue`
- If `state: "all_done"`: congratulate, suggest archive
- Otherwise: proceed to implementation

---

### 4. Read context files

Read the files listed in `contextFiles` from the apply instructions output.

---

### 4.0 Enriched Section Extraction (ENTERPRISE HARDENING)


#### 4.0 Enriched Section Extraction (ENTERPRISE HARDENING)

Before detecting scope/design and design references, attempt to extract ONLY the enriched section.
If the loaded context contains:

<!-- BEGIN_ENRICHED_USER_STORY -->
...
<!-- END_ENRICHED_USER_STORY -->

Then:
- Restrict ALL parsing to the text inside those markers.
- Ignore any "Base User Story" content outside the markers.

If markers are missing:
- Fall back to scanning the full context (best-effort).


---

### 4.1 Detect scope and design metadata

Scan the loaded context files for:

- `design-linked: true|false`
- A `scope:` block containing:
  - `backend: true|false`
  - `frontend: true|false`

Initialize (defaults):

- `scope.backend = false`
- `scope.frontend = false`
- `designLinked = false`
- `liveDesignEnabled = false`


#### 4.1.1 Metadata Tolerance (MANDATORY)

Apply MUST be resilient to non-strict upstream formatting.
Perform strict parsing first. If strict parsing fails to yield values, apply tolerant parsing:

Tolerant patterns to detect:
1) Inline metadata line:
   - `design-linked: true | source: Notion | scope: FE + BE`
   Parse:
   - designLinked from `design-linked:`
   - scope.frontend=true if `scope:` contains `FE` or `frontend`
   - scope.backend=true if `scope:` contains `BE` or `backend`

2) Scope phrases anywhere:
   - `scope: FE + BE`, `scope: BE`, `scope: FE`, `scope: frontend`, `scope: backend`

Precedence:
- If strict metadata exists, it ALWAYS wins.
- If strict metadata missing, tolerant parsing may populate values.

Rules:
- If `scope.frontend == true` and `design-linked == true`:
  - `liveDesignEnabled = true`
- Otherwise:
  - `liveDesignEnabled = false`

---

### 4.2 Detect design references (Live Design Mode only)

Only if `liveDesignEnabled == true`:

Extract design references from the context:
- Prefer a `## Design References` section.
- Parse:
  - `Figma File:` URL (optional if node URLs exist)
  - `Referenced Nodes:` list of node URLs containing `node-id=...`

Rules:
- If Live Design Mode is enabled but no node-id URLs are found:
  - Pause and ask the user to provide at least one Figma node URL with `node-id`.
  - Do NOT implement frontend tasks until a node-id is available.
- Do not assume design structure from prose alone.


#### 4.2.1 Design Reference Tolerance (MANDATORY)

If `## Design References` or `Referenced Nodes:` is missing OR yields zero node-id URLs,
attempt safe reconstruction without inventing anything.

Valid inputs for reconstruction:
- Any base Figma design URL in context: `https://www.figma.com/design/<FILEKEY>/...`
- Any node tokens found in text:
  - `node-id=1:549`, `node-id=1-549`, `(1:549)`, `(1-549)`, `main (1:549): ...`

Reconstruction steps:
1) Identify base Figma design URL:
   - Use the first `https://www.figma.com/design/<FILEKEY>/...` found.
2) Extract node tokens:
   - Accept both `1:549` and `1-549`, normalize `-` -> `:`
3) Build node URLs:
   - URL-encode `:` as `%3A` in query values
   - `<base-url>?node-id=<ENCODED>`

You MUST NOT guess:
- FILEKEY
- node tokens
- missing nodes

---

### 4.3 Fetch design snapshot via Figma MCP (Live Design Mode only)

Only if `liveDesignEnabled == true` and Figma MCP is authenticated:

For each referenced node:
- Inspect the node via Figma MCP.
- Retrieve **both structure AND visual properties**:
  - Node name and type
  - Auto-layout direction (vertical/horizontal/none)
  - Item spacing and padding (if available)
  - Direct children in visual order
  - Component instances and variant info (if resolvable)
  - **Fill colors** (background, foreground — hex + opacity)
  - **Stroke/border colors** (hex + opacity + width)
  - **Border radii** (per-corner if different)
  - **Typography** (font family, font size, font weight, line-height, letter-spacing)
  - **Text colors** (hex + opacity)
  - **Drop shadows and inner shadows** (color, offset, blur, spread)
  - **Opacity** (node-level)
  - **Effects** (blur, layer blend modes if non-default)

Build a **Design Snapshot** in-memory (do not write back to Figma/Notion by default):

## Design Snapshot (from Figma MCP)
Figma File: <...>

Node: <...> (node-id=...)
- Auto Layout: <...>
- Spacing/Padding: <...>
- Colors:
  - Background: <hex> <opacity>
  - Text: <hex> <opacity>
  - Border/Stroke: <hex> <opacity> <width>
- Typography:
  - Font: <family> <weight> <size>/<line-height>
  - Letter Spacing: <value>
- Border Radius: <value or per-corner>
- Shadows: <type> <color> <offset> <blur> <spread>
- Opacity: <value>
- Children (visual order):
  - <child 1> (repeat color/typo/radius for each child with distinct styles)
  - <child 2>
  - <child 3>
- Components/Variants:
  - <...>

If Figma MCP is not authenticated:
- Keep `liveDesignEnabled == true`.
- Warn that frontend fidelity may be lower.
- Ask the user whether to proceed (AI-designed UI) or authenticate Figma via `/mcp`.

#### 4.3.1 UI Framework Compatibility Gate (MANDATORY)

Define the target UI framework for this change as `uiFramework`.

Sources of truth (in order):
1) Change config / workflow input (if provided)
2) Project standards / frontend standards docs (if present)
3) Existing frontend code patterns (imports + dependencies)
4) If still ambiguous: ask the user to choose one (`tailwind`, `bootstrap`, `mui`, `custom-css`)

Rules:
- Figma MCP often returns React + Tailwind code. Treat it as a *visual reference* by default.
- You MAY directly reuse MCP Tailwind classes ONLY if `uiFramework == "tailwind"` AND the repo already uses Tailwind.
- Otherwise, you MUST convert MCP output to match `uiFramework` and the project conventions:
  - Keep structure and UI states (active/inactive/hover), spacing, typography, colors, radii
  - Do NOT introduce new UI frameworks or install dependencies unless the user explicitly requests it
  - Avoid absolute-positioned “pixel perfect” recreation unless the existing codebase already uses that approach

#### 4.3.2 Repo Search Scope Limits (MANDATORY)

When detecting `uiFramework` and styling conventions, restrict reads/searches to the minimal frontend scope:
- frontend/package.json, frontend/src/**, frontend/public/**, frontend/tsconfig.json
- and only the current change folder under openspec/changes/<name>/** when needed

Do NOT scan templates or unrelated directories (e.g., ai-specs/specs/templates/**, .claude/**, historical archives) unless explicitly required by the current task.

---

### 5. Show current progress

Display:
- Schema being used
- Progress: "N/M tasks complete"
- Remaining tasks overview
- Dynamic instruction from CLI
- Scope summary: `backend=<true|false>, frontend=<true|false>`
- Design summary: `design-linked=<true|false>, Live Design Mode=<ON|OFF>`

If Live Design Mode is ON, list the referenced node-ids.

---

### 6. Implement tasks (loop until done or blocked)

For each pending task:
- Show which task is being worked on
- Make the code changes required
- Keep changes minimal and focused
- Mark task complete in the tasks file: `- [ ]` → `- [x]`

#### 6.1 Determine whether the current task is frontend-related

A task is frontend-related if it mentions any of:
- frontend, ui, react, component, page, view, layout, modal, table, css, styles, responsive, accessibility
or references typical UI paths/extensions:
- src/, components/, pages/, .tsx, .jsx, .css, .scss

If uncertain, treat it as frontend-related only when the change touches frontend files.

---

#### 6.2 Frontend task behavior

If `scope.frontend == true` AND the task is frontend-related:

- If `design-linked == true`:
  - Use the Design Snapshot as the primary source of truth.
  - Do not approximate layout from prose if it conflicts with the snapshot.
  - Mirror the Figma hierarchy when composing components (avoid flattening).
  - **Apply design tokens from the snapshot**: colors, typography, border radii, shadows, and opacity MUST be reflected in the implementation (CSS variables, theme tokens, or inline styles — matching `uiFramework` conventions).
  - Do NOT use generic/placeholder colors (e.g., `#f8f9fa`, Bootstrap defaults) when the snapshot provides specific values.
- If `design-linked == false`:
  - Implement an AI-designed UI guided by frontend standards.
  - Keep it minimal, consistent, and accessible.
  - Document any key UI assumptions briefly (in code comments or a short note in the task context).

If `scope.frontend == false`:
- Do NOT implement frontend UI changes as part of this change.
- If a task appears frontend-related but scope.frontend is false, pause and ask whether to update scope/artifacts.

---

#### 6.3 Backend task behavior

If `scope.backend == true` AND the task is backend-related:
- Implement backend changes normally following backend standards.

If `scope.backend == false`:
- Do NOT implement backend changes as part of this change.
- If a task appears backend-related but scope.backend is false, pause and ask whether to update scope/artifacts.

---

Pause if:
- Task is unclear → ask for clarification
- Implementation reveals a design issue → suggest updating artifacts
- Error or blocker encountered → report and wait for guidance
- User interrupts

---

### 7. On completion or pause, show status

Display:
- Tasks completed this session
- Overall progress: "N/M tasks complete"
- If all done: suggest archive
- If paused: explain why and wait for guidance

---

## Output During Implementation

```
## Implementing: <change-name> (schema: <schema-name>)

Scope: backend=<true|false>, frontend=<true|false>
Design: design-linked=<true|false>, Live Design Mode=<ON|OFF>

Working on task 3/7: <task description>
[...implementation happening...]
✓ Task complete
```

## Output On Completion

```
## Implementation Complete

**Change:** <change-name>
**Schema:** <schema-name>
**Progress:** 7/7 tasks complete ✓

### Completed This Session
- [x] Task 1
- [x] Task 2
...

All tasks complete! You can archive this change with `/opsx:archive`.
```

## Output On Pause (Issue Encountered)

```
## Implementation Paused

**Change:** <change-name>
**Schema:** <schema-name>
**Progress:** 4/7 tasks complete

### Issue Encountered
<description of the issue>

**Options:**
1. <option 1>
2. <option 2>
3. Other approach

What would you like to do?
```

---

### 8. Post-apply integration validation (Smoke Test)

After all tasks are marked complete, run an automated smoke test if Docker infrastructure exists.

#### 8.1 Check for Docker infrastructure

Look for `docker-compose.yml` (or `docker-compose.yaml`, `compose.yml`) at the project root.

- If found: proceed to 8.2.
- If not found: skip this step, warn that no Docker infrastructure exists for integration validation, and suggest running `/ai-specs:init-greenfield` to generate it.

#### 8.2 Build and start the stack

```bash
docker compose up -d --build
```

Wait for all services to be healthy (check `docker compose ps`).

- If any service fails to start: report the error, show logs (`docker compose logs <service>`), and pause.
- Timeout: 120 seconds max. If not healthy by then, report and pause.

#### 8.3 Run smoke checks

Perform the following validation checks:

**Backend:**
- Hit the health/root endpoint (e.g., `GET /` or `GET /health` or `GET /api/v1/`) — expect 2xx.
- Hit one representative endpoint from the change (e.g., `GET /api/v1/<resource>/`) — expect 2xx (even if empty list).
- Verify CORS: send an `OPTIONS` request with `Origin: http://localhost:<frontend-port>` — expect `Access-Control-Allow-Origin` header.

**Frontend:**
- Hit the frontend URL (e.g., `GET http://localhost:<frontend-port>/`) — expect 2xx with HTML content.
- Check that the page doesn't show a blank/error screen (look for `<div id="root">` or equivalent in response).

**Integration:**
- From the frontend container/URL, verify the API URL resolves correctly (no double-prefix like `/api/v1/api/v1/`).

#### 8.4 Run E2E tests (if available)

If Cypress, Playwright, or other E2E test configs exist:
- Attempt to run them against the live stack.
- Report pass/fail results.
- If E2E tests fail: show the failure details but do NOT block the apply — report as warnings.

#### 8.5 Tear down

```bash
docker compose down
```

Clean up after validation. Do NOT leave containers running.

#### 8.6 Report results

Display a summary:

```
## Integration Validation

- Backend health: ✓/✗
- Backend API endpoint: ✓/✗
- CORS: ✓/✗
- Frontend serves: ✓/✗
- API URL routing: ✓/✗ (no double-prefix)
- E2E tests: ✓/✗/skipped

Issues found: <list or "none">
```

If any check fails:
- Show the specific error and suggested fix.
- Ask the user whether to fix now or proceed to archive anyway.

---

## Guardrails

- Keep going through tasks until done or blocked
- Always read context files before starting
- If task is ambiguous, pause and ask before implementing
- Keep code changes minimal and scoped
- Update task checkbox immediately after completing each task
- Pause on errors, blockers, or unclear requirements

Design guardrails:
- Live Design Mode is enabled ONLY when `scope.frontend == true` AND `design-linked == true`.
- If Live Design Mode is ON, do not implement frontend UI tasks without at least one node-id URL.
- Prefer the Design Snapshot over prose when implementing UI.
- **Design tokens (colors, typography, radii, shadows) from the snapshot are MANDATORY** — never fall back to framework defaults or generic palettes when the snapshot provides specific values.
- Never modify Figma.
- Do not write snapshot back to Notion unless explicitly requested.

---

## Fluid Workflow Integration

This skill supports the "actions on a change" model:

- Can be invoked anytime
- Allows artifact updates if implementation reveals design issues
- Not phase-locked
