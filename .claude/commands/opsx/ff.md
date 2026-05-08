---
name: "OPSX: Fast Forward"
description: Create a change and generate all artifacts needed for implementation in one go
category: Workflow
tags: [workflow, artifacts, experimental]
---

Fast-forward through artifact creation - generate everything needed to start implementation.
This command orchestrates `/opsx:continue` in a loop until the change is apply-ready.

**Input**: The argument after `/opsx:ff` is the change name (kebab-case), OR a description of what the user wants to build.

---

## Steps

### 1. Get or create the change

**If no input provided**, use the **AskUserQuestion tool** (open-ended) to ask:
> "What change do you want to work on? Describe what you want to build or fix."

From their description, derive a kebab-case name.

**IMPORTANT**: Do NOT proceed without understanding what the user wants to build.

### 2. Create the change directory (if new)

```bash
openspec new change "<name>"
```

This creates a scaffolded change at `openspec/changes/<name>/`.

If a change with that name already exists, ask if user wants to continue it or create a new one.

### 3. Check initial status

```bash
openspec status --change "<name>" --json
```

Parse the JSON to get `artifacts` and `applyRequires`. Use **TodoWrite** to track all artifacts.

### 4. Loop: create artifacts using `/opsx:continue` logic

Repeat until all `applyRequires` artifacts have `status: "done"`:

1. Follow the **exact same logic** as `/opsx:continue` steps 2–6 to create the next ready artifact:
   - Check status → pick first `ready` artifact → get instructions → read dependencies → extract metadata → create artifact → show progress
2. After each artifact, re-check status:
   ```bash
   openspec status --change "<name>" --json
   ```
3. If an artifact requires user input, ask and continue.
4. If `isComplete` or all `applyRequires` are done, stop.

**Key**: Each iteration follows `/opsx:continue`'s artifact creation guidelines exactly (scope/design metadata extraction, task tagging, template usage, guardrails). Refer to `/opsx:continue` as the canonical reference for how to create each artifact.

### 5. Show final status

```bash
openspec status --change "<name>"
```

Summarize:
- Change name and location
- List of artifacts created with brief descriptions
- "All artifacts created! Ready for implementation."
- Prompt: "Run `/opsx:apply` to start implementing."

---

## Guardrails

- Create ALL artifacts needed for implementation (as defined by schema's `apply.requires`)
- Follow `/opsx:continue`'s artifact creation guidelines for EVERY artifact (metadata extraction, scope rules, design references, task tagging)
- Always read dependency artifacts before creating a new one
- If context is critically unclear, ask the user — but prefer reasonable decisions to keep momentum
- Verify each artifact file exists after writing before proceeding to next
