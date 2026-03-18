-- ============================================================
-- Migración 10 — RPCs de jornada / corte
-- ============================================================

ALTER TABLE public.cierres_caja
  ADD COLUMN IF NOT EXISTS tenant_id uuid,
  ADD COLUMN IF NOT EXISTS fecha date DEFAULT CURRENT_DATE,
  ADD COLUMN IF NOT EXISTS status text DEFAULT 'ABIERTA',
  ADD COLUMN IF NOT EXISTS caja_chica_inicial numeric DEFAULT 0,
  ADD COLUMN IF NOT EXISTS total_ventas numeric DEFAULT 0,
  ADD COLUMN IF NOT EXISTS total_efectivo numeric DEFAULT 0,
  ADD COLUMN IF NOT EXISTS total_tarjeta numeric DEFAULT 0,
  ADD COLUMN IF NOT EXISTS total_transfer numeric DEFAULT 0,
  ADD COLUMN IF NOT EXISTS total_gastos numeric DEFAULT 0,
  ADD COLUMN IF NOT EXISTS total_propinas_tarjeta numeric DEFAULT 0,
  ADD COLUMN IF NOT EXISTS efectivo_teorico numeric DEFAULT 0,
  ADD COLUMN IF NOT EXISTS efectivo_contado numeric,
  ADD COLUMN IF NOT EXISTS diferencia numeric,
  ADD COLUMN IF NOT EXISTS folio_corte text,
  ADD COLUMN IF NOT EXISTS abierta_por text,
  ADD COLUMN IF NOT EXISTS cerrada_por text,
  ADD COLUMN IF NOT EXISTS fecha_cierre timestamp with time zone;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.table_constraints
    WHERE table_schema = 'public'
      AND table_name = 'cierres_caja'
      AND constraint_name = 'cierres_caja_status_check'
  ) THEN
    ALTER TABLE public.cierres_caja DROP CONSTRAINT cierres_caja_status_check;
  END IF;

  ALTER TABLE public.cierres_caja
    ADD CONSTRAINT cierres_caja_status_check
    CHECK (status = ANY (ARRAY['ABIERTA', 'CERRADA']));
EXCEPTION WHEN duplicate_object THEN
  NULL;
END
$$;

CREATE UNIQUE INDEX IF NOT EXISTS cierres_caja_tenant_fecha_uq
  ON public.cierres_caja (tenant_id, fecha);

-- Si existen funciones legacy con la misma firma pero distinto retorno,
-- hay que eliminarlas antes de recrearlas.
DROP FUNCTION IF EXISTS public.get_jornada_activa(uuid);
DROP FUNCTION IF EXISTS public.abrir_jornada(uuid, numeric, text);
DROP FUNCTION IF EXISTS public.abrir_jornada(uuid, numeric);
DROP FUNCTION IF EXISTS public.cerrar_jornada(uuid, numeric, numeric, numeric, text, text);
DROP FUNCTION IF EXISTS public.cerrar_jornada(uuid, numeric, uuid);
DROP FUNCTION IF EXISTS public.reabrir_jornada(uuid, uuid, text);

CREATE OR REPLACE FUNCTION public.get_jornada_activa(
  p_tenant_id uuid
)
RETURNS TABLE (
  id uuid,
  tenant_id uuid,
  fecha date,
  status text,
  caja_chica_inicial numeric,
  total_ventas numeric,
  total_efectivo numeric,
  total_tarjeta numeric,
  total_transfer numeric,
  total_gastos numeric,
  total_propinas_tarjeta numeric,
  efectivo_teorico numeric,
  efectivo_contado numeric,
  diferencia numeric,
  folio_corte text,
  created_at timestamp with time zone,
  fecha_cierre timestamp with time zone
)
LANGUAGE sql
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT
    c.id,
    c.tenant_id,
    c.fecha,
    c.status,
    c.caja_chica_inicial,
    c.total_ventas,
    c.total_efectivo,
    c.total_tarjeta,
    c.total_transfer,
    c.total_gastos,
    c.total_propinas_tarjeta,
    c.efectivo_teorico,
    c.efectivo_contado,
    c.diferencia,
    c.folio_corte,
    c.created_at,
    c.fecha_cierre
  FROM public.cierres_caja c
  WHERE c.tenant_id = p_tenant_id
    AND c.fecha = CURRENT_DATE
  ORDER BY c.created_at DESC
  LIMIT 1;
