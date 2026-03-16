-- ============================================================
-- AutoNoma POS Lite — Migración 03: RPCs Principales
-- ============================================================

-- ----------------------------------------
-- RPC: Catálogo completo con modificadores
-- Retorna productos + grupos + opciones en un solo query
-- ----------------------------------------
CREATE OR REPLACE FUNCTION public.get_catalogo_lite(
  p_tenant_id uuid
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_result jsonb;
  v_claim_tenant uuid;
BEGIN
  v_claim_tenant := public.get_tenant_id();
  IF v_claim_tenant IS NOT NULL AND v_claim_tenant <> p_tenant_id THEN
    RAISE EXCEPTION 'Tenant mismatch en get_catalogo_lite';
  END IF;

  SELECT jsonb_build_object(
    'categorias', COALESCE((
      SELECT jsonb_agg(
        jsonb_build_object(
          'id',     c.id,
          'nombre', c.nombre,
          'orden',  c.orden,
          'productos', COALESCE((
            SELECT jsonb_agg(
              jsonb_build_object(
                'id',             p.id,
                'nombre',         p.nombre,
                'precio_base',    p.precio_base,
                'precio_abierto', p.precio_abierto,
                'personalizacion_tipo', p.personalizacion_tipo,
                'descripcion',    p.descripcion,
                'orden_catalogo', p.orden_catalogo,
                'modificadores',  COALESCE((
                  SELECT jsonb_agg(
                    jsonb_build_object(
                      'grupo_id',     mg.id,
                      'grupo_nombre', mg.nombre,
                      'obligatorio',  mg.obligatorio,
                      'seleccion_max',mg.seleccion_max,
                      'orden',        mg.orden,
                      'opciones', COALESCE((
                        SELECT jsonb_agg(
                          jsonb_build_object(
                            'id',          mo.id,
                            'nombre',      mo.nombre,
                            'precio_delta',mo.precio_delta,
                            'es_default',  mo.es_default,
                            'orden',       mo.orden
                          ) ORDER BY mo.orden
                        )
                        FROM public.modificador_opciones mo
                        WHERE mo.grupo_id = mg.id AND mo.activo = true
                      ), '[]'::jsonb)
                    ) ORDER BY mg.orden
                  )
                  FROM public.producto_modificador_grupos pmg
                  JOIN public.modificador_grupos mg ON mg.id = pmg.grupo_id
                  WHERE pmg.producto_id = p.id AND mg.activo = true
                ), '[]'::jsonb)
              ) ORDER BY p.orden_catalogo
            )
            FROM public.productos p
            WHERE p.categoria_id = c.id
              AND p.tenant_id = p_tenant_id
              AND p.activo = true
          ), '[]'::jsonb)
        ) ORDER BY c.orden
      )
      FROM public.categorias c
      WHERE c.tenant_id = p_tenant_id AND c.activo = true
    ), '[]'::jsonb)
  ) INTO v_result;

  RETURN v_result;
END;
$$;

-- ----------------------------------------
-- RPC: Crear venta (comanda) con items que incluyen modificadores
-- ----------------------------------------
ALTER TABLE public.comandas
  ADD COLUMN IF NOT EXISTS client_sale_id uuid;

CREATE OR REPLACE FUNCTION public.crear_venta_lite(
  p_tenant_id   uuid,
  p_client_sale_id uuid,
  p_items       jsonb,   -- [{producto_id, nombre_snapshot, precio_unitario, cantidad, modificadores_snapshot, notas_item}]
  p_pago        jsonb,   -- {metodo: EFECTIVO|TARJETA|TRANSFER, monto, recibido?}
  p_total       numeric,
  p_notas       text DEFAULT NULL
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_comanda_id  uuid;
  v_folio       int;
  v_cambio      numeric;
  v_claim_tenant uuid;
  v_total_calculado numeric;
  v_jornada_id uuid;
  v_existing_record record;
BEGIN
  v_claim_tenant := public.get_tenant_id();
  IF v_claim_tenant IS NOT NULL AND v_claim_tenant <> p_tenant_id THEN
    RAISE EXCEPTION 'Tenant mismatch en crear_venta_lite';
  END IF;

  IF p_client_sale_id IS NULL THEN
    RAISE EXCEPTION 'client_sale_id es requerido';
  END IF;

  -- Idempotencia por venta cliente: si ya existe, retornar la venta previa.
  SELECT c.id, c.folio, c.total, COALESCE(cp.cambio, 0) AS cambio
    INTO v_existing_record
  FROM public.comandas c
  LEFT JOIN public.comanda_pagos cp
    ON cp.comanda_id = c.id
   AND cp.tenant_id = c.tenant_id
   AND cp.orden = 1
  WHERE c.tenant_id = p_tenant_id
    AND c.client_sale_id = p_client_sale_id
  LIMIT 1;
  IF FOUND THEN
    RETURN jsonb_build_object(
      'comanda_id', v_existing_record.id,
      'folio',      v_existing_record.folio,
      'total',      v_existing_record.total,
      'cambio',     v_existing_record.cambio,
      'deduplicated', true
    );
  END IF;

  IF (p_pago->>'metodo') NOT IN ('EFECTIVO', 'TARJETA', 'TRANSFER') THEN
    RAISE EXCEPTION 'Metodo de pago inválido';
  END IF;

  SELECT COALESCE(
    SUM(
      (item->>'precio_unitario')::numeric
      * COALESCE((item->>'cantidad')::int, 1)
    ), 0
  )
    INTO v_total_calculado
  FROM jsonb_array_elements(p_items) AS item;

  IF abs(COALESCE(v_total_calculado, 0) - COALESCE(p_total, 0)) > 0.01 THEN
    RAISE EXCEPTION 'Total inconsistente: esperado %, recibido %', v_total_calculado, p_total;
  END IF;

  -- Evita colisión de folios bajo concurrencia por tenant.
  PERFORM pg_advisory_xact_lock(hashtext(p_tenant_id::text), 1);

  -- Revalidar idempotencia dentro del lock para evitar carrera.
  SELECT c.id, c.folio, c.total, COALESCE(cp.cambio, 0) AS cambio
    INTO v_existing_record
  FROM public.comandas c
  LEFT JOIN public.comanda_pagos cp
    ON cp.comanda_id = c.id
   AND cp.tenant_id = c.tenant_id
   AND cp.orden = 1
  WHERE c.tenant_id = p_tenant_id
    AND c.client_sale_id = p_client_sale_id
  LIMIT 1;
  IF FOUND THEN
    RETURN jsonb_build_object(
      'comanda_id', v_existing_record.id,
      'folio',      v_existing_record.folio,
      'total',      v_existing_record.total,
      'cambio',     v_existing_record.cambio,
      'deduplicated', true
    );
  END IF;

  -- Jornada abierta obligatoria para registrar ventas.
  SELECT id
    INTO v_jornada_id
  FROM public.cierres_caja
  WHERE tenant_id = p_tenant_id
    AND fecha = CURRENT_DATE
    AND status = 'ABIERTA'
  ORDER BY created_at DESC
  LIMIT 1;
  IF v_jornada_id IS NULL THEN
    RAISE EXCEPTION 'No hay jornada ABIERTA para registrar venta';
  END IF;

  -- Siguiente folio del tenant
  SELECT COALESCE(MAX(folio), 0) + 1
    INTO v_folio
  FROM public.comandas
  WHERE tenant_id = p_tenant_id;

  -- Calcular cambio si es efectivo
  v_cambio := CASE
    WHEN (p_pago->>'metodo') = 'EFECTIVO'
    THEN GREATEST(0, COALESCE((p_pago->>'recibido')::numeric, p_total) - p_total)
    ELSE 0
  END;

  -- Insertar comanda
  INSERT INTO public.comandas (
    tenant_id, folio, total, notas, status, metodo_pago, client_sale_id
  )
  VALUES (
    p_tenant_id,
    v_folio,
    p_total,
    p_notas,
    'PAGADA',
    p_pago->>'metodo',
    p_client_sale_id
  )
  RETURNING id INTO v_comanda_id;

  -- Insertar items con snapshot de modificadores
  INSERT INTO public.comanda_items (
    tenant_id,
    comanda_id,
    producto_id,
    nombre_snapshot,
    precio_unitario,
    cantidad,
    subtotal,
    modificadores_snapshot,
    notas_item
  )
  SELECT
    p_tenant_id,
    v_comanda_id,
    (item->>'producto_id')::bigint,
    item->>'nombre_snapshot',
    (item->>'precio_unitario')::numeric,
    COALESCE((item->>'cantidad')::int, 1),
    (item->>'precio_unitario')::numeric * COALESCE((item->>'cantidad')::int, 1),
    COALESCE(item->'modificadores_snapshot', '[]'::jsonb),
    item->>'notas_item'
  FROM jsonb_array_elements(p_items) AS item;

  -- Insertar pago
  INSERT INTO public.comanda_pagos (
    tenant_id,
    comanda_id,
    orden,
    metodo_pago,
    monto,
    recibido,
    cambio,
    propina
  )
  VALUES (
    p_tenant_id,
    v_comanda_id,
    1,
    p_pago->>'metodo',
    p_total,
    COALESCE((p_pago->>'recibido')::numeric, p_total),
    v_cambio,
    0
  );

  -- Actualizar totales en jornada activa (obligatoria en este flujo)
  UPDATE public.cierres_caja
  SET
    total_ventas = total_ventas + p_total,
    total_efectivo = total_efectivo + CASE WHEN (p_pago->>'metodo') = 'EFECTIVO' THEN p_total ELSE 0 END,
    total_tarjeta  = total_tarjeta  + CASE WHEN (p_pago->>'metodo') = 'TARJETA'  THEN p_total ELSE 0 END,
    total_transfer = total_transfer + CASE WHEN (p_pago->>'metodo') = 'TRANSFER' THEN p_total ELSE 0 END
  WHERE id = v_jornada_id;

  RETURN jsonb_build_object(
    'comanda_id', v_comanda_id,
    'folio',      v_folio,
    'total',      p_total,
    'cambio',     v_cambio,
    'deduplicated', false
  );
END;
$$;
