-- ============================================================
-- BASE DE DATOS INICIAL - POS AUTO NOMA (VERSIÓN AVANZADA)
-- Ejecutar en Supabase SQL Editor para crear todas las tablas
-- en el orden correcto.
-- ============================================================

-- 1. Secuencias
CREATE SEQUENCE IF NOT EXISTS productos_id_seq START WITH 1;
CREATE SEQUENCE IF NOT EXISTS comandas_folio_seq START WITH 1000;
CREATE SEQUENCE IF NOT EXISTS comanda_items_id_seq START WITH 1;

-- 2. Tablas Independientes (Sin Foreign Keys)

CREATE TABLE IF NOT EXISTS public.meseros (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  nombre text NOT NULL,
  activo boolean NOT NULL DEFAULT true,
  created_at timestamp with time zone NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.usuarios (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  nombre text NOT NULL,
  usuario text NOT NULL UNIQUE,
  password_hash text NOT NULL,
  rol text NOT NULL CHECK (rol = ANY (ARRAY['GERENTE', 'DUENIO'])),
  activo boolean NOT NULL DEFAULT true,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  updated_at timestamp with time zone NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS usuarios_role_unique_idx ON public.usuarios (rol);

CREATE TABLE IF NOT EXISTS public.productos (
  id bigint PRIMARY KEY DEFAULT nextval('productos_id_seq'::regclass),
  nombre text NOT NULL,
  precio numeric NOT NULL CHECK (precio >= 0),
  categoria text NOT NULL DEFAULT 'GENERAL',
  activo boolean NOT NULL DEFAULT true,
  venta_por_gramo boolean NOT NULL DEFAULT false,
  orden_catalogo integer NOT NULL DEFAULT 1000,
  created_at timestamp with time zone NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.gastos (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  concepto text NOT NULL,
  categoria text NOT NULL DEFAULT 'GENERAL',
  monto numeric NOT NULL CHECK (monto > 0),
  nota text,
  metodo_pago text NOT NULL DEFAULT 'EFECTIVO' CHECK (metodo_pago = ANY (ARRAY['EFECTIVO', 'TARJETA', 'TRANSFER']))
);

CREATE TABLE IF NOT EXISTS public.cierres_caja (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  fecha date NOT NULL UNIQUE,
  total_ventas numeric NOT NULL,
  total_gastos numeric NOT NULL,
  neto numeric NOT NULL,
  caja_chica_inicial numeric NOT NULL DEFAULT 0,
  efectivo_reportado numeric NOT NULL,
  total_propinas_tarjeta numeric NOT NULL DEFAULT 0,
  propinas_tarjeta_detalle jsonb NOT NULL DEFAULT '[]',
  diferencia_efectivo numeric NOT NULL,
  estado text NOT NULL DEFAULT 'CERRADO' CHECK (estado = ANY (ARRAY['ABIERTO', 'CERRADO'])),
  abierto_at timestamp with time zone NOT NULL DEFAULT now(),
  cerrado_at timestamp with time zone,
  reaperturas integer NOT NULL DEFAULT 0,
  reabierto_at timestamp with time zone,
  notas text
);

CREATE TABLE IF NOT EXISTS public.comandas (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  folio bigint UNIQUE NOT NULL DEFAULT nextval('comandas_folio_seq'::regclass),
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  metodo_pago text NOT NULL CHECK (metodo_pago = ANY (ARRAY['EFECTIVO', 'TARJETA', 'TRANSFER'])),
  total numeric NOT NULL CHECK (total >= 0),
  notas text,
  mesero text,
  mesa text,
  recibido numeric,
  cambio numeric,
  status text NOT NULL DEFAULT 'PAGADA' CHECK (status = ANY (ARRAY['PAGADA', 'CANCELADA', 'CORREGIDA'])),
  cancelada_at timestamp with time zone,
  cancelada_por text,
  cancelacion_motivo text
);

-- 3. Tablas Dependientes (Con Foreign Keys)

CREATE TABLE IF NOT EXISTS public.comanda_items (
  id bigint PRIMARY KEY DEFAULT nextval('comanda_items_id_seq'::regclass),
  comanda_id uuid NOT NULL REFERENCES public.comandas(id) ON DELETE CASCADE,
  producto_id bigint NOT NULL REFERENCES public.productos(id) ON DELETE RESTRICT,
  nombre_snapshot text NOT NULL,
  precio_unitario numeric NOT NULL CHECK (precio_unitario >= 0),
  cantidad integer NOT NULL CHECK (cantidad > 0),
  subtotal numeric NOT NULL CHECK (subtotal >= 0)
);

CREATE TABLE IF NOT EXISTS public.comanda_pagos (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  comanda_id uuid NOT NULL REFERENCES public.comandas(id) ON DELETE CASCADE,
  orden integer NOT NULL DEFAULT 1,
  metodo_pago text NOT NULL CHECK (metodo_pago = ANY (ARRAY['EFECTIVO', 'TARJETA', 'TRANSFER'])),
  monto numeric NOT NULL CHECK (monto >= 0),
  recibido numeric,
  cambio numeric,
  propina numeric NOT NULL DEFAULT 0 CHECK (propina >= 0),
  created_at timestamp with time zone NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS comanda_pagos_comanda_idx ON public.comanda_pagos (comanda_id, orden);

CREATE TABLE IF NOT EXISTS public.comanda_correcciones (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  comanda_id uuid NOT NULL REFERENCES public.comandas(id) ON DELETE CASCADE,
  motivo text NOT NULL,
  before_payload jsonb NOT NULL,
  after_payload jsonb NOT NULL,
  corregido_por text NOT NULL,
  created_at timestamp with time zone NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS comanda_correcciones_comanda_idx ON public.comanda_correcciones (comanda_id, created_at);

CREATE TABLE IF NOT EXISTS public.ticket_historial (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  comanda_id uuid NOT NULL REFERENCES public.comandas(id) ON DELETE CASCADE,
  version integer NOT NULL,
  tipo text NOT NULL CHECK (tipo = ANY (ARRAY['ORIGINAL', 'CORREGIDO'])),
  ticket_text text NOT NULL,
  created_by text,
  created_at timestamp with time zone NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS ticket_historial_comanda_version_uq ON public.ticket_historial (comanda_id, version);
CREATE INDEX IF NOT EXISTS ticket_historial_comanda_created_idx ON public.ticket_historial (comanda_id, created_at DESC);

CREATE TABLE IF NOT EXISTS public.propinas (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  fecha timestamp with time zone NOT NULL DEFAULT now(),
  mesero_id uuid REFERENCES public.meseros(id) ON DELETE SET NULL,
  mesero_nombre_snapshot text,
  monto numeric NOT NULL,
  fuente text NOT NULL DEFAULT 'NO_ESPECIFICADO' CHECK (fuente = ANY (ARRAY['EFECTIVO', 'TARJETA', 'TRANSFER', 'NO_ESPECIFICADO'])),
  comanda_id uuid REFERENCES public.comandas(id) ON DELETE SET NULL,
  created_at timestamp with time zone NOT NULL DEFAULT now()
);

-- ============================================================
-- 4. NUEVAS TABLAS DE INVENTARIO
-- ============================================================

CREATE TABLE IF NOT EXISTS public.insumos (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  nombre       text NOT NULL,
  unidad       text NOT NULL DEFAULT 'pz',   -- pz, kg, lt, g, ml, etc.
  stock_actual numeric NOT NULL DEFAULT 0 CHECK (stock_actual >= 0),
  stock_minimo numeric NOT NULL DEFAULT 0 CHECK (stock_minimo >= 0),
  activo       boolean NOT NULL DEFAULT true,
  created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.recetas (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  producto_id bigint NOT NULL REFERENCES public.productos(id) ON DELETE CASCADE,
  insumo_id   uuid   NOT NULL REFERENCES public.insumos(id)   ON DELETE CASCADE,
  cantidad    numeric NOT NULL CHECK (cantidad > 0),
  UNIQUE (producto_id, insumo_id)
);

CREATE TABLE IF NOT EXISTS public.movimientos_inventario (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  insumo_id      uuid NOT NULL REFERENCES public.insumos(id) ON DELETE CASCADE,
  tipo           text NOT NULL CHECK (tipo IN ('ENTRADA', 'SALIDA')),
  cantidad       numeric NOT NULL CHECK (cantidad > 0),
  motivo         text,          -- 'COMANDA', 'AJUSTE MANUAL', 'COMPRA', etc.
  referencia_id  text,          -- comanda_id u otro identificador externo
  created_at     timestamptz NOT NULL DEFAULT now()
);

-- Índices para el inventario
CREATE INDEX IF NOT EXISTS idx_recetas_producto ON public.recetas(producto_id);
CREATE INDEX IF NOT EXISTS idx_recetas_insumo   ON public.recetas(insumo_id);
CREATE INDEX IF NOT EXISTS idx_movimientos_insumo ON public.movimientos_inventario(insumo_id);
CREATE INDEX IF NOT EXISTS idx_movimientos_fecha  ON public.movimientos_inventario(created_at);
