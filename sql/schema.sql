-- WARNING: This schema is for context only and is not meant to be run.
-- Table order and constraints may not be valid for execution.

CREATE TABLE public.cierres_caja (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  fecha date NOT NULL,
  total_ventas numeric NOT NULL,
  total_gastos numeric NOT NULL,
  neto numeric NOT NULL,
  efectivo_reportado numeric NOT NULL,
  diferencia_efectivo numeric NOT NULL,
  notas text,
  CONSTRAINT cierres_caja_pkey PRIMARY KEY (id)
);

CREATE TABLE public.comanda_items (
  id bigint NOT NULL DEFAULT nextval('comanda_items_id_seq'::regclass),
  comanda_id uuid NOT NULL,
  producto_id bigint NOT NULL,
  nombre_snapshot text NOT NULL,
  precio_unitario numeric NOT NULL CHECK (precio_unitario >= 0::numeric),
  cantidad integer NOT NULL CHECK (cantidad > 0),
  subtotal numeric NOT NULL CHECK (subtotal >= 0::numeric),
  CONSTRAINT comanda_items_pkey PRIMARY KEY (id),
  CONSTRAINT comanda_items_comanda_id_fkey FOREIGN KEY (comanda_id) REFERENCES public.comandas(id),
  CONSTRAINT comanda_items_producto_id_fkey FOREIGN KEY (producto_id) REFERENCES public.productos(id)
);

CREATE TABLE public.comandas (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  folio bigint NOT NULL DEFAULT nextval('comandas_folio_seq'::regclass) UNIQUE,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  metodo_pago text NOT NULL CHECK (metodo_pago = ANY (ARRAY['EFECTIVO'::text, 'TARJETA'::text, 'TRANSFER'::text])),
  total numeric NOT NULL CHECK (total >= 0::numeric),
  notas text,
  mesero text,
  recibido numeric,
  cambio numeric,
  status text NOT NULL DEFAULT 'PAGADA'::text,
  CONSTRAINT comandas_pkey PRIMARY KEY (id)
);

CREATE TABLE public.gastos (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  concepto text NOT NULL,
  categoria text NOT NULL DEFAULT 'GENERAL'::text,
  monto numeric NOT NULL CHECK (monto > 0::numeric),
  nota text,
  CONSTRAINT gastos_pkey PRIMARY KEY (id)
);

CREATE TABLE public.meseros (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  nombre text NOT NULL,
  activo boolean NOT NULL DEFAULT true,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT meseros_pkey PRIMARY KEY (id)
);

CREATE TABLE public.productos (
  id bigint NOT NULL DEFAULT nextval('productos_id_seq'::regclass),
  nombre text NOT NULL,
  precio numeric NOT NULL CHECK (precio >= 0::numeric),
  categoria text NOT NULL DEFAULT 'GENERAL'::text,
  activo boolean NOT NULL DEFAULT true,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT productos_pkey PRIMARY KEY (id)
);

CREATE TABLE public.propinas (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  fecha timestamp with time zone NOT NULL DEFAULT now(),
  mesero_id uuid,
  mesero_nombre_snapshot text,
  monto numeric NOT NULL,
  fuente text NOT NULL DEFAULT 'MANUAL'::text,
  comanda_id uuid,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT propinas_pkey PRIMARY KEY (id),
  CONSTRAINT propinas_mesero_id_fkey FOREIGN KEY (mesero_id) REFERENCES public.meseros(id),
  CONSTRAINT propinas_comanda_id_fkey FOREIGN KEY (comanda_id) REFERENCES public.comandas(id)
);
