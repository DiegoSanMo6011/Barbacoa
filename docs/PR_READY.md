# PR Ready — AutoNoma POS Lite

## Branch sugerida
`feat/pos-lite-bootstrap-hardening`

## Commits sugeridos
1. `docs: add POS Lite PRD and migration links`
2. `fix(pwa): harden offline sync and connectivity status`
3. `feat(sql): reinforce multitenant integrity and rpc guards`
4. `chore(devx): add bootstrap and dev scripts`

## Comandos sugeridos
```bash
git checkout -b feat/pos-lite-bootstrap-hardening
git add docs/PRD_POS_LITE.md docs/PR_READY.md README.md
git commit -m "docs: add POS Lite PRD and migration links"

git add pos-pwa/package.json pos-pwa/src/components/CobrarModal.tsx pos-pwa/src/components/Nav.tsx pos-pwa/src/db/localDB.ts pos-pwa/src/sync/catalogoSync.ts pos-pwa/src/sync/syncQueue.ts
git commit -m "fix(pwa): harden offline sync and connectivity status"

git add pos-edge/routers/comandas.py sql/01_schema_lite.sql sql/02_rls_policies.sql sql/03_rpcs.sql sql/seed_demo_cafe.sql
git commit -m "feat(sql): reinforce multitenant integrity and rpc guards"

git add scripts/bootstrap.sh scripts/dev.sh
git commit -m "chore(devx): add bootstrap and dev scripts"
```

## PR title sugerido
`POS Lite MVP: PRD + offline sync fixes + SQL multitenant hardening + bootstrap scripts`

## PR body sugerido
```md
## Resumen
- Se agrega PRD formal de POS Lite con decisión multitenant (1 DB compartida con Full).
- Se corrigen fallos en sincronización offline de PWA.
- Se endurece la capa SQL (RLS, integridad tenant, validaciones de RPC).
- Se agregan scripts para bootstrap local y ejecución de servicios.

## Cambios principales
- Docs:
  - `docs/PRD_POS_LITE.md`
  - `docs/PR_READY.md`
  - `README.md` enlaces a documentación
- PWA:
  - Sync catálogo sobre DB real de Dexie y cache atómica
  - Cola offline correlaciona venta local al sincronizar
  - Estado online/offline reactivo
  - Dependencia `nanoid` añadida
- Edge:
  - Filtro de ventas del día corregido en `listar_ventas`
- SQL:
  - FK tenant en `producto_modificador_grupos`
  - constraints/triggers de consistencia de tenant
  - políticas RLS `FOR ALL`
  - RPCs con validación de tenant, método de pago y total
  - lock transaccional para folio concurrente
  - seed demo corregido
- DevX:
  - `scripts/bootstrap.sh`
  - `scripts/dev.sh`

## Riesgos / notas
- Requiere ejecutar migraciones SQL actualizadas.
- `npm install` para tomar `nanoid`.

## Validación ejecutada
- `python3 -m compileall pos-edge` ✅
- Build de PWA pendiente de dependencias en entorno actual (`tsc` no disponible en PATH sin `npm install` local completo).
```
