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
BARBACOA_UI_SCALE=1.1
BARBACOA_UI_START_MODE=maximized
BARBACOA_UI_OPEN_COMANDAS=collapsed
BARBACOA_SUPABASE_TIMEOUT_SECONDS=20
BARBACOA_MESEROS_REFRESH_TTL_SECONDS=45
BARBACOA_TIMEZONE=America/Mexico_City
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

- Comandas: multi‑comanda, edición rápida, atajos y botones grandes para uso touch/teclado.
- Gastos: registro y consulta diaria.
- Propinas: registro y reporte diario por mesero.
- Corte: resumen diario con caja chica inicial y efectivo esperado en caja.
- Reportes: top productos, ventas por día, CSV.
- Personal: alta/baja de meseros.
- Productos: alta/edición de catálogo.

### UI recomendada para laptop rectangular

- `BARBACOA_UI_START_MODE=maximized` para abrir grande sin forzar fullscreen.
- `BARBACOA_UI_SCALE=1.1` como base recomendada para mejor lectura.
- `BARBACOA_UI_OPEN_COMANDAS=collapsed` para priorizar catálogo y comanda al iniciar.

## Roles y seguridad

- El sistema inicia siempre en rol `MESERO` (sin login).
- Para elevar permisos se usa **Desbloquear** con `ROL + PIN` (`GERENTE` o `DUEÑO`).
- Para regresar a modo base se usa **Bloquear**.
- `MESERO`: flujo de comandas.
- `GERENTE`: comandas + gastos + propinas + corte.
- `DUEÑO`: acceso total + personal + productos + seguridad de PIN.
- Si no hay meseros activos, no se permite guardar comandas hasta activar/crear personal con perfil privilegiado.
- Solo `DUEÑO` puede iniciar/cerrar/reabrir jornada de caja.
- La reapertura de un día cerrado requiere confirmación de PIN de dueño.
- `GERENTE` no tiene acceso a reportes.
- `GERENTE` y `DUEÑO` pueden cambiar su propio PIN desde la barra superior (botón `Cambiar PIN`).
- Recuperación de PIN: desde `Desbloquear` -> `Olvidé mi PIN`.
- El código se envía por correo a `sistemamirandapos@gmail.com` (o el correo configurado).
- El código rota en cada solicitud, expira y solo se puede usar una vez.
- Requiere SMTP configurado en `.env` y conexión a internet.

## Jornada de caja (ergonómico)

1) **Iniciar día**: el dueño captura `caja_chica_inicial` y abre la jornada.  
2) **Operar día**: el sistema calcula efectivo esperado en caja con:
`caja_chica_inicial + ventas_efectivo - gastos - propinas`.  
3) **Cerrar día**: el dueño captura efectivo contado y cierra la jornada.  
4) **Reabrir por accidente**: solo dueño, confirmando PIN, puede reabrir/editar y volver a cerrar.

Migración requerida en Supabase para jornada:
- `sql/cierres_jornada.sql`

Migración recomendada para origen de propinas por método:
- `sql/propinas_origen_metodo.sql`

Migración recomendada para venta por gramos y orden del catálogo en productos:
- `sql/productos_venta_por_gramo.sql`

## Seed inicial de roles

Configura en `.env`:

```env
BARBACOA_GERENTE_PIN=1234
BARBACOA_DUENIO_PIN=5678
BARBACOA_RECOVERY_EMAIL_TO=sistemamirandapos@gmail.com
BARBACOA_SMTP_HOST=smtp.gmail.com
BARBACOA_SMTP_PORT=587
BARBACOA_SMTP_USER=sistemamirandapos@gmail.com
BARBACOA_SMTP_PASSWORD=tu_app_password_de_gmail
BARBACOA_AUTH_CACHE_TTL_HOURS=24
```

Para Gmail, usa `App Password` (no tu contraseña normal).

Ejecuta:

```bash
python scripts/seed_roles.py
```

El seed es idempotente y migra `ADMIN -> DUENIO` (rol mostrado como `DUEÑO`) si detecta datos legacy.

## Auth offline

- Si Supabase no responde, el desbloqueo puede usar caché local en `app/data/auth_cache.json`.
- El caché expira según `BARBACOA_AUTH_CACHE_TTL_HOURS` (default `24`).

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

---

## ✅ Checklist de pruebas manuales (día real simulado)

1) Comandas
- Crear 10–15 comandas con mezcla EFECTIVO/TARJETA/TRANSFER.
- Verificar cambio correcto en EFECTIVO.
- Agregar propina en 2–3 comandas.

2) Gastos
- Registrar 3–5 gastos con categorías distintas.
- Verificar que aparezcan en “Gastos del día”.

3) Propinas
- Registrar 2 propinas manuales además de las de comandas.
- Verificar que se guarden sin error y aparezcan en el reporte diario.

4) Corte
- Abrir Corte y verificar ventas por método, gastos y propinas.
- Ingresar efectivo contado y verificar diferencia.
- Guardar el corte y reabrir para confirmar que carga.

5) Reportes
- Abrir Reportes con rango de 7 días.
- Verificar top productos y ventas por día.
- Exportar CSV y revisar carpeta `exports/`.

6) Gráficas
- Abrir Gráficas y revisar que salgan las 3 secciones.
- Repetir con otro rango de fechas.

---

## 🧾 Ticket de venta (vista previa y archivo)

Al guardar una comanda se genera un ticket con:
- Nombre del negocio, folio, fecha/hora
- Mesa, mesero, método de pago, propina y total
- Lista de productos
- Bloque de facturación con datos solicitados (Nombre, RFC, CP, Régimen Fiscal, Correo, WhatsApp)
- Mensaje de agradecimiento

El archivo se guarda en:
```
exports/tickets/
```

## 🖨️ Impresión de tickets (USB)

1) Conecta la impresora POS-5890 por USB y enciéndela.
2) Verifica el dispositivo:
```
ls /dev/usb/lp*
```
Si aparece, normalmente será `/dev/usb/lp0`.

3) Configura `.env`:
```env
BARBACOA_PRINTER_DEVICE=/dev/usb/lp0
BARBACOA_PRINTER_AUTOPRINT=true
```

4) Guarda una comanda y se imprimirá automáticamente.  
También puedes usar el botón “Imprimir” en la vista previa del ticket.

Si sale un error de permisos, agrega el usuario al grupo `lp` y reinicia sesión:
```bash
sudo usermod -aG lp $USER
```

Opcional: si usas CUPS, define `BARBACOA_PRINTER_NAME` y `BARBACOA_PRINTER_USE_CUPS=true`.

---

## 🖥️ Lanzador de escritorio (portable)

Para crear un acceso directo en el equipo:
```bash
bash scripts/install_desktop_shortcut.sh
```

Instala el launcher en el menú de aplicaciones y, si existe, en el Escritorio.  
En algunos entornos puede requerir marcar el acceso como “Allow Launching”.
