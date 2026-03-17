# Guía de Migración: AutoNoma POS Lite → POS Full

Este documento describe todos los pasos para migrar un cliente de **POS Lite** al **POS completo de AutoNoma**, sin pérdida de datos.

---

## Por qué la migración es simple

Ambas versiones comparten el **mismo Supabase Project** y el mismo esquema base de datos.
El POS Lite es un subconjunto del POS Full, no un producto separado.

---

## Pasos de migración

### 1. Cambiar el plan del tenant

```sql
UPDATE public.tenants
SET
  plan = 'FULL',
  plan_activado_at = now()
WHERE id = 'UUID-DEL-TENANT';
```

### 2. Crear registros faltantes en tablas Full-only

```sql
-- Meseros: insertar al menos uno para no bloquear comandas
INSERT INTO public.meseros (tenant_id, nombre, activo)
VALUES ('UUID-DEL-TENANT', 'Encargado', true);

-- El resto de tablas (inventario, propinas, etc.) son opcionales
-- y se pueden poblar gradualmente
```

### 3. Reemplazar el Edge Lite con el Edge Full

```bash
# En el servidor local del cliente:
cd autonoma-edge   # El repo POS_AUTONOMA
cp .env.example .env
# Copiar las mismas credenciales que usaba el .env de pos-edge
uvicorn main:app --reload --port 8000
```

### 4. Reemplazar la PWA Lite con la PWA Full

```bash
# En el servidor local del cliente:
cd autonoma-pwa
npm install
npm run dev
```

### 5. Verificar compatibilidad de datos

```sql
-- Verificar que los productos migran correctamente
SELECT COUNT(*) FROM public.productos WHERE tenant_id = 'UUID-DEL-TENANT';

-- Verificar histórico de ventas (sigue accesible)
SELECT COUNT(*) FROM public.comandas WHERE tenant_id = 'UUID-DEL-TENANT';

-- Verificar cierres de caja
SELECT COUNT(*) FROM public.cierres_caja WHERE tenant_id = 'UUID-DEL-TENANT';
```

---

## Mapa de compatibilidad de datos

| Tabla | POS Lite | POS Full | Notas |
|-------|----------|----------|-------|
| `tenants` | ✅ | ✅ | Solo cambiar `plan` |
| `categorias` | ✅ | ✅ | 100% compatible |
| `productos` | ✅ | ✅ | 100% compatible |
| `modificador_grupos` | ✅ | ✅ | 100% compatible |
| `modificador_opciones` | ✅ | ✅ | 100% compatible |
| `comandas` | ✅ | ✅ | Historial preservado íntegro |
| `comanda_items` | ✅ (+ snapshot) | ✅ | Snapshot JSONB ignorado por Full pero no rompe |
| `cierres_caja` | ✅ | ✅ | 100% compatible |
| `meseros` | ❌ no usada | ✅ | Crear registros al migrar |
| `propinas` | ❌ no usada | ✅ | Vacía, se puebla al usar Full |
| `gastos_operativos` | ❌ no usada | ✅ | Vacía, se puebla al usar Full |
| `inventario_items` | ❌ no usada | ✅ | Vacía, setup por demanda |

---

## Rollback (si se necesita)

Para volver temporalmente al POS Lite:

```sql
UPDATE public.tenants SET plan = 'LITE' WHERE id = 'UUID-DEL-TENANT';
```

Y regresar al Edge Lite. **Los datos NO se pierden en ninguna dirección.**
