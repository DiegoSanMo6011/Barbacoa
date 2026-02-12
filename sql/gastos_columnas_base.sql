-- Idempotent migration: columnas base de gastos.

ALTER TABLE public.gastos
  ADD COLUMN IF NOT EXISTS nota text,
  ADD COLUMN IF NOT EXISTS metodo_pago text;

UPDATE public.gastos
SET metodo_pago = 'EFECTIVO'
WHERE metodo_pago IS NULL OR btrim(metodo_pago) = '';

UPDATE public.gastos
SET metodo_pago = 'TRANSFER'
WHERE upper(btrim(metodo_pago)) = 'TRANSFERENCIA';

ALTER TABLE public.gastos
  ALTER COLUMN metodo_pago SET DEFAULT 'EFECTIVO',
  ALTER COLUMN metodo_pago SET NOT NULL;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.table_constraints
    WHERE table_schema = 'public'
      AND table_name = 'gastos'
      AND constraint_name = 'gastos_metodo_pago_check'
  ) THEN
    ALTER TABLE public.gastos DROP CONSTRAINT gastos_metodo_pago_check;
  END IF;

  ALTER TABLE public.gastos
    ADD CONSTRAINT gastos_metodo_pago_check
    CHECK (metodo_pago = ANY (ARRAY['EFECTIVO', 'TARJETA', 'TRANSFER']));
EXCEPTION WHEN duplicate_object THEN
  NULL;
END
$$;
