-- ============================================================
-- AutoNoma POS Lite — Migración 01: Schema Base
-- Ejecutar en Supabase SQL Editor (mismo project que POS Full)
-- ============================================================

-- ----------------------------------------
-- 1. Extensión del campo plan en tenants
-- ----------------------------------------
ALTER TABLE public.tenants
  ADD COLUMN IF NOT EXISTS plan text DEFAULT 'LITE'
    CHECK (plan IN ('LITE', 'FULL')),
  ADD COLUMN IF NOT EXISTS plan_activado_at timestamptz,
  ADD COLUMN IF NOT EXISTS nombre_negocio text,
  ADD COLUMN IF NOT EXISTS ciudad text,
  ADD COLUMN IF NOT EXISTS pais text DEFAULT 'MX';

-- ----------------------------------------
-- 2. Categorías de producto
-- ----------------------------------------
CREATE TABLE IF NOT EXISTS public.categorias (
  id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  tenant_id   uuid NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
  nombre      text NOT NULL,
  orden       int  NOT NULL DEFAULT 100,
  activo      bool NOT NULL DEFAULT true,
  created_at  timestamptz DEFAULT now(),
  UNIQUE (tenant_id, nombre)
);

-- ----------------------------------------
-- 3. Productos (sin stock)
-- ----------------------------------------
CREATE TABLE IF NOT EXISTS public.productos (
  id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  tenant_id       uuid NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
  categoria_id    bigint REFERENCES public.categorias(id) ON DELETE SET NULL,
  nombre          text NOT NULL,
  precio          numeric(10,2) NOT NULL DEFAULT 0 CHECK (precio >= 0),
  precio_base     numeric(10,2) NOT NULL DEFAULT 0 CHECK (precio_base >= 0),
  precio_abierto  bool NOT NULL DEFAULT false,
  personalizacion_tipo text NOT NULL DEFAULT 'NINGUNA'
    CHECK (personalizacion_tipo IN ('NINGUNA', 'TACO', 'TORTA')),
  descripcion     text,
  activo          bool NOT NULL DEFAULT true,
  orden_catalogo  int  NOT NULL DEFAULT 1000,
  created_at      timestamptz DEFAULT now(),
  updated_at      timestamptz DEFAULT now()
);

-- Compatibilidad con tablas existentes del POS Full:
-- si productos ya existía, asegurar columnas necesarias de Lite.
ALTER TABLE public.productos
  ADD COLUMN IF NOT EXISTS categoria_id bigint,
  ADD COLUMN IF NOT EXISTS precio numeric(10,2),
  ADD COLUMN IF NOT EXISTS precio_base numeric(10,2) NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS precio_abierto bool NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS personalizacion_tipo text NOT NULL DEFAULT 'NINGUNA',
  ADD COLUMN IF NOT EXISTS descripcion text,
  ADD COLUMN IF NOT EXISTS activo bool NOT NULL DEFAULT true,
  ADD COLUMN IF NOT EXISTS orden_catalogo int NOT NULL DEFAULT 1000,
  ADD COLUMN IF NOT EXISTS created_at timestamptz DEFAULT now(),
  ADD COLUMN IF NOT EXISTS updated_at timestamptz DEFAULT now();

-- Normalizar datos legacy del POS Full para que Lite pueda escribir sin romper.
UPDATE public.productos
SET
  precio = COALESCE(precio, precio_base, 0),
  precio_base = COALESCE(precio_base, precio, 0),
  precio_abierto = COALESCE(precio_abierto, false),
  personalizacion_tipo = COALESCE(personalizacion_tipo, 'NINGUNA')
WHERE
  precio IS NULL
  OR precio_base IS NULL
  OR precio_abierto IS NULL
  OR personalizacion_tipo IS NULL;

ALTER TABLE public.productos
  ALTER COLUMN precio SET DEFAULT 0,
  ALTER COLUMN precio_base SET DEFAULT 0;

