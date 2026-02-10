-- Idempotent migration: use propinas.fuente as payment-origin for tips.

ALTER TABLE public.propinas
  ALTER COLUMN fuente SET DEFAULT 'NO_ESPECIFICADO';

-- Legacy COMANDA rows: infer origin from related comanda payment method.
UPDATE public.propinas p
SET fuente = c.metodo_pago
FROM public.comandas c
WHERE p.comanda_id = c.id
  AND (p.fuente = 'COMANDA' OR p.fuente IS NULL OR btrim(p.fuente) = '')
  AND c.metodo_pago IN ('EFECTIVO', 'TARJETA', 'TRANSFER');

-- Legacy MANUAL / unknown rows become explicit "NO_ESPECIFICADO".
UPDATE public.propinas
SET fuente = 'NO_ESPECIFICADO'
WHERE fuente IS NULL
   OR btrim(fuente) = ''
   OR fuente IN ('MANUAL', 'COMANDA');

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.table_constraints
    WHERE table_schema = 'public'
      AND table_name = 'propinas'
      AND constraint_name = 'propinas_fuente_check'
  ) THEN
    ALTER TABLE public.propinas DROP CONSTRAINT propinas_fuente_check;
  END IF;

  ALTER TABLE public.propinas
    ADD CONSTRAINT propinas_fuente_check
    CHECK (fuente = ANY (ARRAY['EFECTIVO', 'TARJETA', 'TRANSFER', 'NO_ESPECIFICADO']));
EXCEPTION WHEN duplicate_object THEN
  NULL;
END
$$;
