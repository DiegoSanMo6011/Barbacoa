## Summary
- What changed and why

## Task Mapping
- Release: `R?`
- Task ID: `R?-T??`
- Branch: `feat/R?-T??-...` or `fix/R?-H??-...`

## Checklist (Required)
- [ ] Scope matches task ID and acceptance criteria
- [ ] No unrelated files included
- [ ] SQL migration is idempotent (if applicable)
- [ ] Backward compatibility considered
- [ ] Errors and edge cases handled
- [ ] Logs added for operational visibility

## Testing Evidence
- [ ] `./.venv/bin/python scripts/validate_program.py`
- [ ] Manual tests attached (screenshots/videos if UI)
- [ ] Regression checks executed for affected modules

## Data / Security Impact
- [ ] New columns/tables indexed as needed
- [ ] Audit trail added where business-critical
- [ ] Permissions reviewed (role-based)

## Deploy Notes
- [ ] Migration order documented
- [ ] Rollback path documented
- [ ] Staging verification completed
- [ ] Pilot verification completed