ALTER TABLE public.productos
  ALTER COLUMN precio SET NOT NULL,
  ALTER COLUMN precio_base SET NOT NULL,
  ALTER COLUMN precio_abierto SET NOT NULL,
  ALTER COLUMN personalizacion_tipo SET NOT NULL;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'productos_personalizacion_tipo_check'
      AND conrelid = 'public.productos'::regclass
  ) THEN
    ALTER TABLE public.productos
      ADD CONSTRAINT productos_personalizacion_tipo_check
      CHECK (personalizacion_tipo IN ('NINGUNA', 'TACO', 'TORTA'));
  END IF;
END;
$$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint c
    JOIN pg_attribute a
      ON a.attrelid = c.conrelid
     AND a.attnum = ANY (c.conkey)
    WHERE c.conrelid = 'public.productos'::regclass
      AND c.contype = 'f'
      AND a.attname = 'categoria_id'
  ) THEN
    ALTER TABLE public.productos
      ADD CONSTRAINT productos_categoria_id_fkey
      FOREIGN KEY (categoria_id)
      REFERENCES public.categorias(id)
      ON DELETE SET NULL;
  END IF;
END;
$$;

-- ----------------------------------------
-- 4. Grupos de modificadores
--    Ejemplos: "Tamaño", "Tipo de Leche", "Extras"
-- ----------------------------------------
CREATE TABLE IF NOT EXISTS public.modificador_grupos (
  id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  tenant_id     uuid NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
  nombre        text NOT NULL,
  obligatorio   bool NOT NULL DEFAULT false,
  seleccion_max int  NOT NULL DEFAULT 1,   -- 1=radio, >1=checkbox múltiple
  orden         int  NOT NULL DEFAULT 100,
  activo        bool NOT NULL DEFAULT true,
  UNIQUE (tenant_id, nombre)
);

-- ----------------------------------------
-- 5. Opciones dentro de un grupo
--    Ejemplos: "Chico" ($0), "Mediano" (+$10), "Grande" (+$15)
-- ----------------------------------------
CREATE TABLE IF NOT EXISTS public.modificador_opciones (
  id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  tenant_id    uuid NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
  grupo_id     bigint NOT NULL REFERENCES public.modificador_grupos(id) ON DELETE CASCADE,
  nombre       text NOT NULL,
  precio_delta numeric(10,2) NOT NULL DEFAULT 0, -- puede ser negativo (descuento)
  es_default   bool NOT NULL DEFAULT false,
  activo       bool NOT NULL DEFAULT true,
  orden        int  NOT NULL DEFAULT 100
);

-- ----------------------------------------
-- 6. Relación M:N producto ↔ grupo de modificadores
-- ----------------------------------------
CREATE TABLE IF NOT EXISTS public.producto_modificador_grupos (
  producto_id bigint NOT NULL REFERENCES public.productos(id) ON DELETE CASCADE,
  grupo_id    bigint NOT NULL REFERENCES public.modificador_grupos(id) ON DELETE CASCADE,
  tenant_id   uuid NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
  orden       int NOT NULL DEFAULT 100,
  PRIMARY KEY (producto_id, grupo_id)
);

-- ----------------------------------------
-- 7. Ampliar comanda_items para snapshots de modificadores
-- ----------------------------------------
ALTER TABLE public.comanda_items
  ADD COLUMN IF NOT EXISTS modificadores_snapshot jsonb DEFAULT '[]'::jsonb,
  -- [{"grupo":"Tamaño","opcion":"Grande","delta":15.00}]
  ADD COLUMN IF NOT EXISTS notas_item text;

-- ----------------------------------------
-- 8. Constraints y triggers de integridad
-- ----------------------------------------
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'modificador_grupos_seleccion_max_check'
      AND conrelid = 'public.modificador_grupos'::regclass
  ) THEN
    ALTER TABLE public.modificador_grupos
      ADD CONSTRAINT modificador_grupos_seleccion_max_check
      CHECK (seleccion_max >= 1);
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'modificador_opciones_grupo_nombre_key'
      AND conrelid = 'public.modificador_opciones'::regclass
  ) THEN
    ALTER TABLE public.modificador_opciones
      ADD CONSTRAINT modificador_opciones_grupo_nombre_key
      UNIQUE (grupo_id, nombre);
  END IF;
