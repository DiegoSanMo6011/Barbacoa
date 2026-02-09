-- Idempotent migration for role-based access in Barbacoa POS.

CREATE TABLE IF NOT EXISTS public.usuarios (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  nombre text NOT NULL,
  usuario text NOT NULL,
  password_hash text NOT NULL,
  rol text NOT NULL,
  activo boolean NOT NULL DEFAULT true,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  updated_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT usuarios_pkey PRIMARY KEY (id)
);

ALTER TABLE public.usuarios
  ADD COLUMN IF NOT EXISTS nombre text,
  ADD COLUMN IF NOT EXISTS usuario text,
  ADD COLUMN IF NOT EXISTS password_hash text,
  ADD COLUMN IF NOT EXISTS rol text,
  ADD COLUMN IF NOT EXISTS activo boolean NOT NULL DEFAULT true,
  ADD COLUMN IF NOT EXISTS created_at timestamp with time zone NOT NULL DEFAULT now(),
  ADD COLUMN IF NOT EXISTS updated_at timestamp with time zone NOT NULL DEFAULT now();

-- Legacy compatibility: ADMIN is now DUENIO.
UPDATE public.usuarios
SET rol = 'DUENIO',
    updated_at = now()
WHERE rol = 'ADMIN';

-- Keep one row per role before enforcing uniqueness.
WITH ranked AS (
  SELECT
    ctid,
    rol,
    ROW_NUMBER() OVER (
      PARTITION BY rol
      ORDER BY COALESCE(updated_at, created_at, now()) DESC, id DESC
    ) AS rn
  FROM public.usuarios
)
DELETE FROM public.usuarios u
USING ranked r
WHERE u.ctid = r.ctid
  AND r.rn > 1;

-- Keep one credential row per role.
CREATE UNIQUE INDEX IF NOT EXISTS usuarios_role_unique_idx ON public.usuarios (rol);

-- Allow only current roles.
DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.table_constraints
    WHERE table_schema = 'public'
      AND table_name = 'usuarios'
      AND constraint_name = 'usuarios_rol_check'
  ) THEN
    ALTER TABLE public.usuarios DROP CONSTRAINT usuarios_rol_check;
  END IF;

  ALTER TABLE public.usuarios
    ADD CONSTRAINT usuarios_rol_check CHECK (rol = ANY (ARRAY['GERENTE', 'DUENIO']));
EXCEPTION WHEN duplicate_object THEN
  NULL;
END
$$;
