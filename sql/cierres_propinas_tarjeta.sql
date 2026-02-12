-- Idempotent migration: snapshot de propinas TARJETA en cierres_caja.

ALTER TABLE public.cierres_caja
  ADD COLUMN IF NOT EXISTS total_propinas_tarjeta numeric,
  ADD COLUMN IF NOT EXISTS propinas_tarjeta_detalle jsonb;

UPDATE public.cierres_caja
SET total_propinas_tarjeta = COALESCE(total_propinas_tarjeta, 0::numeric)
WHERE total_propinas_tarjeta IS NULL;

UPDATE public.cierres_caja
SET propinas_tarjeta_detalle = COALESCE(propinas_tarjeta_detalle, '[]'::jsonb)
WHERE propinas_tarjeta_detalle IS NULL;

ALTER TABLE public.cierres_caja
  ALTER COLUMN total_propinas_tarjeta SET DEFAULT 0::numeric,
  ALTER COLUMN total_propinas_tarjeta SET NOT NULL,
  ALTER COLUMN propinas_tarjeta_detalle SET DEFAULT '[]'::jsonb,
  ALTER COLUMN propinas_tarjeta_detalle SET NOT NULL;
