# AutoNoma POS

Sistema de Punto de Venta (POS) para operación real en restaurante, con enfoque en velocidad de captura, confiabilidad offline y administración centralizada. Ejecuta en Raspberry Pi con backend en Supabase.

## Visión

- Captura rápida de comandas con atajos y edición inline.
- Operación continua con modo offline y sincronización automática.
- Módulos administrativos: gastos, propinas, corte y reportes.
- Catálogo de productos y personal editable desde la UI.

## Arquitectura

**Frontend local**
- Python + Tkinter/ttk + CustomTkinter.
- UI full-screen, optimizada para caja.

**Backend**
- Supabase (PostgreSQL + API REST).
- Esquema en `sql/schema.sql`.

**Modo offline**
- Cola local en SQLite.
- Reintentos automáticos cada 30s.
- Backups diarios en JSON.

## Estructura del proyecto

```
app/
  main.py                 # App principal (comandas)
  services/               # Supabase + offline
  ui/                     # Dialogs y vistas
  domain/                 # Cálculos
  assets/                 # Branding
sql/
  schema.sql              # Esquema de DB
scripts/
  update_pi.sh            # Update + restart
  run_pos.sh              # Autostart local
```

## Configuración

1) Crear entorno virtual
```bash
python3 -m venv .venv
source .venv/bin/activate
```

2) Instalar dependencias
```bash
pip install -r requirements.txt
```

3) Variables de entorno
```bash
cp .env.example .env
```
Editar `.env` con credenciales Supabase:
```env
SUPABASE_URL=...
SUPABASE_ANON_KEY=...
```

4) Ejecutar
```bash
python app/main.py
```

## Branding (AutoNoma)

Logo en `app/assets/`:
- `logo_autonoma_256.png` o `logo_autonoma.png`
- SVG opcional: `logo_autonoma.svg` (Tkinter no renderiza SVG directo)

## Módulos principales

- Comandas: multi‑comanda, edición rápida, atajos.
- Gastos: registro y consulta diaria.
- Propinas: registro y reporte mensual.
- Corte: resumen diario con efectivo teórico.
- Reportes: top productos, ventas por día, CSV.
- Personal: alta/baja de meseros.
- Productos: alta/edición de catálogo.

## Modo offline (técnico)

- SQLite local: `app/data/offline.db`
- Cola de operaciones: comandas, gastos, propinas, cierres.
- Sync cada 30s en `app/main.py` (`_sync_loop`).
- Backups diarios: `app/data/backups/offline_YYYY-MM-DD.json`

## Raspberry Pi (deploy)

Actualizar y reiniciar:
```bash
cd /home/adminbbq/barbacoa_pos
git checkout main
./scripts/update_pi.sh
```

Ejecutar manual:
```bash
./scripts/run_pos.sh
```