$$;

CREATE OR REPLACE FUNCTION public.abrir_jornada(
  p_tenant_id uuid,
  p_caja_chica numeric,
  p_usuario text DEFAULT NULL
)
RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_id uuid;
BEGIN
  SELECT id
    INTO v_id
  FROM public.cierres_caja
  WHERE tenant_id = p_tenant_id
    AND fecha = CURRENT_DATE
  LIMIT 1;

  IF v_id IS NOT NULL THEN
    UPDATE public.cierres_caja
      SET status = 'ABIERTA',
          caja_chica_inicial = COALESCE(p_caja_chica, caja_chica_inicial),
          abierta_por = COALESCE(NULLIF(p_usuario, ''), abierta_por)
    WHERE id = v_id;
    RETURN v_id;
  END IF;

  INSERT INTO public.cierres_caja (
    tenant_id,
    fecha,
    status,
    caja_chica_inicial,
    total_ventas,
    total_efectivo,
    total_tarjeta,
    total_transfer,
    total_gastos,
    total_propinas_tarjeta,
    abierta_por
  )
  VALUES (
    p_tenant_id,
    CURRENT_DATE,
    'ABIERTA',
    COALESCE(p_caja_chica, 0),
    0, 0, 0, 0, 0, 0,
    COALESCE(NULLIF(p_usuario, ''), 'SYSTEM')
  )
  RETURNING id INTO v_id;

  RETURN v_id;
END;
$$;

CREATE OR REPLACE FUNCTION public.cerrar_jornada(
  p_cierre_id uuid,
  p_efectivo_contado numeric,
  p_gastos_total numeric DEFAULT 0,
  p_propinas_tarjeta numeric DEFAULT 0,
  p_folio_corte text DEFAULT NULL,
  p_usuario text DEFAULT NULL
)
RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_row public.cierres_caja%ROWTYPE;
  v_efectivo_teorico numeric;
BEGIN
  SELECT *
    INTO v_row
  FROM public.cierres_caja
  WHERE id = p_cierre_id
  FOR UPDATE;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'Cierre de caja no encontrado.';
  END IF;

  v_efectivo_teorico :=
      COALESCE(v_row.caja_chica_inicial, 0)
    + COALESCE(v_row.total_efectivo, 0)
    - COALESCE(NULLIF(p_gastos_total, 0), v_row.total_gastos, 0)
    - COALESCE(NULLIF(p_propinas_tarjeta, 0), v_row.total_propinas_tarjeta, 0);

  UPDATE public.cierres_caja
  SET
    status = 'CERRADA',
    total_gastos = COALESCE(NULLIF(p_gastos_total, 0), total_gastos, 0),
    total_propinas_tarjeta = COALESCE(NULLIF(p_propinas_tarjeta, 0), total_propinas_tarjeta, 0),
    efectivo_teorico = v_efectivo_teorico,
    efectivo_contado = p_efectivo_contado,
    diferencia = COALESCE(p_efectivo_contado, 0) - COALESCE(v_efectivo_teorico, 0),
    folio_corte = COALESCE(NULLIF(p_folio_corte, ''), folio_corte),
    fecha_cierre = now(),
    cerrada_por = COALESCE(NULLIF(p_usuario, ''), cerrada_por)
  WHERE id = p_cierre_id;

  RETURN p_cierre_id;
END;
$$;

CREATE OR REPLACE FUNCTION public.reabrir_jornada(
  p_cierre_id uuid,
  p_tenant_id uuid,
  p_pin_duenio text DEFAULT NULL
)
RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  UPDATE public.cierres_caja
  SET
    status = 'ABIERTA',
    efectivo_contado = NULL,
    diferencia = NULL,
    folio_corte = NULL,
    fecha_cierre = NULL
  WHERE id = p_cierre_id
    AND tenant_id = p_tenant_id;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'Jornada no encontrada.';
  END IF;

  RETURN p_cierre_id;
END;
$$;
