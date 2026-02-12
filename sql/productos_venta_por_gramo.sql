-- Idempotent migration:
-- 1) allow products sold by weight (grams)
-- 2) persistent custom ordering in catalog

ALTER TABLE public.productos
  ADD COLUMN IF NOT EXISTS venta_por_gramo boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS orden_catalogo integer NOT NULL DEFAULT 1000;
