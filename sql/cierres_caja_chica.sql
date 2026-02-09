-- Idempotent migration: add caja_chica_inicial to cierres_caja.

ALTER TABLE public.cierres_caja
  ADD COLUMN IF NOT EXISTS caja_chica_inicial numeric NOT NULL DEFAULT 0::numeric;
