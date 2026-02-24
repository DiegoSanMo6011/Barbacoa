-- Idempotent migration: comandas auditables + pagos mixtos + historial de tickets.

ALTER TABLE public.comandas
  ADD COLUMN IF NOT EXISTS mesa text,
  ADD COLUMN IF NOT EXISTS status text,
  ADD COLUMN IF NOT EXISTS cancelada_at timestamp with time zone,
  ADD COLUMN IF NOT EXISTS cancelada_por text,
  ADD COLUMN IF NOT EXISTS cancelacion_motivo text;

UPDATE public.comandas
SET status = COALESCE(NULLIF(status, ''), 'PAGADA')
WHERE status IS NULL OR status = '';

ALTER TABLE public.comandas
  ALTER COLUMN status SET DEFAULT 'PAGADA',
  ALTER COLUMN status SET NOT NULL;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.table_constraints
    WHERE table_schema = 'public'
      AND table_name = 'comandas'
      AND constraint_name = 'comandas_status_check'
  ) THEN
    ALTER TABLE public.comandas DROP CONSTRAINT comandas_status_check;
  END IF;

  ALTER TABLE public.comandas
    ADD CONSTRAINT comandas_status_check
    CHECK (status = ANY (ARRAY['PAGADA', 'CANCELADA', 'CORREGIDA']));
EXCEPTION WHEN duplicate_object THEN
  NULL;
END
$$;

CREATE TABLE IF NOT EXISTS public.comanda_pagos (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  comanda_id uuid NOT NULL,
  orden integer NOT NULL DEFAULT 1,
  metodo_pago text NOT NULL,
  monto numeric NOT NULL CHECK (monto >= 0),
  recibido numeric,
  cambio numeric,
  propina numeric NOT NULL DEFAULT 0 CHECK (propina >= 0),
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT comanda_pagos_pkey PRIMARY KEY (id),
  CONSTRAINT comanda_pagos_comanda_fkey FOREIGN KEY (comanda_id) REFERENCES public.comandas(id) ON DELETE CASCADE
);

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.table_constraints
    WHERE table_schema = 'public'
      AND table_name = 'comanda_pagos'
      AND constraint_name = 'comanda_pagos_metodo_pago_check'
  ) THEN
    ALTER TABLE public.comanda_pagos DROP CONSTRAINT comanda_pagos_metodo_pago_check;
  END IF;

  ALTER TABLE public.comanda_pagos
    ADD CONSTRAINT comanda_pagos_metodo_pago_check
    CHECK (metodo_pago = ANY (ARRAY['EFECTIVO', 'TARJETA', 'TRANSFER']));
EXCEPTION WHEN duplicate_object THEN
  NULL;
END
$$;

CREATE INDEX IF NOT EXISTS comanda_pagos_comanda_idx ON public.comanda_pagos (comanda_id, orden);

INSERT INTO public.comanda_pagos (comanda_id, orden, metodo_pago, monto, recibido, cambio, propina)
SELECT
  c.id,
  1,
  COALESCE(NULLIF(c.metodo_pago, ''), 'EFECTIVO'),
  COALESCE(c.total, 0),
  c.recibido,
  c.cambio,
  0
FROM public.comandas c
WHERE NOT EXISTS (
  SELECT 1 FROM public.comanda_pagos p WHERE p.comanda_id = c.id
);

CREATE TABLE IF NOT EXISTS public.comanda_correcciones (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  comanda_id uuid NOT NULL,
  motivo text NOT NULL,
  before_payload jsonb NOT NULL,
  after_payload jsonb NOT NULL,
  corregido_por text NOT NULL,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT comanda_correcciones_pkey PRIMARY KEY (id),
  CONSTRAINT comanda_correcciones_comanda_fkey FOREIGN KEY (comanda_id) REFERENCES public.comandas(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS comanda_correcciones_comanda_idx ON public.comanda_correcciones (comanda_id, created_at);

CREATE TABLE IF NOT EXISTS public.ticket_historial (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  comanda_id uuid NOT NULL,
  version integer NOT NULL,
  tipo text NOT NULL,
  ticket_text text NOT NULL,
  created_by text,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT ticket_historial_pkey PRIMARY KEY (id),
  CONSTRAINT ticket_historial_comanda_fkey FOREIGN KEY (comanda_id) REFERENCES public.comandas(id) ON DELETE CASCADE
);

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.table_constraints
    WHERE table_schema = 'public'
      AND table_name = 'ticket_historial'
      AND constraint_name = 'ticket_historial_tipo_check'
  ) THEN
    ALTER TABLE public.ticket_historial DROP CONSTRAINT ticket_historial_tipo_check;
  END IF;

  ALTER TABLE public.ticket_historial
    ADD CONSTRAINT ticket_historial_tipo_check
    CHECK (tipo = ANY (ARRAY['ORIGINAL', 'CORREGIDO']));
EXCEPTION WHEN duplicate_object THEN
  NULL;
END
$$;

CREATE UNIQUE INDEX IF NOT EXISTS ticket_historial_comanda_version_uq
  ON public.ticket_historial (comanda_id, version);

CREATE INDEX IF NOT EXISTS ticket_historial_comanda_created_idx
  ON public.ticket_historial (comanda_id, created_at DESC);
