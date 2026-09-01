-- Idempotent migration: índice sobre gastos(created_at).
--
-- Todas las consultas de gastos (corte, listado del día, analítica) filtran
-- por rango de created_at — la tabla no tiene columna de fecha propia — y la
-- columna no estaba indexada.
--
-- Ejecutar a mano en el SQL editor de Supabase (BD de Miranda). No corre
-- automáticamente.

CREATE INDEX IF NOT EXISTS gastos_created_at_idx
  ON public.gastos (created_at);
