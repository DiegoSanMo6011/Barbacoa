-- ============================================================
-- AutoNoma POS Lite — Migración 02: Row Level Security
-- Garantiza aislamiento multitenant para tablas nuevas
-- ============================================================

-- Helper function: tenant_id desde app.tenant_id o JWT claims.
CREATE OR REPLACE FUNCTION public.get_tenant_id()
RETURNS uuid
LANGUAGE sql STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT COALESCE(
    NULLIF(current_setting('app.tenant_id', true), ''),
    CASE
      WHEN NULLIF(current_setting('request.jwt.claims', true), '') IS NULL THEN NULL
      ELSE current_setting('request.jwt.claims', true)::jsonb ->> 'tenant_id'
    END
  )::uuid;
$$;

-- ----------------------------------------
-- categorias
-- ----------------------------------------
ALTER TABLE public.categorias ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "categorias_tenant_isolation" ON public.categorias;
DROP POLICY IF EXISTS "categorias_tenant_insert" ON public.categorias;
DROP POLICY IF EXISTS "categorias_tenant_all" ON public.categorias;

CREATE POLICY "categorias_tenant_all"
  ON public.categorias
  FOR ALL
  USING (tenant_id = public.get_tenant_id())
  WITH CHECK (tenant_id = public.get_tenant_id());

-- ----------------------------------------
-- productos
-- ----------------------------------------
ALTER TABLE public.productos ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "productos_tenant_isolation" ON public.productos;
DROP POLICY IF EXISTS "productos_tenant_insert" ON public.productos;
DROP POLICY IF EXISTS "productos_tenant_all" ON public.productos;

CREATE POLICY "productos_tenant_all"
  ON public.productos
  FOR ALL
  USING (tenant_id = public.get_tenant_id())
  WITH CHECK (tenant_id = public.get_tenant_id());

-- ----------------------------------------
-- modificador_grupos
-- ----------------------------------------
ALTER TABLE public.modificador_grupos ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "mod_grupos_tenant_isolation" ON public.modificador_grupos;
DROP POLICY IF EXISTS "mod_grupos_tenant_insert" ON public.modificador_grupos;
DROP POLICY IF EXISTS "mod_grupos_tenant_all" ON public.modificador_grupos;

CREATE POLICY "mod_grupos_tenant_all"
  ON public.modificador_grupos
  FOR ALL
  USING (tenant_id = public.get_tenant_id())
  WITH CHECK (tenant_id = public.get_tenant_id());

-- ----------------------------------------
-- modificador_opciones
-- ----------------------------------------
ALTER TABLE public.modificador_opciones ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "mod_opciones_tenant_isolation" ON public.modificador_opciones;
DROP POLICY IF EXISTS "mod_opciones_tenant_insert" ON public.modificador_opciones;
DROP POLICY IF EXISTS "mod_opciones_tenant_all" ON public.modificador_opciones;

CREATE POLICY "mod_opciones_tenant_all"
  ON public.modificador_opciones
  FOR ALL
  USING (tenant_id = public.get_tenant_id())
  WITH CHECK (tenant_id = public.get_tenant_id());

-- ----------------------------------------
-- producto_modificador_grupos
-- ----------------------------------------
ALTER TABLE public.producto_modificador_grupos ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "prod_mod_grupos_tenant_isolation" ON public.producto_modificador_grupos;
DROP POLICY IF EXISTS "prod_mod_grupos_tenant_insert" ON public.producto_modificador_grupos;
DROP POLICY IF EXISTS "prod_mod_grupos_tenant_all" ON public.producto_modificador_grupos;

CREATE POLICY "prod_mod_grupos_tenant_all"
  ON public.producto_modificador_grupos
  FOR ALL
  USING (tenant_id = public.get_tenant_id())
  WITH CHECK (tenant_id = public.get_tenant_id());
