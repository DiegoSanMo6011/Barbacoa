-- ============================================================
-- AutoNoma POS Lite — Seed Demo: Cafetería
-- Ejecutar DESPUÉS de las migraciones 01-03
-- Reemplazar 'TU-TENANT-ID-AQUI' con el UUID real del tenant
-- ============================================================

DO $$
DECLARE
  v_tenant uuid := 'TU-TENANT-ID-AQUI'::uuid;
  v_cat_tacos bigint;
  v_cat_consomes bigint;
  v_cat_postres bigint;

  v_taco_maciza bigint;
  v_taco_surtida bigint;
  v_taco_costilla bigint;
  v_consome_chico bigint;
  v_consome_grande bigint;
  v_flan_napolitano bigint;
  v_agua_horchata bigint;
  v_refresco_lata bigint;

  v_grp_tamano bigint;
  v_grp_leche bigint;
  v_grp_extras bigint;
  v_grp_temperatura bigint;
BEGIN

  -- ---- CATEGORÍAS ----
  INSERT INTO public.categorias (tenant_id, nombre, orden)
  VALUES
    (v_tenant, 'Tacos', 10),
    (v_tenant, 'Consomés',     20),
    (v_tenant, 'Postres y Bebidas',         30)
  ON CONFLICT (tenant_id, nombre) DO UPDATE
  SET
    orden = EXCLUDED.orden,
    activo = true;

  SELECT id INTO v_cat_tacos   FROM public.categorias WHERE tenant_id = v_tenant AND nombre = 'Tacos';
  SELECT id INTO v_cat_consomes     FROM public.categorias WHERE tenant_id = v_tenant AND nombre = 'Consomés';
  SELECT id INTO v_cat_postres FROM public.categorias WHERE tenant_id = v_tenant AND nombre = 'Postres y Bebidas';

  -- ---- GRUPOS DE MODIFICADORES ----
  INSERT INTO public.modificador_grupos (tenant_id, nombre, obligatorio, seleccion_max, orden)
  VALUES
    (v_tenant, 'Tamaño',        true,  1, 10),
    (v_tenant, 'Tipo de Leche', false, 1, 20),
    (v_tenant, 'Extras',        false, 3, 30),
    (v_tenant, 'Temperatura',   false, 1, 40)
  ON CONFLICT (tenant_id, nombre) DO UPDATE
  SET
    obligatorio = EXCLUDED.obligatorio,
    seleccion_max = EXCLUDED.seleccion_max,
    orden = EXCLUDED.orden,
    activo = true;

  SELECT id INTO v_grp_tamano      FROM public.modificador_grupos WHERE tenant_id = v_tenant AND nombre = 'Tamaño';
  SELECT id INTO v_grp_leche       FROM public.modificador_grupos WHERE tenant_id = v_tenant AND nombre = 'Tipo de Leche';
  SELECT id INTO v_grp_extras      FROM public.modificador_grupos WHERE tenant_id = v_tenant AND nombre = 'Extras';
  SELECT id INTO v_grp_temperatura FROM public.modificador_grupos WHERE tenant_id = v_tenant AND nombre = 'Temperatura';

  -- ---- OPCIONES: Tamaño ----
  INSERT INTO public.modificador_opciones (tenant_id, grupo_id, nombre, precio_delta, es_default, orden)
  VALUES
    (v_tenant, v_grp_tamano, 'Chico',   0,    true,  10),
    (v_tenant, v_grp_tamano, 'Mediano', 10.0, false, 20),
    (v_tenant, v_grp_tamano, 'Grande',  20.0, false, 30)
  ON CONFLICT (grupo_id, nombre) DO UPDATE
  SET
    precio_delta = EXCLUDED.precio_delta,
    es_default = EXCLUDED.es_default,
    orden = EXCLUDED.orden,
    activo = true;

  -- ---- OPCIONES: Tipo de Leche ----
  INSERT INTO public.modificador_opciones (tenant_id, grupo_id, nombre, precio_delta, es_default, orden)
  VALUES
    (v_tenant, v_grp_leche, 'Entera',   0,    true,  10),
    (v_tenant, v_grp_leche, 'Deslactosada', 0, false, 20),
    (v_tenant, v_grp_leche, 'Avena',    10.0, false, 30),
    (v_tenant, v_grp_leche, 'Almendra', 12.0, false, 40),
    (v_tenant, v_grp_leche, 'Soya',     10.0, false, 50)
  ON CONFLICT (grupo_id, nombre) DO UPDATE
  SET
    precio_delta = EXCLUDED.precio_delta,
    es_default = EXCLUDED.es_default,
    orden = EXCLUDED.orden,
    activo = true;

  -- ---- OPCIONES: Extras ----
  INSERT INTO public.modificador_opciones (tenant_id, grupo_id, nombre, precio_delta, es_default, orden)
  VALUES
    (v_tenant, v_grp_extras, 'Shot extra', 15.0, false, 10),
    (v_tenant, v_grp_extras, 'Caramelo',   8.0,  false, 20),
    (v_tenant, v_grp_extras, 'Canela',     5.0,  false, 30),
    (v_tenant, v_grp_extras, 'Vainilla',   8.0,  false, 40)
  ON CONFLICT (grupo_id, nombre) DO UPDATE
  SET
    precio_delta = EXCLUDED.precio_delta,
    es_default = EXCLUDED.es_default,
    orden = EXCLUDED.orden,
    activo = true;

  -- ---- OPCIONES: Temperatura ----
  INSERT INTO public.modificador_opciones (tenant_id, grupo_id, nombre, precio_delta, es_default, orden)
  VALUES
    (v_tenant, v_grp_temperatura, 'Caliente',    0, true,  10),
    (v_tenant, v_grp_temperatura, 'Extra Caliente', 0, false, 20)
  ON CONFLICT (grupo_id, nombre) DO UPDATE
  SET
    precio_delta = EXCLUDED.precio_delta,
    es_default = EXCLUDED.es_default,
    orden = EXCLUDED.orden,
    activo = true;

  -- ---- PRODUCTOS ----
  INSERT INTO public.productos (
    tenant_id,
    categoria_id,
    nombre,
    precio,
    precio_base,
    descripcion,
    orden_catalogo,
    activo,
    precio_abierto,
    personalizacion_tipo
  )
  SELECT
    v_tenant,
    data.categoria_id,
    data.nombre,
    data.precio,
    data.precio_base,
    data.descripcion,
    data.orden_catalogo,
    true,
    data.precio_abierto,
    data.personalizacion_tipo
  FROM (
    VALUES
      (v_cat_tacos,   'Taco de Maciza',       35.0, 35.0, 'Taco tradicional', 10, false, 'TACO'),
      (v_cat_tacos,   'Taco de Surtida',           35.0, 35.0, 'Taco de diversas carnes', 20, false, 'TACO'),
      (v_cat_tacos,   'Taco de Costilla',           40.0, 40.0, 'Taco premium', 30, false, 'TACO'),
      (v_cat_consomes,     'Consomé Chico',               40.0, 40.0, 'Medio litro con carne', 10, false, 'NINGUNA'),
      (v_cat_consomes,     'Consomé Grande',               70.0, 70.0, 'Litro completo', 20, false, 'NINGUNA'),
      (v_cat_postres,       'Flan Napolitano',      45.0, 45.0, 'Rebanada generosa', 10, false, 'NINGUNA'),
      (v_cat_postres,       'Agua de Horchata',     30.0, 30.0, 'Medio Litro', 20, false, 'NINGUNA'),
      (v_cat_postres,       'Refresco Lata',        25.0, 25.0, 'Variedad de sabores', 30, false, 'NINGUNA'),
      (v_cat_postres, 'Pastel personalizable', 0.0, 0.0, 'Costo abierto, sin modificadores', 40, true, 'NINGUNA')
  ) AS data(categoria_id, nombre, precio, precio_base, descripcion, orden_catalogo, precio_abierto, personalizacion_tipo)
  WHERE NOT EXISTS (
    SELECT 1
    FROM public.productos p
    WHERE p.tenant_id = v_tenant
      AND p.nombre = data.nombre
  );

  SELECT id INTO v_taco_maciza     FROM public.productos WHERE tenant_id = v_tenant AND nombre = 'Taco de Maciza';
  SELECT id INTO v_taco_surtida    FROM public.productos WHERE tenant_id = v_tenant AND nombre = 'Taco de Surtida';
  SELECT id INTO v_taco_costilla   FROM public.productos WHERE tenant_id = v_tenant AND nombre = 'Taco de Costilla';
  SELECT id INTO v_consome_chico   FROM public.productos WHERE tenant_id = v_tenant AND nombre = 'Consomé Chico';
  SELECT id INTO v_consome_grande  FROM public.productos WHERE tenant_id = v_tenant AND nombre = 'Consomé Grande';
  SELECT id INTO v_flan_napolitano FROM public.productos WHERE tenant_id = v_tenant AND nombre = 'Flan Napolitano';
  SELECT id INTO v_agua_horchata   FROM public.productos WHERE tenant_id = v_tenant AND nombre = 'Agua de Horchata';
  SELECT id INTO v_refresco_lata   FROM public.productos WHERE tenant_id = v_tenant AND nombre = 'Refresco Lata';

  -- ---- Canonizar "Pastel personalizable" (único, costo abierto y sin plantilla) ----
  UPDATE public.productos
  SET
    nombre = 'Pastel personalizable',
    categoria_id = v_cat_postres,
    precio = 0,
    precio_base = 0,
    precio_abierto = true,
    personalizacion_tipo = 'NINGUNA',
    descripcion = 'Costo abierto, sin modificadores',
    activo = true,
    orden_catalogo = 30
  WHERE id = (
    SELECT p.id
    FROM public.productos p
    WHERE p.tenant_id = v_tenant
      AND lower(p.nombre) = lower('Pastel personalizable')
    ORDER BY p.id
    LIMIT 1
  );

  UPDATE public.productos
  SET activo = false
  WHERE tenant_id = v_tenant
    AND lower(nombre) = lower('Pastel personalizable')
    AND id <> (
      SELECT p.id
      FROM public.productos p
      WHERE p.tenant_id = v_tenant
        AND lower(p.nombre) = lower('Pastel personalizable')
      ORDER BY p.id
      LIMIT 1
    );

  DELETE FROM public.producto_modificador_grupos
  WHERE tenant_id = v_tenant
    AND producto_id IN (
      SELECT id
      FROM public.productos
      WHERE tenant_id = v_tenant
        AND lower(nombre) = lower('Pastel personalizable')
    );

  -- ---- ASIGNAR MODIFICADORES A PRODUCTOS ----
  -- Americano: Tamaño + Extras + Temperatura
  INSERT INTO public.producto_modificador_grupos (tenant_id, producto_id, grupo_id, orden)
  VALUES
    (v_tenant, v_cafe_americano, v_grp_tamano,      10),
    (v_tenant, v_cafe_americano, v_grp_extras,      20),
    (v_tenant, v_cafe_americano, v_grp_temperatura, 30)
  ON CONFLICT (producto_id, grupo_id) DO NOTHING;

  -- Latte: Tamaño + Leche + Extras
  INSERT INTO public.producto_modificador_grupos (tenant_id, producto_id, grupo_id, orden)
  VALUES
    (v_tenant, v_cafe_latte, v_grp_tamano, 10),
    (v_tenant, v_cafe_latte, v_grp_leche,  20),
    (v_tenant, v_cafe_latte, v_grp_extras, 30)
  ON CONFLICT (producto_id, grupo_id) DO NOTHING;

  -- Cappuccino: Tamaño + Leche + Extras
  INSERT INTO public.producto_modificador_grupos (tenant_id, producto_id, grupo_id, orden)
  VALUES
    (v_tenant, v_cappuccino, v_grp_tamano, 10),
    (v_tenant, v_cappuccino, v_grp_leche,  20),
    (v_tenant, v_cappuccino, v_grp_extras, 30)
  ON CONFLICT (producto_id, grupo_id) DO NOTHING;

  -- Frappé: Tamaño + Leche + Extras
  INSERT INTO public.producto_modificador_grupos (tenant_id, producto_id, grupo_id, orden)
  VALUES
    (v_tenant, v_frappe, v_grp_tamano, 10),
    (v_tenant, v_frappe, v_grp_leche,  20),
    (v_tenant, v_frappe, v_grp_extras, 30)
  ON CONFLICT (producto_id, grupo_id) DO NOTHING;

  -- Croissant y Panque: sin modificadores (precio fijo)

  RAISE NOTICE '✅ Seed completado para tenant %', v_tenant;
END;
$$;
