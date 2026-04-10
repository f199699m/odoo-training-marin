# Personal Context — Carlos Fernando Marin Guadarrama (CFMG)

## Odoo Identity

Carlos Fernando Marin Guadarrama

- ODOO_USER_ID: 1041
- ODOO_LOGIN: carlos.marin@agromarin.mx
- ODOO_DEFAULT_TASK_PROJECT_ID: 36

## Role Profile

- **Role**: Gerente Logistico (`role_logistics_manager`)
- **Department**: Logistics and Supply Chain
- **Tier**: manager
- **Profile**: functional

## Active Project

$PROJECT = agromarin
$DB = marin190
$DEPARTMENT = operaciones
$ACTIVE_REPOS = addons, enterprise, core
$WORKSPACE = knowledge/agromarin-knowledge/workspaces/workspace-CFMG

## Project Details

| Item | Value |
|------|-------|
| Addons | `addons/agromarin-addons/` |
| Knowledge | `knowledge/agromarin-knowledge/` |
| Workspace | `knowledge/agromarin-knowledge/workspaces/workspace-CFMG/` |
| Conf | `conf/agromarin.conf` |

## GitHub Workflow

All commit and PR content MUST be in English.

### Commits

- Commit messages MUST be in English.
- NEVER add "Co-Authored-By" to commit messages. This is a company policy.
- Structure:

```
[TAG] module: short summary of the change

Detailed description of the problem or context that motivated the change.
Explain what was happening before and why it was incorrect or insufficient.

Description of the implemented solution:
- Point 1
- Point 2
- Point N

Task ID: XXXXX
```

- Valid tags: [FIX], [IMP], [ADD], [REM], [REF], [MOV], [MERGE], [CLA], [I18N]
- The subject line (first line) must be concise and descriptive.
- The body must explain the problem, the solution, and list affected files/areas if applicable.
- Include "Task ID: XXXXX" at the end when a task ID is provided.
- Use list format (- or numbered) to detail multiple changes.

### Pull Requests

- Structure:

```
# [Task ID: XXXXX](https://agromarin.mx/odoo/project.task/XXXXX)

Brief one-line summary of the PR objective.

---

## Problem

Clear description of the problem being solved. What was wrong,
inconsistent, or missing.

---

## Solution

### modified_file_or_area
- Change 1
- Change 2

### another_file_or_area
- Change 1

---

## Verification

- [ ] Verification step 1
- [ ] Verification step 2
```

- PR title must be short (< 70 characters).
- "Task ID: XXXXX" MUST be a hyperlink to the Odoo task.
- Problem section explains the "why".
- Solution section explains the "what and how".
- Verification section lists steps to validate the change.

## Environment Overrides

### Shell Override
- **Shell**: bash (`~/.bashrc`), not zsh

## Environment Gotchas

### Database flag
- Always use `-d marin190` explicitly when starting Odoo

## Personal Preferences

### Communication
- Default language: Spanish for conversation, English for code/commits/PRs
- Use business terms and Odoo menu paths, not technical jargon
- When explaining code concepts, relate them to logistics/warehouse operations

### Learning Context
- Currently learning Python fundamentals through Odoo-contextualized exercises
- Explain programming concepts with supply chain analogies when possible
- Be patient with technical concepts — build from what I already know about Odoo

### Work Style
- Prefer step-by-step guidance over long explanations
- Show me the Odoo UI path first, code only when strictly necessary
- When I ask about inventory, purchasing, or delivery — assume I mean Odoo operations
