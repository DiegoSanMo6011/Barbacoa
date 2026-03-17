# PRD — AutoNoma POS Lite

## 1) Resumen
AutoNoma POS Lite es una versión de entrada para micro-negocios (cafeterías/pastelerías) con operación **offline-first**, venta rápida y sincronización en segundo plano con Supabase.

Objetivo principal: cobrar en menos de 15 segundos por ticket en hardware rehabilitado (All-in-One con SSD), sin la complejidad de inventarios y analítica avanzada del POS Full.

## 2) Alcance del MVP (Lite)
- Catálogo de productos sin stock.
- Productos personalizables con modificadores (grupos y opciones con delta de precio).
- Flujo de venta rápida: seleccionar producto, aplicar modificadores, cobrar.
- Métodos de pago: efectivo, tarjeta, transferencia.
- Corte de caja básico (abrir/cerrar jornada y resumen diario).
- Ticket de venta para confirmación y reimpresión.
- Sincronización offline -> online con cola local.

## 3) Fuera de alcance (MVP Lite)
- Inventario, recetas y mermas.
- Analítica avanzada y reportes corporativos.
- Múltiples estaciones simultáneas por tenant.
- Promociones complejas y motor de descuentos.

## 4) Requisitos no funcionales
- Arranque de la PWA en < 3s en equipo rehabilitado.
- Operación offline continua hasta 72h.
- UI táctil, aprendizaje en minutos para cajeros no técnicos.
- Aislamiento multitenant estricto por `tenant_id`.

## 5) Arquitectura propuesta
- `pos-pwa/`: React + TypeScript + Dexie (IndexedDB) + Zustand.
- `pos-edge/`: FastAPI como backend local para simplificar seguridad y contratos.
- `sql/`: migraciones y RPCs en Supabase (PostgreSQL).

Flujo:
1. PWA consulta catálogo al Edge y lo cachea en IndexedDB.
2. Venta se registra localmente de inmediato.
3. Si hay red, se sincroniza al instante; si no, se encola.
4. Sincronizador drena cola cuando regresa conectividad.

## 6) Modelo de datos para productos personalizables
Tablas nuevas/clave:
- `categorias`
- `productos`
- `modificador_grupos`
- `modificador_opciones`
- `producto_modificador_grupos` (M:N)
- `comanda_items.modificadores_snapshot` (JSONB para histórico inmutable)

Relación conceptual:
1. Un producto pertenece a una categoría.
2. Un producto puede tener 0..N grupos de modificadores.
3. Cada grupo tiene 1..N opciones.
4. Cada opción puede sumar/restar al precio base con `precio_delta`.
5. En venta, se guarda snapshot del nombre/opción/delta para preservar histórico aunque cambie el catálogo.

Ejemplo:
- Producto: `Café Latte` (55.00)
- Grupo obligatorio: `Tamaño` -> Chico +0, Mediano +10, Grande +20
- Grupo opcional: `Tipo de leche` -> Entera +0, Avena +10
- Total unitario: `precio_base + suma(deltas seleccionados)`

## 7) Decisión multitenant: 1 DB compartida vs 2 DB separadas
### Alternativas evaluadas
1. Una sola base/proyecto Supabase para Lite + Full.
2. Dos bases/proyectos separados (Lite y Full).

### Decisión
Se adopta **opción 1: una sola base/proyecto Supabase** con `tenant_id` + RLS + `tenants.plan` como feature flag (`LITE`/`FULL`).

### Razones
- Migración Lite -> Full inmediata sin ETL ni downtime.
- Menor costo operativo (backups, observabilidad, migraciones, soporte).
- Menor complejidad de código y menos rutas de fallo.
- Permite desplegar clientes Lite rápido.

### Riesgos y mitigaciones
- Riesgo: crecimiento de carga Full afecte Lite.
  - Mitigar con índices por `tenant_id`, RPCs acotadas y límites por plan.
- Riesgo: fuga de datos entre tenants.
  - Mitigar con RLS + validaciones server-side + triggers de consistencia.

### Cuándo considerar separar en 2 DB
- > 500 tenants activos o p95 de consultas críticas > 300ms sostenido.
- Requisitos regulatorios por segmento.
- Diferencias operativas radicales entre Lite y Full.

## 8) Compatibilidad con migración a POS Full
- Se comparte `tenant_id` y tablas core (`productos`, `comandas`, `cierres_caja`).
- Migrar un cliente es cambiar `tenants.plan` a `FULL`.
- No hay transformación de histórico de ventas.
- Funciones/tables Full-only pueden activarse incrementalmente por tenant.

## 9) Estructura de repositorio (inicial)
```text
pos_lite/
├── docs/
│   ├── PRD_POS_LITE.md
│   └── MIGRATION_GUIDE.md
├── sql/
│   ├── 01_schema_lite.sql
│   ├── 02_rls_policies.sql
│   ├── 03_rpcs.sql
│   └── seed_demo_cafe.sql
├── pos-edge/
│   ├── main.py
│   ├── core/
│   ├── models/
│   └── routers/
├── pos-pwa/
│   ├── src/db/
│   ├── src/store/
│   ├── src/sync/
│   ├── src/components/
│   └── src/views/
└── README.md
```

## 10) Decisiones cerradas para arranque
- Repo: `POS_LITE` en `AutoNomaMX`, privado.
- Multitenant: base única compartida con POS Full.
- Modificadores: esquema grupos + opciones + `precio_delta` (aprobado para cafetería).
- Offline local: Dexie/IndexedDB (más simple que wa-sqlite para MVP).
- Backend local: mantener `pos-edge` (evita exponer service key en cliente y simplifica evolución).
