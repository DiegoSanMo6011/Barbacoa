-- ============================================================
-- MÓDULO DE INVENTARIO — POS AutoNoma
-- Ejecutar en Supabase SQL Editor antes de usar el módulo.
-- ============================================================

-- 1. Insumos: ingredientes / materiales del negocio
CREATE TABLE IF NOT EXISTS public.insumos (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  nombre       text NOT NULL,
  unidad       text NOT NULL DEFAULT 'pz',   -- pz, kg, lt, g, ml, etc.
  stock_actual numeric NOT NULL DEFAULT 0 CHECK (stock_actual >= 0),
  stock_minimo numeric NOT NULL DEFAULT 0 CHECK (stock_minimo >= 0),
  activo       boolean NOT NULL DEFAULT true,
  created_at   timestamptz NOT NULL DEFAULT now()
);

-- 2. Recetas: cuánto consume cada producto de cada insumo al venderse
CREATE TABLE IF NOT EXISTS public.recetas (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  producto_id bigint NOT NULL REFERENCES public.productos(id) ON DELETE CASCADE,
  insumo_id   uuid   NOT NULL REFERENCES public.insumos(id)   ON DELETE CASCADE,
  cantidad    numeric NOT NULL CHECK (cantidad > 0),
  UNIQUE (producto_id, insumo_id)
);

-- 3. Historial de movimientos de inventario
CREATE TABLE IF NOT EXISTS public.movimientos_inventario (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  insumo_id      uuid NOT NULL REFERENCES public.insumos(id) ON DELETE CASCADE,
  tipo           text NOT NULL CHECK (tipo IN ('ENTRADA', 'SALIDA')),
  cantidad       numeric NOT NULL CHECK (cantidad > 0),
  motivo         text,          -- 'COMANDA', 'AJUSTE MANUAL', 'COMPRA', etc.
  referencia_id  text,          -- comanda_id u otro identificador externo
  created_at     timestamptz NOT NULL DEFAULT now()
);

-- Índices para consultas frecuentes
CREATE INDEX IF NOT EXISTS idx_recetas_producto ON public.recetas(producto_id);
CREATE INDEX IF NOT EXISTS idx_recetas_insumo   ON public.recetas(insumo_id);
CREATE INDEX IF NOT EXISTS idx_movimientos_insumo ON public.movimientos_inventario(insumo_id);
CREATE INDEX IF NOT EXISTS idx_movimientos_fecha  ON public.movimientos_inventario(created_at);
