-- Idempotent migration: jornada controls in cierres_caja.

ALTER TABLE public.cierres_caja
  ADD COLUMN IF NOT EXISTS caja_chica_inicial numeric NOT NULL DEFAULT 0::numeric,
  ADD COLUMN IF NOT EXISTS estado text,
  ADD COLUMN IF NOT EXISTS abierto_at timestamp with time zone,
  ADD COLUMN IF NOT EXISTS cerrado_at timestamp with time zone,
  ADD COLUMN IF NOT EXISTS reaperturas integer,
  ADD COLUMN IF NOT EXISTS reabierto_at timestamp with time zone;

UPDATE public.cierres_caja
SET estado = COALESCE(NULLIF(estado, ''), 'CERRADO')
WHERE estado IS NULL OR estado = '';

UPDATE public.cierres_caja
SET abierto_at = COALESCE(abierto_at, created_at, now())
WHERE abierto_at IS NULL;

UPDATE public.cierres_caja
SET reaperturas = COALESCE(reaperturas, 0)
WHERE reaperturas IS NULL;

ALTER TABLE public.cierres_caja
  ALTER COLUMN estado SET DEFAULT 'CERRADO',
  ALTER COLUMN estado SET NOT NULL,
  ALTER COLUMN abierto_at SET DEFAULT now(),
  ALTER COLUMN abierto_at SET NOT NULL,
  ALTER COLUMN reaperturas SET DEFAULT 0,
  ALTER COLUMN reaperturas SET NOT NULL;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.table_constraints
    WHERE table_schema = 'public'
      AND table_name = 'cierres_caja'
      AND constraint_name = 'cierres_caja_estado_check'
  ) THEN
    ALTER TABLE public.cierres_caja DROP CONSTRAINT cierres_caja_estado_check;
  END IF;

  ALTER TABLE public.cierres_caja
    ADD CONSTRAINT cierres_caja_estado_check
    CHECK (estado = ANY (ARRAY['ABIERTO', 'CERRADO']));
EXCEPTION WHEN duplicate_object THEN
  NULL;
END
$$;

-- Deduplicate by fecha before enforcing uniqueness.
WITH ranked AS (
  SELECT
    ctid,
    fecha,
    ROW_NUMBER() OVER (
      PARTITION BY fecha
      ORDER BY COALESCE(cerrado_at, created_at, now()) DESC, id DESC
    ) AS rn
  FROM public.cierres_caja
)
DELETE FROM public.cierres_caja c
USING ranked r
WHERE c.ctid = r.ctid
  AND r.rn > 1;

CREATE UNIQUE INDEX IF NOT EXISTS cierres_caja_fecha_unique_idx
  ON public.cierres_caja (fecha);
