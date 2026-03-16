-- ============================================================
-- AutoNoma POS Lite — Migración 04: Go-Live hardening
-- ============================================================

-- Compatibilidad para generar UUID aleatorio en backfill.
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ----------------------------------------
-- Idempotencia de ventas: client_sale_id en comandas
-- ----------------------------------------
ALTER TABLE public.comandas
  ADD COLUMN IF NOT EXISTS client_sale_id uuid;

UPDATE public.comandas
SET client_sale_id = gen_random_uuid()
WHERE client_sale_id IS NULL;

ALTER TABLE public.comandas
  ALTER COLUMN client_sale_id SET NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_comandas_tenant_client_sale_id
  ON public.comandas (tenant_id, client_sale_id);

-- ----------------------------------------
-- Auditoría mínima de eventos críticos
-- ----------------------------------------
CREATE TABLE IF NOT EXISTS public.audit_eventos (
  id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  tenant_id   uuid NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
  evento      text NOT NULL,
  rol         text,
  usuario     text,
  session_id  text,
  request_id  text,
  ip          text,
  path        text,
  metadata    jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_audit_eventos_tenant_created
  ON public.audit_eventos (tenant_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_audit_eventos_evento
  ON public.audit_eventos (evento, created_at DESC);

ALTER TABLE public.audit_eventos ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "audit_eventos_tenant_all" ON public.audit_eventos;
CREATE POLICY "audit_eventos_tenant_all"
  ON public.audit_eventos
  FOR ALL
  USING (tenant_id = public.get_tenant_id())
  WITH CHECK (tenant_id = public.get_tenant_id());
