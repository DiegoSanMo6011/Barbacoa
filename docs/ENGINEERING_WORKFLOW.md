# Engineering Workflow

## Branch Strategy
- One branch per task.
- Naming:
  - `feat/R{release}-T{order}-{slug}`
  - `fix/R{release}-H{order}-{slug}`

## Commit Style
- Conventional commits only:
  - `feat:`
  - `fix:`
  - `refactor:`
  - `test:`
  - `docs:`

## Pull Request Rules
- One PR per task.
- Squash merge.
- Mandatory checklist completion from PR template.
- No merge without review.

## Release Rules
- Weekly cadence.
- Promotion flow:
  1. Staging
  2. Pilot
  3. Production
- Tag format: `vMAJOR.MINOR.PATCH`

## Quality Gates
- Run `./.venv/bin/python scripts/validate_program.py` before PR.
- Include manual test evidence for UI changes.
- Idempotent SQL migration for schema updates.

## Rollback
- Always create DB backup before migrations.
- Keep rollback SQL or restore script ready.
