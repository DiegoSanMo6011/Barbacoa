# R5 Release Runbook (POS Core)

## Scope
- R0-R5 only (POS core).
- Includes hotfix: split payments with `EFECTIVO` row and empty `recibido`.

## Go/No-Go Gate
- `./.venv/bin/python scripts/validate_program.py` is green.
- Manual smoke tests for split payments are green.
- No critical issue open in payment, ticket history, cancellation, correction, reprint, or corte/reportes.

## Release Branch and PR
1. Create release bundle branch:
```bash
git checkout -b feat/R5-T00-pos-core-bundle
```
2. Commit with conventional commits by logical blocks.
3. Open one PR to `main` with:
- PR template completed.
- Validation output attached.
- Manual test evidence attached.
4. Review + squash merge only.

## Production Deployment Window
- Recommended window: close of day, 45-60 minutes.

## Pre-Deployment Checklist
1. Confirm jornada closed and no active command capture.
2. Take production DB backup:
```bash
SUPABASE_DB_URL=... ./scripts/backup_supabase.sh
```
3. Confirm rollback operator has dump path ready.

## Database Migration (Production)
- Execute:
```sql
-- sql/comandas_pagos_auditoria.sql
```

## App Update (Production Machine)
1. Pull merged release/tag.
2. Install dependencies (if required).
3. Restart POS service.

## Smoke Tests (20-30 min)
1. Save split payment: 2 methods, one `EFECTIVO` with empty `recibido`.
2. Save split payment: `EFECTIVO` with `recibido < monto` should block.
3. Tip distribution by payment method reflects in reports.
4. Cancel order with reason and verify report exclusion.
5. Correct ticket with reason and verify audit trail.
6. Reprint original and latest corrected ticket.
7. Verify corte and ventas por método.

## Rollback Plan
1. Restore DB:
```bash
SUPABASE_DB_URL=... ./scripts/restore_supabase.sh backups/db/supabase_YYYYMMDD_HHMMSS.dump
```
2. Checkout previous stable app version/tag.
3. Restart POS service.
4. Re-run minimum smoke tests.

## Communication Plan
- Pilot day: next business day after deploy.
- General customer update: after pilot passes without critical incidents.