END;
$$;

CREATE OR REPLACE FUNCTION public.set_productos_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_productos_updated_at ON public.productos;
CREATE TRIGGER trg_productos_updated_at
BEFORE UPDATE ON public.productos
FOR EACH ROW
EXECUTE FUNCTION public.set_productos_updated_at();

CREATE OR REPLACE FUNCTION public.sync_productos_precios()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  NEW.precio := COALESCE(NEW.precio, NEW.precio_base, 0);
  NEW.precio_base := COALESCE(NEW.precio_base, NEW.precio, 0);
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_productos_sync_precios ON public.productos;
CREATE TRIGGER trg_productos_sync_precios
BEFORE INSERT OR UPDATE ON public.productos
FOR EACH ROW
EXECUTE FUNCTION public.sync_productos_precios();

CREATE OR REPLACE FUNCTION public.validate_modificador_opcion_tenant()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
  v_grupo_tenant uuid;
BEGIN
  SELECT tenant_id INTO v_grupo_tenant
  FROM public.modificador_grupos
  WHERE id = NEW.grupo_id;

  IF v_grupo_tenant IS NULL THEN
    RAISE EXCEPTION 'Grupo de modificador % no existe', NEW.grupo_id;
  END IF;

  IF NEW.tenant_id <> v_grupo_tenant THEN
    RAISE EXCEPTION 'Tenant mismatch: opcion(%) != grupo(%)', NEW.tenant_id, v_grupo_tenant;
  END IF;

  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_modificador_opciones_tenant ON public.modificador_opciones;
CREATE TRIGGER trg_modificador_opciones_tenant
BEFORE INSERT OR UPDATE ON public.modificador_opciones
FOR EACH ROW
EXECUTE FUNCTION public.validate_modificador_opcion_tenant();

CREATE OR REPLACE FUNCTION public.validate_producto_modificador_tenant()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
  v_producto_tenant uuid;
  v_grupo_tenant uuid;
BEGIN
  SELECT tenant_id INTO v_producto_tenant
  FROM public.productos
  WHERE id = NEW.producto_id;

  SELECT tenant_id INTO v_grupo_tenant
  FROM public.modificador_grupos
  WHERE id = NEW.grupo_id;

  IF v_producto_tenant IS NULL OR v_grupo_tenant IS NULL THEN
    RAISE EXCEPTION 'Producto % o Grupo % no existe', NEW.producto_id, NEW.grupo_id;
  END IF;

  IF NEW.tenant_id <> v_producto_tenant OR NEW.tenant_id <> v_grupo_tenant THEN
    RAISE EXCEPTION
      'Tenant mismatch en producto_modificador_grupos: tenant %, producto %, grupo %',
      NEW.tenant_id, v_producto_tenant, v_grupo_tenant;
  END IF;

  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_producto_modificador_tenant ON public.producto_modificador_grupos;
CREATE TRIGGER trg_producto_modificador_tenant
BEFORE INSERT OR UPDATE ON public.producto_modificador_grupos
FOR EACH ROW
EXECUTE FUNCTION public.validate_producto_modificador_tenant();

-- ----------------------------------------
-- 9. Índices de rendimiento
-- ----------------------------------------
CREATE INDEX IF NOT EXISTS idx_productos_tenant      ON public.productos (tenant_id, activo, orden_catalogo);
CREATE INDEX IF NOT EXISTS idx_categorias_tenant     ON public.categorias (tenant_id, activo, orden);
CREATE INDEX IF NOT EXISTS idx_mod_grupos_tenant     ON public.modificador_grupos (tenant_id, activo);
CREATE INDEX IF NOT EXISTS idx_mod_opciones_grupo    ON public.modificador_opciones (grupo_id, activo, orden);
CREATE INDEX IF NOT EXISTS idx_prod_mod_grupos_prod  ON public.producto_modificador_grupos (producto_id);
CREATE INDEX IF NOT EXISTS idx_prod_mod_grupos_tenant ON public.producto_modificador_grupos (tenant_id, orden);
